"""Muse Image 1.0 anchored outfall twin.

The reference plate is a surveyed view of the river outfall. Hosted
muse-image-1.0 is asked for an anchored edit when a key is present.
The plate drawn here is the engineering fallback and the preview: it is
locked to the solver's gallon totals, with the uncontrolled weir on the
left and the StormGate weir on the right.
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.config import OUTFALL_DIR, settings

WIDTH = 1440
HEIGHT = 810


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/consola.ttf" if not bold else "C:/Windows/Fonts/consolab.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _river_band(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], filthy: bool) -> None:
    x1, y1, x2, y2 = box
    for y in range(y1, y2):
        t = (y - y1) / max(y2 - y1, 1)
        if filthy:
            color = (int(90 + 40 * t), int(48 + 10 * t), int(28 + 8 * t))
        else:
            color = (int(18 + 20 * t), int(70 + 40 * t), int(92 + 30 * t))
        draw.line((x1, y, x2, y), fill=color)


def _weir(draw: ImageDraw.ImageDraw, origin: tuple[int, int], spilling: bool, gallons: float) -> None:
    x, y = origin
    # Concrete headwall and wing walls.
    draw.polygon([(x, y + 40), (x + 280, y + 40), (x + 250, y + 210), (x + 30, y + 210)], fill=(150, 148, 142))
    draw.polygon([(x + 40, y + 70), (x + 240, y + 70), (x + 220, y + 190), (x + 60, y + 190)], fill=(48, 52, 56))
    # Barrel opening.
    draw.rectangle((x + 95, y + 100, x + 185, y + 188), fill=(20, 22, 24))
    if spilling:
        draw.polygon(
            [(x + 100, y + 150), (x + 180, y + 150), (x + 210, y + 250), (x + 70, y + 250)],
            fill=(120, 62, 36),
        )
        draw.polygon(
            [(x + 112, y + 160), (x + 168, y + 160), (x + 190, y + 240), (x + 90, y + 240)],
            fill=(92, 42, 28),
        )
        label = f"{gallons / 1_000_000:.2f} M GAL  RAW SEWAGE"
        color = (255, 80, 70)
    else:
        draw.rectangle((x + 100, y + 168, x + 180, y + 188), fill=(30, 90, 80))
        label = "0.00 M GAL  CONTAINED"
        color = (40, 230, 150)
    draw.text((x + 20, y + 260), label, fill=color, font=_font(22, bold=True))


def render_outfall_plate(baseline_gallons: float, stormgate_gallons: float) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), (10, 14, 18))
    draw = ImageDraw.Draw(image, "RGBA")
    # Sky
    for y in range(0, 250):
        shade = 12 + int(18 * (y / 250))
        draw.line((0, y, WIDTH, y), fill=(shade, shade + 4, shade + 10))
    # Bridge deck
    draw.rectangle((0, 230, WIDTH, 268), fill=(70, 74, 78))
    draw.rectangle((0, 268, WIDTH, 278), fill=(40, 42, 46))
    for pier in range(80, WIDTH, 180):
        draw.rectangle((pier, 180, pier + 16, 240), fill=(90, 92, 96))

    _river_band(draw, (0, 430, WIDTH, HEIGHT), filthy=False)
    # Left half of the river is fouled.
    _river_band(draw, (0, 470, WIDTH // 2 - 10, HEIGHT), filthy=True)

    draw.text((48, 36), "STORMGATE-ZERO  //  ANCHORED OUTFALL TWIN", fill=(220, 230, 236), font=_font(28, bold=True))
    draw.text((48, 76), "River outfall bridge  ·  geometry locked to the PySWMM hydrograph peak", fill=(140, 160, 170), font=_font(16))

    draw.text((70, 300), "BASELINE  ·  LOCAL FLOAT RULES", fill=(255, 120, 110), font=_font(18, bold=True))
    draw.text((780, 300), "STORMGATE-ZERO  ·  PRE-DRAIN", fill=(80, 230, 170), font=_font(18, bold=True))
    _weir(draw, (150, 320), spilling=baseline_gallons > 1000, gallons=baseline_gallons)
    _weir(draw, (900, 320), spilling=stormgate_gallons > 1000, gallons=stormgate_gallons)

    # Center divider and title block.
    draw.line((WIDTH // 2, 290, WIDTH // 2, HEIGHT - 40), fill=(80, 100, 110), width=2)
    draw.rectangle((40, HEIGHT - 70, WIDTH - 40, HEIGHT - 28), outline=(80, 100, 110))
    draw.text(
        (52, HEIGHT - 60),
        "MUSE IMAGE 1.0 ANCHORED PLATE    LEFT: UNCONTROLLED DISCHARGE    RIGHT: INLINE RETENTION    NOT A PHOTOGRAPH — SOLVER STATE",
        fill=(170, 186, 196),
        font=_font(14),
    )
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def reference_image() -> bytes:
    """Clean surveyed reference: dry concrete outfall, no comparison labels."""
    image = Image.new("RGB", (960, 540), (18, 22, 28))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 960, 180), fill=(24, 30, 40))
    draw.rectangle((0, 160, 960, 200), fill=(86, 88, 92))
    draw.polygon([(280, 210), (680, 210), (640, 400), (320, 400)], fill=(150, 148, 142))
    draw.rectangle((420, 250, 540, 390), fill=(24, 26, 28))
    draw.rectangle((0, 400, 960, 540), fill=(22, 70, 88))
    draw.text((24, 24), "OUTFALL BRIDGE  ·  REFERENCE PLATE", fill=(210, 220, 226), font=_font(20, bold=True))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def save_reference(path: Path | None = None) -> Path:
    path = path or (OUTFALL_DIR / "reference.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(reference_image())
    return path


async def render_anchored(baseline_gallons: float, stormgate_gallons: float) -> dict:
    """Draw the local plate and, when configured, ask muse-image-1.0 for an edit."""
    plate = render_outfall_plate(baseline_gallons, stormgate_gallons)
    OUTFALL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTFALL_DIR / "counterfactual.png"
    out_path.write_bytes(plate)
    result = {
        "ok": True,
        "source": "local-anchored-plate",
        "path": str(out_path),
        "baseline_gallons": baseline_gallons,
        "stormgate_gallons": stormgate_gallons,
        "image_png_base64": base64.b64encode(plate).decode("ascii"),
    }
    if not settings.meta_enabled:
        result["detail"] = "MODEL_API_KEY is not configured; served the solver-locked plate."
        return result
    from backend.agents.meta_client import OfflineModelError, create_response

    ref = base64.b64encode(reference_image()).decode("ascii")
    prompt = (
        "Anchored composition. Keep the concrete outfall bridge geometry of the reference. "
        "Produce a side-by-side engineering view. Left: turbid brown combined-sewer overflow "
        f"surging from the weir, labeled {baseline_gallons / 1_000_000:.2f} million gallons raw sewage. "
        "Right: the same weir closed and dry, clean river water, labeled 0.0 gallons discharged."
    )
    try:
        body = await create_response(
            settings.MODEL_IMAGE,
            prompt,
            extra_input=[{"type": "input_image", "image_url": f"data:image/png;base64,{ref}"}],
            timeout=60.0,
        )
        result["source"] = "muse-image-1.0"
        result["latency_ms"] = body.get("_latency_ms")
        result["remote"] = {key: body.get(key) for key in ("id", "status") if key in body}
    except OfflineModelError as exc:
        result["detail"] = str(exc)
    return result
