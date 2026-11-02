"""Muse Voice Transcribe bridge.

Two entry points, matching the hosted API:
  * WebSocket proxy toward wss://api.meta.ai/v1/asr/realtime
  * File POST toward https://api.meta.ai/v1/asr/transcribe

Speaker turns are parsed into hardware faults the MPC state vector can
apply. A jammed sluice mentioned as "50 percent" becomes orifice index 1
locked at 0.50. The parser is the load-bearing piece; the hosted ASR is
used when a key and audio are both present.
"""

from __future__ import annotations

import audioop
import io
import json
import re
import wave
from typing import Any

import httpx

from backend.agents.meta_client import _ssl_context
from backend.config import settings

_SPEAKER_RE = re.compile(r"\b(?:speaker|operator)\s*(\d+)\b", re.IGNORECASE)
_JAM_RE = re.compile(
    r"(?:orifice|sluice(?:\s+gate)?|gate)\s*(?:#|no\.?)?\s*([1-4]|OR\s*[1-4]|O\s*[1-4])"
    r".{0,80}?(?:jammed|stuck|locked|frozen|seized|mechanically)"
    r".{0,40}?(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)",
    re.IGNORECASE | re.DOTALL,
)
_JAM_ALT_RE = re.compile(
    r"(?:jammed|stuck|locked|frozen|seized).{0,40}?"
    r"(?:orifice|sluice(?:\s+gate)?|gate)\s*(?:#|no\.?)?\s*([1-4])"
    r".{0,40}?(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)",
    re.IGNORECASE | re.DOTALL,
)
_OR_RE = re.compile(r"\bOR\s*([1-4])\b|\bO([1-4])\b", re.IGNORECASE)
_PLANT_RE = re.compile(
    r"(?:plant|wwtp|treatment).{0,40}?(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)",
    re.IGNORECASE | re.DOTALL,
)

ROLES = {
    1: "Field Crew",
    2: "Plant Lead",
    3: "Interceptor Desk",
    4: "SCADA Operator",
}


def _orifice_index(token: str) -> int | None:
    match = re.search(r"([1-4])", token)
    if not match:
        return None
    return int(match.group(1)) - 1


def parse_faults(transcript: str) -> list[dict[str, Any]]:
    """Turn diarized radio text into structured actuator constraints."""
    faults: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for pattern in (_JAM_RE, _JAM_ALT_RE):
        for match in pattern.finditer(transcript):
            index = _orifice_index(match.group(1))
            if index is None:
                continue
            percent = float(match.group(2))
            if percent > 100:
                continue
            key = ("valve_jam", index, round(percent, 1))
            if key in seen:
                continue
            seen.add(key)
            speaker = _nearest_speaker(transcript, match.start())
            faults.append(
                {
                    "type": "valve_jam",
                    "orifice_index": index,
                    "orifice_id": f"OR{index + 1}",
                    "locked_setting": round(percent / 100.0, 4),
                    "speaker": speaker["label"],
                    "role": speaker["role"],
                    "raw": transcript[max(0, match.start() - 40) : match.end() + 20].strip(),
                }
            )
    for match in _PLANT_RE.finditer(transcript):
        percent = float(match.group(1))
        if percent > 100 or ("jam" in match.group(0).lower()):
            continue
        speaker = _nearest_speaker(transcript, match.start())
        faults.append(
            {
                "type": "plant_capacity",
                "capacity_fraction": round(percent / 100.0, 4),
                "speaker": speaker["label"],
                "role": speaker["role"],
                "raw": match.group(0).strip(),
            }
        )
    return faults


def _nearest_speaker(text: str, position: int) -> dict[str, str]:
    last = None
    for match in _SPEAKER_RE.finditer(text):
        if match.start() <= position:
            last = match
        else:
            break
    if last is None:
        return {"label": "Speaker 1", "role": ROLES[1]}
    number = int(last.group(1))
    return {"label": f"Speaker {number}", "role": ROLES.get(number, "Operator")}


def diarize_plaintext(transcript: str) -> list[dict[str, str]]:
    """Split a transcript into speaker turns. A single block is Speaker 1."""
    parts = re.split(r"(?=(?:Speaker|Operator)\s+\d+\s*[:\-])", transcript.strip(), flags=re.IGNORECASE)
    turns = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        speaker = _nearest_speaker(part, 0)
        spoken = re.sub(r"^(?:Speaker|Operator)\s+\d+\s*[:\-]\s*", "", part, flags=re.IGNORECASE)
        turns.append({"speaker": speaker["label"], "role": speaker["role"], "text": spoken.strip()})
    if not turns and transcript.strip():
        turns.append({"speaker": "Speaker 1", "role": ROLES[1], "text": transcript.strip()})
    return turns


def _to_api_wav(audio: bytes) -> bytes:
    """Meta accepts mono 16-bit PCM WAV at 16 kHz or 24 kHz."""
    try:
        with wave.open(io.BytesIO(audio)) as source:
            channels = source.getnchannels()
            width = source.getsampwidth()
            rate = source.getframerate()
            frames = source.readframes(source.getnframes())
    except wave.Error:
        return audio
    if width != 2:
        frames = audioop.lin2lin(frames, width, 2)
        width = 2
    if channels != 1:
        frames = audioop.tomono(frames, width, 0.5, 0.5)
    if rate not in (16000, 24000):
        frames, _ = audioop.ratecv(frames, 2, 1, rate, 16000, None)
        rate = 16000
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(frames)
    return output.getvalue()


async def transcribe_file(audio: bytes, filename: str = "war-room.wav") -> dict:
    """POST /v1/asr/transcribe. Offline callers get an empty transcript and a reason."""
    if not settings.meta_enabled:
        return {
            "ok": False,
            "source": "offline",
            "text": "",
            "turns": [],
            "faults": [],
            "detail": "MODEL_API_KEY is not configured; pass radio text to /api/voice/text.",
        }
    url = f"{settings.META_BASE_URL}/asr/transcribe"
    audio = _to_api_wav(audio)
    request = json.dumps(
        {
            "model": settings.MODEL_VOICE,
            "audioEncoding": "WAV",
            "mode": "DIARIZATION",
        }
    )
    files = {
        "request": (None, request, "application/json"),
        "audio": (filename, audio, "audio/wav"),
    }
    headers = {"Authorization": f"Bearer {settings.META_API_KEY}", "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=60.0, verify=_ssl_context()) as client:
        response = await client.post(url, headers=headers, files=files)
    if response.status_code >= 400:
        return {
            "ok": False,
            "source": "muse-voice-transcribe-1.0",
            "text": "",
            "turns": [],
            "faults": [],
            "detail": f"HTTP {response.status_code}: {response.text[:300]}",
        }
    body = response.json()
    text = body.get("text") or body.get("transcript") or ""
    if not text and isinstance(body.get("segments"), list):
        chunks = []
        for segment in body["segments"]:
            speaker = segment.get("speaker") or "Speaker 1"
            chunks.append(f"{speaker}: {segment.get('text', '')}")
        text = "\n".join(chunks)
    return {
        "ok": True,
        "source": "muse-voice-transcribe-1.0",
        "text": text,
        "turns": diarize_plaintext(text),
        "faults": parse_faults(text),
        "latency_ms": None,
    }


def realtime_url() -> str:
    """WebSocket URL for the live microphone proxy."""
    base = settings.META_BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
    return f"{base}/asr/realtime?model={settings.MODEL_VOICE}"


def ingest_transcript(text: str, t_min: float) -> dict:
    turns = diarize_plaintext(text)
    for turn in turns:
        turn["t_min"] = t_min
    return {"turns": turns, "faults": parse_faults(text)}
