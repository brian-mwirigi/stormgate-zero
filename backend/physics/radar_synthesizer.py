"""Synthetic NEXRAD Doppler reflectivity for the design storm.

Frames are a calibrated radar product: two convective cores advect across
the four sewer subcatchments. The same kinematics drive the SAM fallback
and the picture the command center paints.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from backend.config import settings
from backend.physics.design_storm import cell_state
from backend.physics.storm_catalog import active_cells

FRAME_SIZE = 480


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def dbz_to_rgb(dbz: np.ndarray) -> np.ndarray:
    """NEXRAD-like color scale. High cores land in red and magenta so a
    45 dBZ threshold can seed SAM boxes without a model call."""
    stops = [
        (0.0, (8, 12, 20)),
        (12.0, (16, 40, 92)),
        (22.0, (18, 110, 70)),
        (32.0, (40, 190, 70)),
        (40.0, (230, 190, 30)),
        (46.0, (230, 70, 30)),
        (52.0, (210, 30, 50)),
        (58.0, (230, 40, 190)),
        (70.0, (255, 240, 255)),
    ]
    rgb = np.zeros(dbz.shape + (3,), dtype=np.float32)
    for (v0, c0), (v1, c1) in zip(stops, stops[1:]):
        span = max(v1 - v0, 1e-6)
        t = np.clip((dbz - v0) / span, 0.0, 1.0)
        band = (dbz >= v0) & (dbz <= v1)
        for channel in range(3):
            column = _lerp(c0[channel], c1[channel], t)
            rgb[..., channel] = np.where(band, column, rgb[..., channel])
    rgb = np.where(dbz[..., None] <= 0.5, np.array([8, 12, 20], dtype=np.float32), rgb)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def reflectivity_field(t_min: float, size: int = FRAME_SIZE) -> np.ndarray:
    """dBZ grid at time t, shape (size, size), y axis downward."""
    ys = (np.arange(size) + 0.5) / size
    xs = (np.arange(size) + 0.5) / size
    grid_x, grid_y = np.meshgrid(xs, ys)
    field = np.zeros((size, size), dtype=np.float32)
    # Weak stratiform background so the scope is not a black void.
    field += 8.0 + 3.0 * np.sin(grid_x * 9.0 + t_min * 0.05) * np.cos(grid_y * 7.0)
    for cell in active_cells():
        state = cell_state(cell, t_min)
        if state is None:
            continue
        x, y, dbz = state
        sigma = float(cell["sigma"])
        weight = np.exp(-((grid_x - x) ** 2 + (grid_y - y) ** 2) / (2 * sigma * sigma))
        field = np.maximum(field, weight * dbz)
    rng = np.random.default_rng(int(t_min * 10) + 17)
    field += rng.normal(0.0, 0.6, size=field.shape).astype(np.float32)
    return np.clip(field, 0.0, 75.0)


def render_frame_rgb(t_min: float, size: int = FRAME_SIZE) -> np.ndarray:
    rgb = dbz_to_rgb(reflectivity_field(t_min, size))
    image = Image.fromarray(rgb, mode="RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    # Range rings sit under the cores visually but are faint enough that the
    # >45 dBZ detector ignores them.
    cx = cy = size // 2
    for radius in (70, 140, 210):
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=(180, 210, 220, 28))
    draw.text((12, 12), f"NEXRAD  {t_min:05.1f} min   dBZ", fill=(190, 220, 230, 180))
    return np.asarray(image.convert("RGB"))


def render_frame_png(t_min: float, size: int = FRAME_SIZE) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    Image.fromarray(render_frame_rgb(t_min, size), mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def active_cores(t_min: float) -> list[dict]:
    """Analytic cores. The OpenCV seeder is cross-checked against these."""
    cores = []
    for cell in active_cells():
        state = cell_state(cell, t_min)
        if state is None:
            continue
        x, y, dbz = state
        sigma = float(cell["sigma"])
        cores.append(
            {
                "id": int(cell["id"]),
                "name": cell["name"],
                "cx": round(x, 4),
                "cy": round(y, 4),
                "rx": round(sigma * 1.6, 4),
                "ry": round(sigma * 1.35, 4),
                "dbz": round(dbz, 2),
                "vx_per_min": float(cell["vx"]),
                "vy_per_min": float(cell["vy"]),
            }
        )
    return cores


def write_radar_assets(frame_count: int = 37, minutes: float = 90.0) -> dict:
    """Write PNG frames, an MP4 loop, and a contact sheet. Returns paths."""
    from backend.config import RADAR_DIR

    frame_dir = RADAR_DIR / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    frames_bgr = []
    for index in range(frame_count):
        t_min = minutes * index / max(frame_count - 1, 1)
        rgb = render_frame_rgb(t_min)
        path = frame_dir / f"frame_{index:03d}.png"
        Image.fromarray(rgb, mode="RGB").save(path)
        paths.append(path)
        frames_bgr.append(rgb[:, :, ::-1].copy())

    mp4_path = RADAR_DIR / "nexrad_loop.mp4"
    mp4_error = None
    try:
        import cv2

        writer = cv2.VideoWriter(
            str(mp4_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            8.0,
            (FRAME_SIZE, FRAME_SIZE),
        )
        if not writer.isOpened():
            mp4_error = "VideoWriter did not open"
        else:
            for bgr in frames_bgr:
                writer.write(bgr)
            writer.release()
    except Exception as exc:  # pragma: no cover - codec availability
        mp4_error = f"{type(exc).__name__}: {exc}"

    sheet = Image.new("RGB", (FRAME_SIZE * 6, FRAME_SIZE * 2), (6, 8, 12))
    for index, path in enumerate(paths[:: max(len(paths) // 12, 1)][:12]):
        thumb = Image.open(path).resize((FRAME_SIZE, FRAME_SIZE))
        sheet.paste(thumb, ((index % 6) * FRAME_SIZE, (index // 6) * FRAME_SIZE))
    sheet_path = RADAR_DIR / "contact_sheet.png"
    sheet.save(sheet_path)

    polygons = {name: list(box) for name, box in settings.SUBCATCHMENT_POLYGONS.items()}
    return {
        "frames": [str(p) for p in paths],
        "mp4": str(mp4_path) if mp4_path.exists() else None,
        "mp4_error": mp4_error,
        "contact_sheet": str(sheet_path),
        "polygons": polygons,
    }
