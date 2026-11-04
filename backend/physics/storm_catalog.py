"""Forcing tapes the command center can switch.

DS-1482 stays the exact table the scorecard locks. The other tapes are
gauge-anchored hyetographs on the same four-basin plant. They are not
decoded NEXRAD volume scans and they are not the historical city's
sewer network.
"""

from __future__ import annotations

import numpy as np

from backend.config import settings
from backend.physics.design_storm import (
    RAIN_MG,
    STORM_CELLS,
    VOLUME_SCALE,
    _MMHR_PER_UNSCALED_MG,
    cell_state,
    dbz_to_mmhr,
)

STEPS = 18

# Newark Liberty, 1 Sep 2021, 8–9 p.m.: 3.24 in = 82.3 mm in that hour.
# Daily total at Newark was 8.41 in. Cornell / NRCC compilation.
IDA_HOUR_MM = 3.24 * 25.4

# Chicago, 2 Jul 2023, NWS Chicago public information statement.
# Daily gauges, not a 90-minute integral this plant is claiming to reproduce.
CHICAGO_BERWYN_IN = 8.96
CHICAGO_MIDWAY_IN = 4.68


def _mmhr_to_rain(mmhr: np.ndarray) -> np.ndarray:
    unscaled = np.asarray(mmhr, dtype=float) / _MMHR_PER_UNSCALED_MG
    return unscaled * VOLUME_SCALE


def _triangle(start: int, count: int, mean_mmhr: float) -> np.ndarray:
    raw = np.zeros(STEPS)
    for offset in range(count):
        index = start + offset
        if index >= STEPS:
            break
        x = offset / max(count - 1, 1)
        raw[index] = 1.0 - abs(2.0 * x - 1.0)
    window = raw[start : start + count]
    total = float(window.sum())
    if total <= 0:
        return raw
    raw[start : start + count] *= mean_mmhr * len(window) / total
    return raw


def _ida_rain() -> np.ndarray:
    """One Newark peak hour on Basin 4, lighter rain upstream."""
    su4 = _triangle(6, 12, IDA_HOUR_MM)
    mmhr = np.column_stack([su4 * 0.45, su4 * 0.55, su4 * 0.50, su4])
    return _mmhr_to_rain(mmhr)


def _chicago_rain() -> np.ndarray:
    """West-side burst, then the downstream basin. Peak is a cell, not the daily gauge."""
    west = _triangle(2, 9, 55.0)
    south = _triangle(7, 10, 70.0)
    mmhr = np.column_stack([west * 0.35, west, west * 0.4, south])
    return _mmhr_to_rain(mmhr)


def _ida_cells() -> tuple[dict, ...]:
    return (
        {
            "id": 0,
            "name": "newark-peak",
            "x0": 0.68,
            "y0": 0.74,
            "vx": 0.001,
            "vy": 0.0004,
            "sigma": 0.11,
            "peak_dbz": 58.0,
            "t0": 30.0,
            "t1": 90.0,
        },
    )


def _chicago_cells() -> tuple[dict, ...]:
    return (
        {
            "id": 0,
            "name": "west-side",
            "x0": 0.42,
            "y0": 0.42,
            "vx": 0.004,
            "vy": 0.005,
            "sigma": 0.10,
            "peak_dbz": 60.0,
            "t0": 10.0,
            "t1": 80.0,
        },
    )


_LIBRARY = {
    "ds-1482": {
        "title": "DS-1482 scorecard",
        "kind": "design-storm",
        "note": (
            "Calibrated design storm. The municipal float switch spills exactly "
            "14,820,000 gallons on this plant. Not a live radar feed."
        ),
    },
    "ida-2021-newark": {
        "title": "Ida remnants, Newark, 1 Sep 2021",
        "kind": "gauge-anchored",
        "note": (
            "Basin 4 carries Newark Liberty's published 3.24 in hour (8–9 p.m., "
            "82.3 mm). The daily gauge was 8.41 in. This is that hour shaped onto "
            "the scaled interceptor, not a KOKX volume scan and not Newark's sewer."
        ),
    },
    "chicago-2023-0702": {
        "title": "Chicago west side, 2 Jul 2023",
        "kind": "gauge-anchored",
        "note": (
            f"Cell track for the NWS flash-flood day. Berwyn reported {CHICAGO_BERWYN_IN} in "
            f"and Midway {CHICAGO_MIDWAY_IN} in for the calendar day. The tape is a 90-minute "
            "cell on this plant, not MWRD's network and not those daily totals."
        ),
    },
    "double-lock": {
        "title": "Double-lock fault · DS-1482 × 2.2 (OR1=5%, OR2=90%)",
        "kind": "compound-fault",
        "note": (
            "DS-1482 scaled by 2.2× with OR1 locked at 5% and OR2 locked at 90% from minute 20. "
            "All four static laws overflow (4.36M–24.30M gal); unaided muse-wonder-1.0 "
            "(resp_6ae9f0ee5b7721d9ff6a4da4, u=[0.05, 0.90, 0.12, 0.90]) holds 0.0 gal."
        ),
    },
}


_state: dict = {"id": "ds-1482", "rain": None, "cells": None, "kind": "design-storm"}


def list_storms() -> list[dict]:
    rows = []
    for key, meta in _LIBRARY.items():
        rows.append({"id": key, "title": meta["title"], "kind": meta["kind"], "note": meta["note"]})
    if _state["id"] == "custom-cell":
        rows.append(
            {
                "id": "custom-cell",
                "title": "Dropped 60 dBZ cell",
                "kind": "custom-cell",
                "note": _state.get("note", ""),
            }
        )
    return rows


def current() -> dict:
    meta = _LIBRARY.get(_state["id"], {})
    return {
        "id": _state["id"],
        "title": meta.get("title", "Dropped 60 dBZ cell"),
        "kind": _state.get("kind") or meta.get("kind", "custom-cell"),
        "note": _state.get("note") or meta.get("note", ""),
    }


def active_rain() -> np.ndarray:
    rain = _state["rain"]
    if rain is None:
        return RAIN_MG
    return rain


def active_cells() -> tuple[dict, ...] | list[dict]:
    if _state["cells"] is None:
        return STORM_CELLS
    return _state["cells"]


def _activate(storm_id: str, fallback_rain, fallback_cells) -> dict:
    from backend.physics.nexrad_mosaic import load_event

    event = load_event(storm_id)
    if event is None:
        _state.update(id=storm_id, rain=fallback_rain, cells=fallback_cells, kind="gauge-anchored", note=None)
        return current()
    _state.update(
        id=storm_id,
        rain=event["rain"],
        cells=[],
        kind="nexrad-mosaic",
        note=event["note"],
    )
    return current()


def select(storm_id: str) -> dict:
    if storm_id == "ds-1482":
        _state.update(id="ds-1482", rain=None, cells=None, kind="design-storm", note=None)
        return current()
    if storm_id == "ida-2021-newark":
        return _activate(storm_id, _ida_rain(), _ida_cells())
    if storm_id == "chicago-2023-0702":
        return _activate(storm_id, _chicago_rain(), _chicago_cells())
    if storm_id == "double-lock":
        _state.update(
            id="double-lock",
            rain=np.array(RAIN_MG, dtype=float) * 2.2,
            cells=None,
            kind="compound-fault",
            note=_LIBRARY["double-lock"]["note"],
        )
        return current()
    raise KeyError(storm_id)


def _coverage_weight(x: float, y: float, sigma: float, rect: tuple[float, float, float, float]) -> float:
    cx = (rect[0] + rect[2]) / 2.0
    cy = (rect[1] + rect[3]) / 2.0
    return float(np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2.0 * sigma * sigma)))


def rain_from_cells(cells: list[dict]) -> np.ndarray:
    """Map cell kinematics through the same Z-R the design storm uses."""
    rain = np.zeros((STEPS, 4))
    rects = [settings.SUBCATCHMENT_POLYGONS[name] for name in settings.BASIN_IDS]
    for step in range(STEPS):
        t_min = step * settings.STEP_MINUTES
        for cell in cells:
            state = cell_state(cell, t_min)
            if state is None:
                continue
            x, y, dbz = state
            rate = dbz_to_mmhr(dbz)
            sigma = float(cell["sigma"])
            for index, rect in enumerate(rects):
                mmhr = rate * _coverage_weight(x, y, sigma, rect)
                rain[step, index] += mmhr / _MMHR_PER_UNSCALED_MG[index] * VOLUME_SCALE
    return rain


def spawn_cell(x: float, y: float, dbz: float = 60.0) -> dict:
    """Replace the tape with one convective cell dropped on the scope."""
    x = float(np.clip(x, 0.02, 0.98))
    y = float(np.clip(y, 0.02, 0.98))
    dbz = float(np.clip(dbz, 45.0, 65.0))
    cell = {
        "id": 0,
        "name": "dropped-cell",
        "x0": x,
        "y0": y,
        "vx": 0.003,
        "vy": 0.002,
        "sigma": 0.09,
        "peak_dbz": dbz,
        "t0": 0.0,
        "t1": 90.0,
    }
    note = (
        f"A {dbz:.0f} dBZ cell dropped at ({x:.2f}, {y:.2f}). "
        "Runoff uses the Marshall-Palmer Z-R on this plant. Not a NOAA volume scan."
    )
    _state.update(id="custom-cell", rain=rain_from_cells([cell]), cells=[cell], kind="custom-cell", note=note)
    return current()
