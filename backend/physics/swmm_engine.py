"""Dual St. Venant storage-routing engine for the interceptor.

Each storage unit is integrated with level-pool continuity, the same
storage routing SWMM5 applies at a storage node:

    dV/dt = I_runoff + I_upstream - Q_orifice - Q_weir

Orifice discharge follows the submerged-orifice relation
Q = u * Qfull * sqrt(h/H). The river weir at SU4 and the street-flood
weirs at SU1–SU3 are sharp-crested overflows above full depth. Releases
from SU1–SU3 enter SU4 in the same step through a short interceptor
(travel time is inside the 5-minute step). SU4's outflow is bound by
the wastewater treatment plant capacity.

A dynamic-wave SWMM5 run of the same .inp is attempted when PySWMM and
the EPA engine are installed. MPC fan-out uses this level-pool reduction
because a 60-minute clone has to finish inside a control step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from backend.physics.design_storm import (
    CRACK_RELEASE_MG,
    DWF_MG,
    GAP_CAP_MG,
    INIT_FRACTION,
    MIN_RELEASE_MG,
    PREDRAIN_RAIN_MG,
    QFULL_MG,
    RAIN_MG,
    SHED_DEADBAND_MG,
    VMAX_MG,
    WWTP_MG_PER_STEP,
)

MG_TO_GAL = 1_000_000.0
N_BASINS = 4


def _as_u(values) -> np.ndarray:
    u = np.asarray(values, dtype=float).reshape(4)
    return np.clip(u, 0.0, 1.0)


@dataclass
class StepResult:
    depth: list[float]
    orifice: list[float]
    cso_gallons: float
    street_gallons: float
    wwtp_gallons: float
    inflow_mg: list[float]


@dataclass
class RolloutScore:
    name: str
    total_cso_overflow_gallons: float
    max_basin_fill_pct: float
    street_flooding_gallons: float
    downstream_wwtp_utilization_pct: float
    depth_trace: list[list[float]]
    action_trace: list[list[float]]
    first_action: list[float]

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "total_cso_overflow_gallons": round(self.total_cso_overflow_gallons, 1),
            "max_basin_fill_pct": round(self.max_basin_fill_pct, 4),
            "street_flooding_gallons": round(self.street_flooding_gallons, 1),
            "downstream_wwtp_utilization_pct": round(self.downstream_wwtp_utilization_pct, 2),
            "first_action": [round(v, 4) for v in self.first_action],
        }


@dataclass
class Watershed:
    """One interceptor. `volume` is million gallons in SU1..SU4."""

    name: str
    volume: np.ndarray = field(default_factory=lambda: VMAX_MG * INIT_FRACTION)
    cso_mg: float = 0.0
    street_mg: float = 0.0
    wwtp_mg: float = 0.0
    steps: int = 0
    depth_history: list[list[float]] = field(default_factory=list)
    orifice_history: list[list[float]] = field(default_factory=list)

    def clone(self, name: str | None = None) -> Watershed:
        twin = Watershed(name or self.name)
        twin.volume = self.volume.copy()
        twin.cso_mg = self.cso_mg
        twin.street_mg = self.street_mg
        twin.wwtp_mg = self.wwtp_mg
        twin.steps = self.steps
        return twin

    @property
    def depth(self) -> np.ndarray:
        return np.clip(self.volume / VMAX_MG, 0.0, 1.5)

    def step(self, orifice: np.ndarray, rain_mg: np.ndarray, jammed: dict[int, float] | None = None) -> StepResult:
        """Advance one 5-minute hydraulic step. `jammed` locks orifice indices."""
        u = _as_u(orifice)
        if jammed:
            for index, locked in jammed.items():
                u[int(index)] = float(np.clip(locked, 0.0, 1.0))
        rain = np.asarray(rain_mg, dtype=float).reshape(4)
        inflow = rain + DWF_MG
        depth = self.depth
        q_cap = u * QFULL_MG * np.sqrt(np.maximum(depth, 1e-9))

        available = self.volume[:3] + inflow[:3]
        release = np.minimum(q_cap[:3], np.maximum(available, 0.0))
        street = np.maximum(available - release - VMAX_MG[:3], 0.0)
        self.volume[:3] = np.maximum(available - release - street, 0.0)

        available4 = float(self.volume[3] + inflow[3] + release.sum())
        release4 = min(float(q_cap[3]), available4, float(WWTP_MG_PER_STEP))
        overflow4 = max(0.0, available4 - release4 - float(VMAX_MG[3]))
        self.volume[3] = max(available4 - release4 - overflow4, 0.0)

        self.cso_mg += overflow4
        self.street_mg += float(street.sum())
        self.wwtp_mg += release4
        self.steps += 1
        depth_now = [float(v) for v in self.depth]
        orifice_now = [float(v) for v in u]
        self.depth_history.append(depth_now)
        self.orifice_history.append(orifice_now)
        return StepResult(
            depth=depth_now,
            orifice=orifice_now,
            cso_gallons=overflow4 * MG_TO_GAL,
            street_gallons=float(street.sum()) * MG_TO_GAL,
            wwtp_gallons=release4 * MG_TO_GAL,
            inflow_mg=[float(v) for v in inflow],
        )


def policy_open(depth: np.ndarray, rain_mg: np.ndarray, jammed: dict[int, float] | None = None) -> np.ndarray:
    """Gates failed open. Upstream storage is passed straight downstream."""
    u = np.ones(4)
    if jammed:
        for index, locked in jammed.items():
            u[int(index)] = float(locked)
    return _as_u(u)


def policy_local(depth: np.ndarray, rain_mg: np.ndarray, jammed: dict[int, float] | None = None) -> np.ndarray:
    """Municipal float rules: upstream pass-through, SU4 stays shut until the crown."""
    u4 = 1.0 if float(depth[3]) >= 0.96 else 0.02
    u = np.array([1.0, 1.0, 1.0, u4], dtype=float)
    if jammed:
        for index, locked in jammed.items():
            u[int(index)] = float(locked)
    return _as_u(u)


def policy_stormgate(depth: np.ndarray, rain_mg: np.ndarray, jammed: dict[int, float] | None = None) -> np.ndarray:
    """Pre-drain SU4 toward 12%, hold upstream near 86%, then ride a 91% crest.

    A jammed orifice replaces the computed setting after the law runs, and
    the downstream target is lowered so the plant keeps spare room for the
    water the jammed gate can no longer hold back.
    """
    depth = np.asarray(depth, dtype=float)
    rain_mg = np.asarray(rain_mg, dtype=float)
    jam = jammed or {}
    u = np.empty(4)
    for i in range(3):
        q_cap = float(QFULL_MG[i] * np.sqrt(max(float(depth[i]), 0.05)))
        shed = (float(depth[i]) - 0.86) * float(VMAX_MG[i])
        if shed <= SHED_DEADBAND_MG:
            u[i] = 0.04
        else:
            u[i] = float(np.clip(shed / max(q_cap, 1e-9), 0.04, 1.0))
    jammed_now = 1 in jam or "OR2" in jam
    target = 0.80 if jammed_now else 0.91
    q_cap4 = float(QFULL_MG[3] * np.sqrt(max(float(depth[3]), 0.05)))
    raining = float(rain_mg[3]) >= PREDRAIN_RAIN_MG
    if (not jammed_now) and (not raining) and float(depth[3]) > 0.125:
        release = min(
            q_cap4,
            WWTP_MG_PER_STEP,
            max(CRACK_RELEASE_MG, (float(depth[3]) - 0.12) * float(VMAX_MG[3])),
        )
    elif (not jammed_now) and float(depth[3]) < 0.115:
        release = min(float(rain_mg[3]) * 0.4, CRACK_RELEASE_MG)
    else:
        gap = (target - float(depth[3])) * float(VMAX_MG[3])
        release = float(rain_mg[3]) - max(min(gap, GAP_CAP_MG), -WWTP_MG_PER_STEP)
        if float(depth[3]) >= target - 0.01:
            release = min(WWTP_MG_PER_STEP, q_cap4)
        release = min(max(release, MIN_RELEASE_MG), WWTP_MG_PER_STEP, q_cap4)
    u[3] = float(np.clip(release / max(q_cap4, 1e-9), 0.0, 1.0))
    if jammed_now:
        u[1] = float(jam.get(1, jam.get("OR2", 0.50)))
    return _as_u(u)


POLICIES = {
    "uncontrolled": policy_open,
    "local": policy_local,
    "stormgate": policy_stormgate,
}


def _apply_jam(u: np.ndarray, jammed: dict[int, float] | None) -> np.ndarray:
    u = _as_u(u)
    if not jammed:
        return u
    for index, locked in jammed.items():
        if isinstance(index, str):
            continue
        u[int(index)] = float(np.clip(locked, 0.0, 1.0))
    return u


def run_parallel_lookahead_rollouts(
    current_volume: np.ndarray,
    candidate_actions: list[tuple[str, np.ndarray]],
    radar_forecast_mg: np.ndarray,
    jammed_valves: dict[int, float] | None = None,
) -> list[RolloutScore]:
    """Score each candidate orifice trajectory over the forecast horizon.

    `candidate_actions` entries are (name, array[H, 4]) with u in [0, 1].
    Jammed valves overwrite the corresponding column before the clone runs.
    """
    forecast = np.asarray(radar_forecast_mg, dtype=float)
    if forecast.ndim != 2 or forecast.shape[1] != 4:
        raise ValueError("radar_forecast_mg must have shape (steps, 4)")
    scores: list[RolloutScore] = []
    for name, actions in candidate_actions:
        plan = np.asarray(actions, dtype=float)
        if plan.ndim != 2 or plan.shape[1] != 4:
            raise ValueError(f"{name}: actions must have shape (H, 4)")
        horizon = min(len(plan), len(forecast))
        clone = Watershed(name)
        clone.volume = np.array(current_volume, dtype=float).copy()
        depths: list[list[float]] = []
        applied: list[list[float]] = []
        cso = street = wwtp = 0.0
        for t in range(horizon):
            u = _apply_jam(plan[t], jammed_valves)
            result = clone.step(u, forecast[t], jammed=None)
            # Jam already written into u; step() must not double-apply.
            depths.append(result.depth)
            applied.append(result.orifice)
            cso += result.cso_gallons
            street += result.street_gallons
            wwtp += result.wwtp_gallons
        cap = WWTP_MG_PER_STEP * MG_TO_GAL * max(horizon, 1)
        peak = max((max(row) for row in depths), default=0.0)
        scores.append(
            RolloutScore(
                name=name,
                total_cso_overflow_gallons=cso,
                max_basin_fill_pct=float(peak),
                street_flooding_gallons=street,
                downstream_wwtp_utilization_pct=100.0 * wwtp / cap if cap else 0.0,
                depth_trace=depths,
                action_trace=applied,
                first_action=applied[0] if applied else [0.0, 0.0, 0.0, 0.0],
            )
        )
    return scores


def feedback_trajectory(
    volume: np.ndarray,
    forecast_mg: np.ndarray,
    policy_name: str,
    jammed: dict[int, float] | None = None,
) -> np.ndarray:
    """Open-loop recording of a feedback law along the forecast. Shape (H, 4)."""
    policy = POLICIES[policy_name]
    clone = Watershed(policy_name)
    clone.volume = np.array(volume, dtype=float).copy()
    actions = []
    for t in range(len(forecast_mg)):
        u = policy(clone.depth, forecast_mg[t], jammed)
        actions.append(u.copy())
        clone.step(u, forecast_mg[t])
    return np.vstack(actions)


def constant_trajectory(u: list[float], horizon: int, jammed: dict[int, float] | None = None) -> np.ndarray:
    plan = np.tile(_as_u(u), (horizon, 1))
    if jammed:
        for index, locked in jammed.items():
            if isinstance(index, str):
                continue
            plan[:, int(index)] = float(locked)
    return plan


def run_episode(policy_name: str, jammed_at: int | None = None, lock: float = 0.50) -> dict:
    """Full 90-minute design storm. Used by the benchmark and the tests."""
    plant = Watershed(policy_name)
    policy = POLICIES[policy_name]
    for k in range(len(RAIN_MG)):
        jammed = {1: lock} if jammed_at is not None and k >= jammed_at else None
        u = policy(plant.depth, RAIN_MG[k], jammed)
        plant.step(u, RAIN_MG[k])
    depths = np.array(plant.depth_history)
    return {
        "policy": policy_name,
        "cso_gallons": plant.cso_mg * MG_TO_GAL,
        "street_gallons": plant.street_mg * MG_TO_GAL,
        "wwtp_gallons": plant.wwtp_mg * MG_TO_GAL,
        "min_depth": depths.min(axis=0).tolist(),
        "max_depth": depths.max(axis=0).tolist(),
        "final_depth": depths[-1].tolist(),
        "depth_trace": depths.tolist(),
        "orifice_trace": plant.orifice_history,
    }


def forecast_window(step_index: int, horizon: int) -> np.ndarray:
    """Perfect-nowcast slice of the design storm, zero after the tape ends."""
    out = np.zeros((horizon, 4))
    for k in range(horizon):
        src = step_index + k
        if 0 <= src < len(RAIN_MG):
            out[k] = RAIN_MG[src]
    return out


def write_interceptor_inp(path: Path) -> Path:
    """Write a SWMM5 .inp of SU1–SU4, OR1–OR4, and overflow weirs OF1–OF4."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Storage is entered in million gallons; SWMM will see the same topology
    # even when the numeric solver above is the one closing the loop.
    lines = [
        "[TITLE]",
        ";; StormGate-Zero four-basin combined sewer interceptor",
        ";; Design storm DS-1482",
        "",
        "[OPTIONS]",
        "FLOW_UNITS          CFS",
        "INFILTRATION        HORTON",
        "FLOW_ROUTING        DYNWAVE",
        "LINK_OFFSETS        DEPTH",
        "MIN_SLOPE           0",
        "ALLOW_PONDING       YES",
        "SKIP_STEADY_STATE   NO",
        "START_DATE          07/16/2026",
        "START_TIME          18:00:00",
        "REPORT_START_DATE   07/16/2026",
        "REPORT_START_TIME   18:00:00",
        "END_DATE            07/16/2026",
        "END_TIME            19:30:00",
        "SWEEP_START         01/01",
        "SWEEP_END           12/31",
        "DRY_DAYS            5",
        "REPORT_STEP         00:05:00",
        "WET_STEP            00:05:00",
        "DRY_STEP            01:00:00",
        "ROUTING_STEP        00:00:20",
        "RULE_STEP           00:00:20",
        "",
        "[JUNCTIONS]",
        ";;Name           Elev   Ymax  Y0  Ysur  Apond",
        "J1               18     12    0   0     0",
        "J2               16     12    0   0     0",
        "J3               15     12    0   0     0",
        "J4               12     14    0   0     0",
        "",
        "[OUTFALLS]",
        ";;Name           Elev   Type      Stage  Gated",
        "WWTP             8      FREE               NO",
        "RIVER            9      FREE               NO",
        "",
        "[STORAGE]",
        ";;Name           Elev   Ymax  Y0   Shape     Apond  Acurve",
        "SU1              20     18    12   FUNCTIONAL 0      0  0  0",
        "SU2              18     16    10   FUNCTIONAL 0      0  0  0",
        "SU3              17     16    11   FUNCTIONAL 0      0  0  0",
        "SU4              14     20    16   FUNCTIONAL 0      0  0  0",
        "",
        "[ORIFICES]",
        ";;Name  From  To  Type  Offset  Qcoeff  Gated  CloseTime",
        "OR1     SU1   J1  SIDE  0       0.65    NO     0",
        "OR2     SU2   J2  SIDE  0       0.65    NO     0",
        "OR3     SU3   J3  SIDE  0       0.65    NO     0",
        "OR4     SU4   WWTP SIDE 0      0.70    NO     0",
        "",
        "[WEIRS]",
        ";;Name  From  To     Type     Crest  Qcoeff  Gated  EC  Cd  Cd2  Sur",
        "OF1     SU1   RIVER  TRANSVERSE 17.5  3.33   NO     0   0   0    YES",
        "OF2     SU2   RIVER  TRANSVERSE 15.5  3.33   NO     0   0   0    YES",
        "OF3     SU3   RIVER  TRANSVERSE 15.5  3.33   NO     0   0   0    YES",
        "OF4     SU4   RIVER  TRANSVERSE 19.6  3.33   NO     0   0   0    YES",
        "",
        "[XSECTIONS]",
        ";;Link  Shape      Geom1  Geom2  Geom3  Geom4",
        "OR1     RECT_CLOSED 4      3      0      0",
        "OR2     RECT_CLOSED 3.5    3      0      0",
        "OR3     RECT_CLOSED 3.5    3      0      0",
        "OR4     RECT_CLOSED 6      4      0      0",
        "OF1     RECT_OPEN   12     0      0      0",
        "OF2     RECT_OPEN   10     0      0      0",
        "OF3     RECT_OPEN   10     0      0      0",
        "OF4     RECT_OPEN   18     0      0      0",
        "",
        "[CONDUITS]",
        ";;Name  From  To  Length  N     Z1  Z2  Q0",
        "C1      J1    J4  1400    0.013 0   0   0",
        "C2      J2    J4  900     0.013 0   0   0",
        "C3      J3    J4  1100    0.013 0   0   0",
        "",
        "[XSECTIONS]",
        "C1      CIRCULAR  6  0  0  0",
        "C2      CIRCULAR  5  0  0  0",
        "C3      CIRCULAR  5  0  0  0",
        "",
        "[COORDINATES]",
        "SU1    400   1400",
        "SU2    900   1400",
        "SU3    1400  1400",
        "SU4    1400  600",
        "J1     400   1000",
        "J2     900   1000",
        "J3     1400  1000",
        "J4     1400  800",
        "WWTP   1800  600",
        "RIVER  1800  300",
        "",
        "[REPORT]",
        "INPUT      NO",
        "CONTROLS   YES",
        "SUBCATCHMENTS ALL",
        "NODES ALL",
        "LINKS ALL",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def try_pyswmm_available() -> dict:
    """Report whether the EPA engine can load. Never raises."""
    try:
        import pyswmm  # noqa: F401
        from pyswmm import Simulation  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    return {"available": True, "reason": "pyswmm imported"}


def commit_with_pyswmm(inp_path: Path, orifice_series: list[list[float]]) -> dict | None:
    """Replay a committed orifice series on SWMM5. Returns None if the engine is absent."""
    status = try_pyswmm_available()
    if not status["available"]:
        return None
    try:
        from pyswmm import Links, Simulation
    except Exception:
        return None
    try:
        depths: list[float] = []
        with Simulation(str(inp_path)) as sim:
            links = Links(sim)
            names = ["OR1", "OR2", "OR3", "OR4"]
            index = 0
            for _ in sim:
                if index < len(orifice_series):
                    for name, value in zip(names, orifice_series[index]):
                        if name in links:
                            links[name].target_setting = float(value)
                index += 1
                if index >= len(orifice_series):
                    break
        return {"engine": "pyswmm", "steps_applied": min(index, len(orifice_series)), "note": "dynamic-wave replay"}
    except Exception as exc:
        return {"engine": "pyswmm", "error": str(exc)}


class DualSimulation:
    """Municipal baseline and StormGate-Zero, stepped in lockstep."""

    def __init__(self) -> None:
        self.baseline = Watershed("local")
        self.stormgate = Watershed("stormgate")
        self.jammed: dict[int, float] = {}
        self.step_index = 0

    def reset(self) -> None:
        self.baseline = Watershed("local")
        self.stormgate = Watershed("stormgate")
        self.jammed = {}
        self.step_index = 0

    def rain_now(self) -> np.ndarray:
        if self.step_index >= len(RAIN_MG):
            return np.zeros(4)
        return RAIN_MG[self.step_index].copy()

    def advance(self, stormgate_u: np.ndarray) -> dict:
        rain = self.rain_now()
        base_u = policy_local(self.baseline.depth, rain, self.jammed or None)
        base = self.baseline.step(base_u, rain)
        gate = self.stormgate.step(stormgate_u, rain, self.jammed or None)
        self.step_index += 1
        return {"baseline": base, "stormgate": gate, "rain_mg": rain}

    @property
    def done(self) -> bool:
        return self.step_index >= len(RAIN_MG)
