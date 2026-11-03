"""FastAPI command bus. The hydraulic twin streams to the React SCADA UI."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.agents.voice_scada_bridge import realtime_url
from backend.config import SWMM_DIR, settings
from backend.episode import episode
from backend.physics.radar_synthesizer import render_frame_png
from backend.physics.swmm_engine import run_episode, try_pyswmm_available, write_interceptor_inp


class TranscriptIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class FaultIn(BaseModel):
    orifice_index: int = 1
    locked_setting: float = 0.5


class StormIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)


class CellIn(BaseModel):
    x: float
    y: float
    dbz: float = 60.0


@asynccontextmanager
async def lifespan(_app: FastAPI):
    write_interceptor_inp(SWMM_DIR / "interceptor.inp")
    await episode.start()
    yield
    episode.running = False


app = FastAPI(title="StormGate-Zero", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "meta_configured": settings.meta_enabled,
        "open_weight_configured": settings.open_weight_enabled,
        "open_weight_host": "brev" if settings.brev_configured else "partner",
        "open_weight_model": settings.open_weight_model,
        "pyswmm": try_pyswmm_available(),
        "step": episode.sim.step_index,
        "running": episode.running,
    }


@app.get("/api/state")
async def state() -> dict:
    return episode.public_state()


@app.post("/api/episode/start")
async def start() -> dict:
    await episode.start()
    return episode.public_state()


@app.post("/api/episode/pause")
async def pause() -> dict:
    await episode.pause()
    return episode.public_state()


@app.get("/api/storms")
async def storms() -> dict:
    from backend.physics.storm_catalog import list_storms

    return {"storms": list_storms(), "active": episode.public_state()["storm"]}


@app.post("/api/storm")
async def choose_storm(body: StormIn) -> dict:
    try:
        storm = await episode.use_storm(body.id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown storm {exc}") from exc
    return {"ok": True, "storm": storm, "state": episode.public_state()}


@app.post("/api/storm/cell")
async def drop_cell(body: CellIn) -> dict:
    storm = await episode.drop_cell(body.x, body.y, body.dbz)
    return {"ok": True, "storm": storm, "state": episode.public_state()}


@app.post("/api/verify/wave")
async def verify_wave() -> dict:
    episode.wave = None
    await episode._maybe_wave(force=True)
    await episode.publish()
    return episode.wave or {"ok": False, "error": "no orifice history yet"}


@app.post("/api/episode/reset")
async def reset() -> dict:
    await episode.reset()
    await episode.start()
    return episode.public_state()


@app.post("/api/fault")
async def fault(_body: FaultIn | None = None) -> dict:
    """Chaos injector. The canonical radio call is parsed like any other transcript."""
    parsed = await episode.inject_jam()
    return {"ok": True, **parsed, "state": episode.public_state()}


@app.post("/api/fault/clear")
async def fault_clear() -> dict:
    await episode.clear_jam()
    return episode.public_state()


@app.post("/api/voice/text")
async def voice_text(body: TranscriptIn) -> dict:
    parsed = await episode.inject_transcript(body.text, source="TEXT")
    return {"ok": True, **parsed}


@app.post("/api/voice/transcribe")
async def voice_file(file: UploadFile = File(...)) -> dict:
    from backend.agents.voice_scada_bridge import transcribe_file

    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="empty audio")
    result = await transcribe_file(audio, file.filename or "war-room.wav")
    if result.get("text"):
        parsed = await episode.inject_transcript(result["text"], source="MUSE VOICE", latency_ms=result.get("latency_ms"))
        result["applied"] = parsed
    episode.models["muse-voice-transcribe-1.0"] = {
        "status": "LIVE" if result.get("ok") else "OFFLINE",
        "latency_ms": result.get("latency_ms"),
    }
    await episode.publish()
    return result


@app.post("/api/outfall")
async def outfall() -> dict:
    from backend.agents.image_counterfactual import render_anchored

    rendered = await render_anchored(episode.sim.baseline.cso_mg * 1_000_000, episode.sim.stormgate.cso_mg * 1_000_000)
    episode.outfall_ready = True
    episode.models["muse-image-1.0"] = {
        "status": "LIVE" if rendered.get("source") == "muse-image-1.0" else "ANCHORED PLATE",
        "latency_ms": rendered.get("latency_ms"),
    }
    await episode.publish()
    # The PNG is fetched from /api/outfall/latest so the JSON stays small.
    rendered.pop("image_png_base64", None)
    return rendered


@app.get("/api/outfall/latest")
async def outfall_latest() -> Response:
    from backend.config import OUTFALL_DIR

    path = OUTFALL_DIR / "counterfactual.png"
    if not path.exists():
        from backend.agents.image_counterfactual import render_outfall_plate

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            render_outfall_plate(episode.sim.baseline.cso_mg * 1_000_000, episode.sim.stormgate.cso_mg * 1_000_000)
        )
    return Response(content=path.read_bytes(), media_type="image/png")


@app.get("/api/radar/frame/{index}")
async def radar_frame(index: int, storm: str = "") -> Response:
    from backend.physics.nexrad_mosaic import frame_png
    from backend.physics.storm_catalog import current

    storm_id = storm or current()["id"]
    real = frame_png(storm_id, index)
    if real is not None:
        return Response(content=real, media_type="image/png")
    index = max(0, min(index, 36))
    t_min = 90.0 * index / 36.0
    return Response(content=render_frame_png(t_min), media_type="image/png")


@app.get("/api/benchmark")
async def benchmark() -> dict:
    rows = []
    for name in ("uncontrolled", "local", "stormgate"):
        result = run_episode(name)
        rows.append(
            {
                "policy": name,
                "cso_gallons": round(result["cso_gallons"], 1),
                "street_gallons": round(result["street_gallons"], 1),
                "max_depth": [round(v, 4) for v in result["max_depth"]],
                "min_depth": [round(v, 4) for v in result["min_depth"]],
            }
        )
    jammed = run_episode("stormgate", jammed_at=8)
    rows.append(
        {
            "policy": "stormgate_or2_jammed",
            "cso_gallons": round(jammed["cso_gallons"], 1),
            "street_gallons": round(jammed["street_gallons"], 1),
            "max_depth": [round(v, 4) for v in jammed["max_depth"]],
            "min_depth": [round(v, 4) for v in jammed["min_depth"]],
        }
    )
    return {"design_storm": "DS-1482", "rows": rows}


@app.websocket("/ws/twin")
async def twin(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = episode.subscribe()
    try:
        await websocket.send_json(episode.public_state())
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        episode.unsubscribe(queue)


@app.websocket("/ws/voice")
async def voice_socket(websocket: WebSocket) -> None:
    """Browser microphone proxy.

    Text frames are JSON. `{type:"transcript", text:"..."}` is parsed locally.
    Binary frames are forwarded to Muse Voice realtime when a key is set.
    """
    await websocket.accept()
    upstream = None
    relay = None
    if settings.meta_enabled:
        try:
            import websockets

            upstream = await websockets.connect(
                realtime_url(),
                additional_headers={"Authorization": f"Bearer {settings.META_API_KEY}"},
            )

            async def _relay() -> None:
                try:
                    async for incoming in upstream:
                        if isinstance(incoming, bytes):
                            await websocket.send_bytes(incoming)
                        else:
                            await websocket.send_text(incoming)
                            try:
                                event = json.loads(incoming)
                            except json.JSONDecodeError:
                                event = {}
                            text = event.get("text") or event.get("transcript")
                            if text:
                                await episode.inject_transcript(str(text), source="MUSE VOICE")
                except Exception:
                    return

            relay = asyncio.create_task(_relay())
        except Exception as exc:
            await websocket.send_json({"type": "status", "source": "offline", "detail": str(exc)})
    else:
        await websocket.send_json(
            {"type": "status", "source": "offline", "detail": "realtime ASR key not configured"}
        )
    try:
        while True:
            incoming = await websocket.receive()
            if incoming.get("text"):
                try:
                    event = json.loads(incoming["text"])
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "transcript" and event.get("text"):
                    parsed = await episode.inject_transcript(str(event["text"]), source="BROWSER SPEECH")
                    await websocket.send_json({"type": "parsed", **parsed})
                elif upstream is not None:
                    await upstream.send(incoming["text"])
            elif incoming.get("bytes") and upstream is not None:
                await upstream.send(incoming["bytes"])
    except WebSocketDisconnect:
        pass
    finally:
        if relay is not None:
            relay.cancel()
        if upstream is not None:
            await upstream.close()
