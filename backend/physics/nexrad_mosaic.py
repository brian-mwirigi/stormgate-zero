"""Real IEM N0Q national-mosaic frames for two historical hours.

The pictures are the Iowa Environmental Mesonet archive of the NWS N0Q
composite, not a drawing. Rainfall is Marshall-Palmer on a palette reading
of those pixels inside a 1.2-degree window. It is not a Level-II volume
scan and not the city's sewer sheds. The four basins are quadrants of
that window: northwest, southwest, northeast, southeast.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

from backend.config import ROOT
from backend.physics.design_storm import VOLUME_SCALE, _MMHR_PER_UNSCALED_MG, dbz_to_mmhr

# Upper-left of the IEM 4326 N0Q mosaic, from the .wld next to the PNG.
ORIGIN_LON = -126.0
ORIGIN_LAT = 50.0
DEG_PER_PX = 0.005

OUT_DIR = ROOT / "traces" / "nexrad"
RAW_DIR = ROOT / "data" / "radar" / "nexrad"

# Palette index anchors read off the 1 Sep 2021 / 2 Jul 2023 mosaics.
# Index 150 is gold (255, 196, 0), treated as 45 dBZ. Index 170 is red, 55 dBZ.
_INDEX = np.array([96, 110, 128, 138, 150, 160, 170, 180, 190, 210], dtype=float)
_DBZ = np.array([10, 18, 28, 35, 45, 50, 55, 60, 65, 72], dtype=float)

EVENTS = {
    "ida-2021-newark": {
        "title": "Ida remnants, Newark, 1 Sep 2021",
        "center": (40.69, -74.17),
        "stamps": [
            "202109012330",
            "202109012345",
            "202109020000",
            "202109020015",
            "202109020030",
            "202109020045",
        ],
        "note": (
            "IEM N0Q mosaic over Newark, 23:30–00:45 UTC 1–2 Sep 2021 "
            "(the 8–9 p.m. local hour when Newark recorded 3.24 in). "
            "Quadrant rainfall is Marshall-Palmer on the mosaic palette. "
            "Not a KOKX Level-II volume and not Newark's sewer."
        ),
    },
    "chicago-2023-0702": {
        "title": "Chicago west side, 2 Jul 2023",
        "center": (41.85, -87.75),
        "stamps": [
            "202307022100",
            "202307022130",
            "202307022200",
            "202307022230",
            "202307022300",
            "202307022330",
        ],
        "note": (
            "IEM N0Q mosaic over the west side of Chicago, 21:00–23:30 UTC "
            "on 2 Jul 2023 (4:00–6:30 p.m. CDT). NWS daily gauges that day "
            "include Berwyn 8.96 in and Midway 4.68 in. Quadrant rainfall is "
            "Marshall-Palmer on the mosaic palette, not MWRD's network."
        ),
    },
}


def _url(stamp: str) -> str:
    day = f"{stamp[0:4]}/{stamp[4:6]}/{stamp[6:8]}"
    return f"https://mesonet.agron.iastate.edu/archive/data/{day}/GIS/uscomp/n0q_{stamp}.png"


def _download(stamp: str) -> Path | None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"n0q_{stamp}.png"
    if path.exists() and path.stat().st_size > 100_000:
        return path
    try:
        urllib.request.urlretrieve(_url(stamp), path)
    except Exception:
        if path.exists():
            path.unlink()
        return None
    if path.stat().st_size < 100_000:
        path.unlink(missing_ok=True)
        return None
    return path


def index_to_dbz(index: np.ndarray) -> np.ndarray:
    values = np.interp(index.astype(float), _INDEX, _DBZ)
    return np.where(index < 96, 0.0, values).astype(np.float32)


def _crop(image: Image.Image, lat: float, lon: float) -> Image.Image:
    col = int(round((lon - ORIGIN_LON) / DEG_PER_PX))
    row = int(round((ORIGIN_LAT - lat) / DEG_PER_PX))
    return image.crop((col - 120, row - 120, col + 120, row + 120))


def _quadrant_mmhr(dbz: np.ndarray) -> list[float]:
    height, width = dbz.shape
    mid_y, mid_x = height // 2, width // 2
    quads = [
        dbz[:mid_y, :mid_x],
        dbz[mid_y:, :mid_x],
        dbz[:mid_y, mid_x:],
        dbz[mid_y:, mid_x:],
    ]
    rates = []
    for quad in quads:
        flat = quad.ravel()
        echoed = flat[flat >= 18.0]
        if len(echoed) == 0:
            rates.append(0.0)
            continue
        rates.append(float(np.mean([dbz_to_mmhr(float(v)) for v in echoed])))
    return rates


def _repeat_to_18(rows: list[list[float]]) -> np.ndarray:
    if not rows:
        return np.zeros((18, 4))
    block = max(1, 18 // len(rows))
    tiled = []
    for row in rows:
        tiled.extend([row] * block)
    while len(tiled) < 18:
        tiled.append(rows[-1])
    mmhr = np.asarray(tiled[:18], dtype=float)
    return mmhr / _MMHR_PER_UNSCALED_MG * VOLUME_SCALE


def build_event(storm_id: str) -> dict:
    """Download the mosaics, crop them, and write the rain the plant will use."""
    spec = EVENTS[storm_id]
    lat, lon = spec["center"]
    folder = OUT_DIR / storm_id
    folder.mkdir(parents=True, exist_ok=True)
    rates = []
    frames = []
    for stamp in spec["stamps"]:
        downloaded = _download(stamp)
        if downloaded is None:
            continue
        index = len(frames)
        image = Image.open(downloaded)
        crop = _crop(image, lat, lon)
        dbz = index_to_dbz(np.asarray(crop))
        rates.append(_quadrant_mmhr(dbz))
        rgb = crop.convert("RGB").resize((480, 480), Image.Resampling.NEAREST)
        frame_path = folder / f"frame_{index:02d}.png"
        rgb.save(frame_path, format="PNG")
        frames.append({"stamp": stamp, "url": _url(stamp), "file": frame_path.name, "mmhr": [round(v, 2) for v in rates[-1]]})
    rain = _repeat_to_18(rates)
    meta = {
        "id": storm_id,
        "title": spec["title"],
        "note": spec["note"],
        "center_lat": lat,
        "center_lon": lon,
        "frames": frames,
        "product": "IEM N0Q national mosaic",
    }
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    np.save(folder / "rain.npy", rain)
    return meta


def load_event(storm_id: str) -> dict | None:
    folder = OUT_DIR / storm_id
    rain_path = folder / "rain.npy"
    meta_path = folder / "meta.json"
    if not rain_path.exists() or not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["rain"] = np.load(rain_path)
    return meta


def frame_png(storm_id: str, step_index: int) -> bytes | None:
    event = load_event(storm_id)
    if event is None:
        return None
    frames = event.get("frames") or []
    if not frames:
        return None
    slot = min(int(step_index) * len(frames) // 37, len(frames) - 1)
    path = OUT_DIR / storm_id / frames[slot]["file"]
    if not path.exists():
        return None
    return path.read_bytes()
