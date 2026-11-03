"""SAM 3.1 video segmentation, with a deterministic geometric fallback.

Primary path: POST https://api.meta.ai/v1/responses, model sam-3.1, with
either a concept phrase ("red storm cell") or an `<0f>` object prompt.
SAM accepts one or the other, never both in the same request.

Fallback path: OpenCV HSV threshold of Frame 0 at >45 dBZ (red/magenta
cores), formatted with `build_object_prompt`. Those boxes seed object
multiplex for the rest of the tape. Masks are intersected with the GIS
subcatchment polygons to build the 45-minute runoff lookahead.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

import numpy as np

from backend.config import settings
from backend.physics.design_storm import mg_step_to_mmhr
from backend.physics.storm_catalog import active_rain
from backend.physics.radar_synthesizer import active_cores, render_frame_rgb
from backend.physics.swmm_engine import forecast_window

# Wire grammar
# Request, concept form (no boxes):
#   <0f><concept>red storm cell</concept></0f>
# Request, object form (no concept):
#   <0f><objects><obj id="0"><box x1="0.1" y1="0.2" x2="0.3" y2="0.4"/></obj></objects></0f>
# Response frame:
#   <0f><frame index="2" t="10">
#     <obj id="0"><box x1="0.1" y1="0.2" x2="0.3" y2="0.4"/>
#     <mask codec="rle" width="64" height="64">1 4 0 8</mask></obj>
#   </frame></0f>

_FRAME_RE = re.compile(r"<frame\b([^>]*)>(.*?)</frame>", re.IGNORECASE | re.DOTALL)
_OBJ_RE = re.compile(r"<obj\b([^>]*)>(.*?)</obj>", re.IGNORECASE | re.DOTALL)
_BOX_ATTR_RE = re.compile(
    r"<box\b[^>]*x1=\"([0-9.]+)\"[^>]*y1=\"([0-9.]+)\"[^>]*x2=\"([0-9.]+)\"[^>]*y2=\"([0-9.]+)\"[^>]*/?>",
    re.IGNORECASE,
)
_BOX_TEXT_RE = re.compile(
    r"<box>\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*</box>",
    re.IGNORECASE,
)
_MASK_RE = re.compile(
    r"<mask\b([^>]*)>([0-9\s]+)</mask>",
    re.IGNORECASE,
)
_ATTR_RE = re.compile(r"([A-Za-z0-9_]+)=\"([^\"]*)\"")
_PIPE_BOX_RE = re.compile(
    r"<\|box;x1=([0-9.]+);y1=([0-9.]+);x2=([0-9.]+);y2=([0-9.]+);w=([0-9.]+);h=([0-9.]+)\|>",
    re.IGNORECASE,
)


def _attrs(blob: str) -> dict[str, str]:
    return {key: value for key, value in _ATTR_RE.findall(blob)}


def build_object_prompt(boxes: list[tuple[float, float, float, float]]) -> str:
    """Format Frame-0 boxes in the `<0f>` object-multiplex grammar. Max 16."""
    parts = ["<0f><objects>"]
    for index, box in enumerate(boxes[:16]):
        x1, y1, x2, y2 = box
        parts.append(
            f'<obj id="{index}"><box x1="{x1:.4f}" y1="{y1:.4f}" x2="{x2:.4f}" y2="{y2:.4f}"/></obj>'
        )
    parts.append("</objects></0f>")
    return "".join(parts)


def build_concept_prompt(concept: str = "red storm cell") -> str:
    safe = concept.replace("<", "").replace(">", "")
    return f"<0f><concept>{safe}</concept></0f>"


def decode_rle(counts: list[int], width: int, height: int) -> np.ndarray:
    """Row-major start-with-zero run-length mask, clipped to width*height."""
    mask = np.zeros(width * height, dtype=np.uint8)
    cursor = 0
    value = 0
    for count in counts:
        count = int(count)
        if count <= 0:
            value = 1 - value
            continue
        end = min(cursor + count, mask.size)
        if value == 1:
            mask[cursor:end] = 1
        cursor = end
        value = 1 - value
        if cursor >= mask.size:
            break
    return mask.reshape((height, width))


def parse_sam_wire(payload: str) -> list[dict]:
    """Built-in parser for the `<0f>` grammar. Returns frames of objects."""
    frames = []
    blocks = _FRAME_RE.findall(payload) or [("", payload)]
    for attr_blob, inner in blocks:
        attrs = _attrs(attr_blob)
        objects = []
        for obj_attrs, obj_inner in _OBJ_RE.findall(inner):
            meta = _attrs(obj_attrs)
            box = _BOX_ATTR_RE.search(obj_inner) or _BOX_TEXT_RE.search(obj_inner)
            if not box:
                continue
            coords = tuple(float(v) for v in box.groups())
            mask = None
            mask_match = _MASK_RE.search(obj_inner)
            if mask_match:
                mask_meta = _attrs(mask_match.group(1))
                counts = [int(tok) for tok in mask_match.group(2).split() if tok.isdigit()]
                width = int(mask_meta.get("width", "64"))
                height = int(mask_meta.get("height", "64"))
                mask = decode_rle(counts, width, height)
            objects.append({"id": int(meta.get("id", len(objects))), "box": coords, "mask": mask})
        if objects:
            frames.append(
                {
                    "index": int(attrs.get("index", len(frames))),
                    "t_min": float(attrs.get("t", "0")),
                    "objects": objects,
                }
            )
    return frames


def boxes_from_sam_text(payload: str) -> list[tuple[float, float, float, float]]:
    """Normalize the `<|box;x1=...;w=480;h=480|>` wire into unit-square boxes."""
    boxes = []
    for match in _PIPE_BOX_RE.finditer(payload or ""):
        x1, y1, x2, y2, width, height = (float(value) for value in match.groups())
        if width <= 0 or height <= 0:
            continue
        boxes.append((x1 / width, y1 / height, x2 / width, y2 / height))
    return boxes


def parse_sam_payload(payload: str) -> list[dict]:
    """Prefer Meta's parser when it is installed, otherwise the built-in grammar."""
    try:
        import meta_sam_parser  # type: ignore

        parsed = meta_sam_parser.parse(payload)
        if isinstance(parsed, list) and parsed:
            return parsed
    except Exception:
        pass
    return parse_sam_wire(payload)


def _boxes_from_rgb(rgb: np.ndarray) -> list[tuple[float, float, float, float]]:
    """>45 dBZ cores are red/magenta on the NEXRAD scale. HSV via OpenCV."""
    height, width = rgb.shape[:2]
    mask = None
    try:
        import cv2

        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        red_low = cv2.inRange(hsv, (0, 90, 80), (12, 255, 255))
        red_high = cv2.inRange(hsv, (168, 70, 70), (179, 255, 255))
        mask = cv2.bitwise_or(red_low, red_high)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w * h < 70:
                continue
            boxes.append((x / width, y / height, (x + w) / width, (y + h) / height))
    except Exception:
        red = rgb[:, :, 0].astype(np.int16)
        green = rgb[:, :, 1].astype(np.int16)
        blue = rgb[:, :, 2].astype(np.int16)
        hot = ((red > 160) & (green < 120) & (blue < 140)) | ((red > 150) & (blue > 130) & (green < 120))
        boxes = _component_boxes(hot, width, height)
    boxes.sort(key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
    return boxes[:16]


def _component_boxes(hot: np.ndarray, width: int, height: int) -> list[tuple[float, float, float, float]]:
    """Connected components without OpenCV, used when the codec stack is absent."""
    visited = np.zeros_like(hot, dtype=bool)
    boxes = []
    ys, xs = np.where(hot)
    for seed_y, seed_x in zip(ys.tolist(), xs.tolist()):
        if visited[seed_y, seed_x]:
            continue
        stack = [(seed_y, seed_x)]
        visited[seed_y, seed_x] = True
        min_x = max_x = seed_x
        min_y = max_y = seed_y
        count = 0
        while stack:
            y, x = stack.pop()
            count += 1
            min_x, max_x = min(min_x, x), max(max_x, x)
            min_y, max_y = min(min_y, y), max(max_y, y)
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if ny < 0 or nx < 0 or ny >= height or nx >= width:
                    continue
                if visited[ny, nx] or not hot[ny, nx]:
                    continue
                visited[ny, nx] = True
                stack.append((ny, nx))
        if count < 70:
            continue
        boxes.append((min_x / width, min_y / height, (max_x + 1) / width, (max_y + 1) / height))
    return boxes


def extract_dbz_boxes_frame0(video_path: str | None = None) -> list[tuple[float, float, float, float]]:
    """Seed boxes from the first frame of the radar tape, or from a render at t=0."""
    frame = None
    if video_path and Path(video_path).exists():
        try:
            import cv2

            capture = cv2.VideoCapture(str(video_path))
            ok, bgr = capture.read()
            capture.release()
            if ok and bgr is not None:
                frame = bgr[:, :, ::-1]
        except Exception:
            frame = None
    if frame is None:
        frame = render_frame_rgb(0.0)
    return _boxes_from_rgb(frame)


def _polygon_coverage(cx: float, cy: float, sigma: float, rect: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = rect
    xs = np.linspace(x1, x2, 18)
    ys = np.linspace(y1, y2, 18)
    grid_x, grid_y = np.meshgrid(xs, ys)
    weight = np.exp(-((grid_x - cx) ** 2 + (grid_y - cy) ** 2) / (2 * sigma * sigma))
    return float(weight.mean())


def coverage_by_basin(cores: list[dict]) -> dict[str, float]:
    coverage = {name: 0.0 for name in settings.BASIN_IDS}
    for core in cores:
        sigma = max(float(core.get("rx", 0.08)) / 1.6, 0.04)
        for name, rect in settings.SUBCATCHMENT_POLYGONS.items():
            coverage[name] = max(
                coverage[name],
                _polygon_coverage(float(core["cx"]), float(core["cy"]), sigma, rect),
            )
    return {key: round(value, 4) for key, value in coverage.items()}


def lookahead_mmhr(step_index: int) -> dict[str, list[float]]:
    """45-minute hyetograph. Quantitative rates come from the calibrated Z-R
    product of this tape; polygon coverage is reported alongside for the operator."""
    window = forecast_window(step_index, settings.LOOKAHEAD_STEPS)
    mmhr = mg_step_to_mmhr(window)
    named = {}
    for index, basin in enumerate(settings.BASIN_SHORT):
        named[basin] = [round(float(v), 2) for v in mmhr[:, index]]
    return named


def _sam_boxes(t_min: float) -> list[tuple[float, float, float, float]] | None:
    from backend.agents.model_traces import load as load_traces
    from backend.physics.storm_catalog import current

    traces = load_traces()
    storm_id = current()["id"]
    if storm_id == "ds-1482":
        frames = (traces.get("sam") or {}).get("frames") or []
    else:
        frames = ((traces.get("sam_events") or {}).get(storm_id) or {}).get("frames") or []
    if not frames:
        return None
    nearest = min(frames, key=lambda frame: abs(float(frame.get("t_min", 0)) - t_min))
    boxes = []
    for obj in nearest.get("objects") or []:
        box = obj.get("box")
        if isinstance(box, (list, tuple)) and len(box) == 4:
            boxes.append(tuple(float(v) for v in box))
    return boxes or None


def radar_snapshot(step_index: int, t_min: float) -> dict:
    """Everything the command center needs for one radar beat."""
    cores = active_cores(t_min)
    sam_boxes = _sam_boxes(t_min)
    if sam_boxes:
        boxes = sam_boxes
    else:
        boxes = [(c["cx"] - c["rx"], c["cy"] - c["ry"], c["cx"] + c["rx"], c["cy"] + c["ry"]) for c in cores]
    # Clip boxes into the unit square for the prompt grammar.
    clipped = []
    for x1, y1, x2, y2 in boxes:
        clipped.append((max(0.0, x1), max(0.0, y1), min(1.0, x2), min(1.0, y2)))
    return {
        "t_min": t_min,
        "cores": cores,
        "coverage": coverage_by_basin(cores),
        "object_prompt": build_object_prompt(clipped) if clipped else build_concept_prompt(),
        "forecast_mm_hr": lookahead_mmhr(step_index),
        "forecast_mg": forecast_window(step_index, settings.HORIZON_STEPS),
        "rain_now_mg": active_rain()[step_index].tolist() if step_index < len(active_rain()) else [0, 0, 0, 0],
    }


async def segment_frames(times_min: list[float]) -> dict:
    """Ask sam-3.1 to segment rendered radar frames. One call per time."""
    import io

    from PIL import Image

    from backend.agents.meta_client import OfflineModelError, stream_response_text
    from backend.agents.model_traces import load as load_traces
    from backend.agents.model_traces import save as save_traces

    frames = []
    errors = []
    latency = 0.0
    for t_min in times_min:
        rgb = render_frame_rgb(t_min)
        buffer = io.BytesIO()
        Image.fromarray(rgb).save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        content = [
            {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"},
            {"type": "input_text", "text": "red storm cell"},
        ]
        try:
            text, elapsed = await stream_response_text(settings.MODEL_SAM, content, timeout=70.0)
            latency += elapsed
            parsed = parse_sam_payload(text)
            objects = []
            for frame in parsed:
                for obj in frame.get("objects") or []:
                    box = obj.get("box")
                    if isinstance(box, (list, tuple)) and len(box) == 4:
                        objects.append({"id": obj.get("id", len(objects)), "box": [round(float(v), 4) for v in box]})
            if not objects:
                for box in boxes_from_sam_text(text):
                    objects.append({"id": len(objects), "box": [round(v, 4) for v in box]})
            frames.append(
                {
                    "t_min": t_min,
                    "objects": objects,
                    "raw_excerpt": text[:500],
                }
            )
        except (OfflineModelError, Exception) as exc:
            errors.append({"t_min": t_min, "detail": str(exc)[:300]})
    payload = {
        "ok": bool(frames) and not errors,
        "model": settings.MODEL_SAM,
        "latency_ms": round(latency, 1),
        "frames": frames,
        "errors": errors,
    }
    traces = load_traces()
    traces["sam"] = payload
    save_traces(traces)
    return payload


async def segment_pngs(storm_id: str, paths: list[Path], concept: str = "red storm cell") -> dict:
    """Segment real mosaic crops. Stored beside the DS-1482 SAM trace, not over it."""
    from backend.agents.meta_client import OfflineModelError, stream_response_text
    from backend.agents.model_traces import load as load_traces
    from backend.agents.model_traces import save as save_traces

    frames = []
    errors = []
    latency = 0.0
    for index, path in enumerate(paths):
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        content = [
            {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"},
            {"type": "input_text", "text": concept},
        ]
        t_min = index * 15.0
        try:
            text, elapsed = await stream_response_text(settings.MODEL_SAM, content, timeout=70.0)
            latency += elapsed
            objects = []
            for box in boxes_from_sam_text(text):
                objects.append({"id": len(objects), "box": [round(v, 4) for v in box]})
            if not objects:
                for frame in parse_sam_payload(text):
                    for obj in frame.get("objects") or []:
                        box = obj.get("box")
                        if isinstance(box, (list, tuple)) and len(box) == 4:
                            objects.append({"id": len(objects), "box": [round(float(v), 4) for v in box]})
            frames.append({"t_min": t_min, "file": path.name, "objects": objects, "raw_excerpt": text[:500]})
        except (OfflineModelError, Exception) as exc:
            errors.append({"t_min": t_min, "file": path.name, "detail": str(exc)[:300]})
    payload = {
        "ok": bool(frames) and not errors,
        "model": settings.MODEL_SAM,
        "product": "IEM N0Q mosaic crop",
        "latency_ms": round(latency, 1),
        "frames": frames,
        "errors": errors,
    }
    traces = load_traces()
    traces.setdefault("sam_events", {})
    traces["sam_events"][storm_id] = payload
    save_traces(traces)
    return payload


async def segment_video(video_path: str, *, use_boxes: bool = False) -> dict:
    """Call sam-3.1. Concept phrase and box prompt are mutually exclusive."""
    from backend.agents.meta_client import OfflineModelError, stream_response_text

    video = Path(video_path)
    if use_boxes:
        boxes = extract_dbz_boxes_frame0(str(video) if video.exists() else None)
        prompt = build_object_prompt(boxes)
        content = [{"type": "input_text", "text": prompt}]
    else:
        boxes = []
        content = [{"type": "input_text", "text": "red storm cell"}]
    if video.exists():
        encoded = base64.b64encode(video.read_bytes()).decode("ascii")
        content.insert(0, {"type": "input_video", "video_url": f"data:video/mp4;base64,{encoded}"})
    try:
        text, latency_ms = await stream_response_text(settings.MODEL_SAM, content)
        frames = parse_sam_payload(text)
        return {
            "ok": True,
            "source": "sam-3.1",
            "latency_ms": round(latency_ms, 1),
            "frames": [
                {"index": f["index"], "objects": [{"id": o["id"], "box": o["box"]} for o in f["objects"]]}
                for f in frames
            ],
            "seed_boxes": boxes,
        }
    except OfflineModelError as exc:
        return {"ok": False, "source": "geometric-fallback", "detail": str(exc), "seed_boxes": boxes}
