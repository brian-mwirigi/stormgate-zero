"""One PySWMM dynamic-wave pass over the committed orifice series.

The live MPC loop stays on level-pool continuity so twelve clones finish
inside a control step. This runner is the end-of-episode check: the EPA
engine integrates the same gate schedule on a short interceptor and
reports conduit depth above the crown. It is not a second copy of the
14,820,000 gallon scorecard.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from backend.config import SWMM_DIR

# Cubic feet per million gallons, and psi per foot of water.
CF_PER_MG = 133_680.555
PSI_PER_FT = 0.4335
M_PER_FT = 0.3048
PIPE_DIAMETER_FT = {"C1": 6.0, "C2": 5.0, "C3": 5.0}


def _cfs(mg_per_step: float) -> float:
    """Million gallons over a 5-minute step, as a steady cubic-feet-per-second."""
    return float(mg_per_step) * CF_PER_MG / 300.0


def write_wave_inp(path: Path, rain_mg: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rain = np.asarray(rain_mg, dtype=float)
    if rain.ndim != 2 or rain.shape[1] != 4:
        raise ValueError("rain_mg must have shape (steps, 4)")
    series_lines = []
    for name_index, name in enumerate(("TS1", "TS2", "TS3", "TS4")):
        for step, row in enumerate(rain):
            minute = step * 5
            hour, mins = divmod(minute, 60)
            series_lines.append(
                f"{name:<8} 07/16/2026  {18 + hour:02d}:{mins:02d}  {_cfs(row[name_index]):.4f}"
            )
    # Constant-area storages on the order of the level-pool volumes.
    body = f"""[TITLE]
;; StormGate-Zero dynamic-wave verification

[OPTIONS]
FLOW_UNITS          CFS
FLOW_ROUTING        DYNWAVE
LINK_OFFSETS        DEPTH
ALLOW_PONDING       YES
START_DATE          07/16/2026
START_TIME          18:00:00
REPORT_START_DATE   07/16/2026
REPORT_START_TIME   18:00:00
END_DATE            07/16/2026
END_TIME            19:30:00
REPORT_STEP         00:05:00
WET_STEP            00:05:00
DRY_STEP            00:05:00
ROUTING_STEP        00:00:20
RULE_STEP           00:00:20

[JUNCTIONS]
;;Name           Elev   Ymax  Y0  Ysur  Apond
J1               10     8     0   20    0
J2               10     8     0   20    0
J3               10     8     0   20    0
J4               8      10    0   20    0

[OUTFALLS]
;;Name           Elev   Type      Stage  Gated
WWTP             6      FREE               NO
RIVER            6      FREE               NO

[STORAGE]
;;Name           Elev   Ymax  Y0  Type        A1      A2  A0
SU1              14     12    8   FUNCTIONAL  180000  0   0
SU2              14     12    7   FUNCTIONAL  150000  0   0
SU3              14     12    8   FUNCTIONAL  160000  0   0
SU4              12     14    10  FUNCTIONAL  250000  0   0

[ORIFICES]
;;Name  From  To    Type  Offset  Qcoeff  Gated  CloseTime
OR1     SU1   J1    SIDE  0       0.65    NO     0
OR2     SU2   J2    SIDE  0       0.65    NO     0
OR3     SU3   J3    SIDE  0       0.65    NO     0
OR4     SU4   WWTP  SIDE  0       0.70    NO     0

[CONDUITS]
;;Name  From  To  Length  N      Z1  Z2  Q0
C1      J1    J4  1400    0.013  0   0   0
C2      J2    J4  900     0.013  0   0   0
C3      J3    J4  1100    0.013  0   0   0

[XSECTIONS]
;;Link  Shape        Geom1  Geom2  Geom3  Geom4
OR1     RECT_CLOSED  4      3      0      0
OR2     RECT_CLOSED  3.5    3      0      0
OR3     RECT_CLOSED  3.5    3      0      0
OR4     RECT_CLOSED  6      4      0      0
C1      CIRCULAR     6      0      0      0
C2      CIRCULAR     5      0      0      0
C3      CIRCULAR     5      0      0      0

[INFLOWS]
;;Node  Parameter  TimeSeries  Type  Mfactor  Sfactor  Baseline  Pattern
SU1     FLOW       TS1         FLOW  1.0      1.0
SU2     FLOW       TS2         FLOW  1.0      1.0
SU3     FLOW       TS3         FLOW  1.0      1.0
SU4     FLOW       TS4         FLOW  1.0      1.0

[TIMESERIES]
;;Name   Date        Time   Value
{chr(10).join(series_lines)}

[REPORT]
INPUT      NO
NODES ALL
LINKS ALL
"""
    path.write_text(body, encoding="utf-8")
    return path


def verify_dynamic_wave(orifice_series: list[list[float]], rain_mg: np.ndarray) -> dict:
    """Run SWMM5. Returns surcharge head. Never raises."""
    try:
        from pyswmm import Links, Nodes, Simulation
    except Exception as exc:
        return {"ok": False, "engine": "pyswmm", "error": f"{type(exc).__name__}: {exc}"}
    path = SWMM_DIR / "wave_verify.inp"
    try:
        write_wave_inp(path, rain_mg)
        series = [list(map(float, row)) for row in orifice_series]
        max_link = {name: 0.0 for name in PIPE_DIAMETER_FT}
        max_node = {}
        max_surcharge = {}
        with Simulation(str(path)) as sim:
            links = Links(sim)
            nodes = Nodes(sim)
            for _step in sim:
                elapsed = (sim.current_time - sim.start_time).total_seconds()
                bucket = min(int(elapsed // 300), max(len(series) - 1, 0))
                if series:
                    for name, value in zip(("OR1", "OR2", "OR3", "OR4"), series[bucket]):
                        if name in links:
                            links[name].target_setting = float(value)
                for name in PIPE_DIAMETER_FT:
                    if name in links:
                        max_link[name] = max(max_link[name], float(links[name].depth))
                for name in ("SU1", "SU2", "SU3", "SU4", "J1", "J2", "J3", "J4"):
                    if name in nodes:
                        node = nodes[name]
                        depth = float(node.depth)
                        max_node[name] = max(max_node.get(name, 0.0), depth)
                        full = float(getattr(node, "full_depth", 0.0) or 0.0)
                        max_surcharge[name] = max(max_surcharge.get(name, 0.0), max(0.0, depth - full))
        pipes = []
        worst_ft = 0.0
        worst_name = ""
        for name, full in PIPE_DIAMETER_FT.items():
            depth = max_link[name]
            head_ft = max(0.0, depth - full)
            pipes.append(
                {
                    "link": name,
                    "max_depth_ft": round(depth, 3),
                    "diameter_ft": full,
                    "fill_ratio": round(depth / full, 3) if full else 0.0,
                    "surcharge_ft": round(head_ft, 3),
                    "surcharge_m": round(head_ft * M_PER_FT, 3),
                    "surcharge_psi": round(head_ft * PSI_PER_FT, 3),
                }
            )
        for name, head_ft in max_surcharge.items():
            if head_ft >= worst_ft:
                worst_ft = head_ft
                worst_name = name
        return {
            "ok": True,
            "engine": "pyswmm-dynwave",
            "steps_commanded": len(series),
            "worst_link": worst_name,
            "worst_surcharge_ft": round(worst_ft, 3),
            "worst_surcharge_m": round(worst_ft * M_PER_FT, 3),
            "worst_surcharge_psi": round(worst_ft * PSI_PER_FT, 3),
            "pipes": pipes,
            "max_node_depth_ft": {key: round(value, 3) for key, value in max_node.items()},
            "max_node_surcharge_ft": {key: round(value, 3) for key, value in max_surcharge.items()},
            "note": "SWMM5 dynamic wave on the verification interceptor. Not the level-pool gallon scorecard.",
        }
    except Exception as exc:
        return {"ok": False, "engine": "pyswmm", "error": f"{type(exc).__name__}: {exc}"}
