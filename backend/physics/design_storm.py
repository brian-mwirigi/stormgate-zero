"""Design storm DS-1482 for the four-basin interceptor.

Depths are invariant to a uniform scaling of storage, orifice capacity,
plant capacity, dry-weather flow, and runoff. The scale below is the
value that makes the municipal local-rule weir integrate to
14,820,000 gallons on this hydrograph. StormGate-Zero's pre-drain law
is unchanged by that scale and stays off the weir.
"""

from __future__ import annotations

import numpy as np

# Local-rule spill of the unscaled network, million gallons, rain-scale 1.15.
_UNSCALED_LOCAL_CSO_MG = 4.598522
VOLUME_SCALE = 14.82 / _UNSCALED_LOCAL_CSO_MG

_RAIN_STEP_MG = np.array(
    [
        [0.05, 0.03, 0.02, 0.02],
        [0.18, 0.06, 0.04, 0.02],
        [0.32, 0.14, 0.07, 0.03],
        [0.28, 0.22, 0.10, 0.03],
        [0.16, 0.20, 0.12, 0.04],
        [0.08, 0.12, 0.08, 0.05],
        [0.04, 0.06, 0.04, 0.08],
        [0.02, 0.03, 0.02, 0.15],
        [0.02, 0.02, 0.02, 0.45],
        [0.01, 0.01, 0.01, 0.90],
        [0.01, 0.01, 0.01, 1.25],
        [0.01, 0.01, 0.01, 1.15],
        [0.01, 0.01, 0.01, 0.70],
        [0.01, 0.01, 0.01, 0.30],
        [0.01, 0.01, 0.01, 0.12],
        [0.01, 0.01, 0.01, 0.05],
        [0.01, 0.01, 0.01, 0.02],
        [0.01, 0.01, 0.01, 0.02],
    ],
    dtype=float,
)
_RAIN_STEP_MG[:, 3] *= 1.15

# Million gallons of runoff arriving during each 5-minute step.
RAIN_MG = _RAIN_STEP_MG * VOLUME_SCALE

VMAX_MG = np.array([5.8, 4.9, 5.3, 7.4]) * VOLUME_SCALE
QFULL_MG = np.array([1.35, 1.15, 1.25, 3.4]) * VOLUME_SCALE
DWF_MG = np.array([0.015, 0.010, 0.012, 0.006]) * VOLUME_SCALE
WWTP_MG_PER_STEP = 1.90 * VOLUME_SCALE
INIT_FRACTION = np.array([0.72, 0.64, 0.68, 0.81])

# Feedback-law thresholds, scaled with storage so the depth path is identical.
PREDRAIN_RAIN_MG = 0.40 * VOLUME_SCALE
GAP_CAP_MG = 1.5 * VOLUME_SCALE
SHED_DEADBAND_MG = 0.02 * VOLUME_SCALE
CRACK_RELEASE_MG = 0.05 * VOLUME_SCALE
MIN_RELEASE_MG = 0.02 * VOLUME_SCALE

# Two convective cores. Positions are normalized radar coordinates.
# Core A crosses Basin 1 early; core B arrives over Basin 4 near minute 55.
STORM_CELLS = (
    {
        "id": 0,
        "name": "core-alpha",
        "x0": 0.20,
        "y0": 0.18,
        "vx": 0.0072,  # per minute
        "vy": 0.0064,
        "sigma": 0.085,
        "peak_dbz": 52.0,
        "t0": 0.0,
        "t1": 48.0,
    },
    {
        "id": 1,
        "name": "core-bravo",
        "x0": 0.16,
        "y0": 0.30,
        "vx": 0.0094,
        "vy": 0.0082,
        "sigma": 0.095,
        "peak_dbz": 57.0,
        "t0": 8.0,
        "t1": 78.0,
    },
)


# Unscaled million-gallons-per-step that we treat as the reference hyetograph
# intensity. These are the design-storm peaks before VOLUME_SCALE, paired with
# the reflectivity the radar paints for the same cores.
_MMHR_PER_UNSCALED_MG = np.array([150.0, 180.0, 230.0, 43.0])


def mg_step_to_mmhr(rain_mg: np.ndarray) -> np.ndarray:
    """Map a runoff step in million gallons back to an equivalent mm/hr hyetograph."""
    unscaled = np.asarray(rain_mg, dtype=float) / VOLUME_SCALE
    return np.maximum(unscaled * _MMHR_PER_UNSCALED_MG, 0.0)


def dbz_to_mmhr(dbz: float) -> float:
    """Marshall-Palmer Z-R, lightly capped so a 55 dBZ core is a cloudburst."""
    if dbz < 18.0:
        return 0.0
    z_value = 10 ** (dbz / 10.0)
    rate = (z_value / 200.0) ** (1.0 / 1.6)
    return float(min(rate, 85.0))


def cell_state(cell: dict, t_min: float) -> tuple[float, float, float] | None:
    """Return (x, y, dbz) for a cell at t minutes, or None if it has decayed."""
    if t_min < cell["t0"] or t_min > cell["t1"]:
        return None
    age = (t_min - cell["t0"]) / max(cell["t1"] - cell["t0"], 1.0)
    life = float(np.sin(np.pi * np.clip(age, 0.0, 1.0)) ** 0.85)
    # The core is already on scope at the first frame so Frame-0 box seeding
    # has a >45 dBZ target. The sine envelope would otherwise open at zero.
    if age < 0.08:
        life = max(life, 0.72)
    if life < 0.04:
        return None
    x = cell["x0"] + cell["vx"] * (t_min - cell["t0"])
    y = cell["y0"] + cell["vy"] * (t_min - cell["t0"])
    return float(x), float(y), float(cell["peak_dbz"] * (0.55 + 0.45 * life))
