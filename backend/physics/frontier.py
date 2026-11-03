"""Measured proofs: a searched gate schedule against the hand-written laws.

The schedule is a receding-horizon search on this file's level-pool plant.
It is the same class of continuous opening the hosted model is allowed to
propose. The numbers come from replaying that search, not from a target
the search was told to hit.
"""

from __future__ import annotations

import itertools
from typing import Callable

import numpy as np

from backend.physics.design_storm import RAIN_MG
from backend.physics.swmm_engine import Watershed, policy_local, policy_open, policy_stormgate

GRID = (0.04, 0.35, 0.70, 1.0)
HEADLINE_SCALE = 2.2
HEADLINE_LOCKS = {0: 0.05, 1: 0.90}
HEADLINE_JAM_AT = 4

FAULTS = (
    ("clean", None, 99),
    ("or2-locked-50", {1: 0.50}, 8),
    ("or2-open-or3-shut", {1: 0.65, 2: 0.05}, 6),
    ("or1-shut-or4-pinched", {0: 0.05, 3: 0.20}, 0),
)


def _jam(locks: dict[int, float] | None, jam_at: int, step: int):
    if not locks or step < jam_at:
        return None
    return locks


def _play(rain: np.ndarray, choose: Callable, locks, jam_at: int) -> dict:
    plant = Watershed("proof")
    actions = []
    for step in range(len(rain)):
        jam = _jam(locks, jam_at, step)
        orifice = choose(plant, rain, step, jam, locks, jam_at)
        plant.step(orifice, rain[step], jammed=jam)
        actions.append([round(float(value), 4) for value in plant.orifice_history[-1]])
    return {
        "cso_gallons": round(plant.cso_mg * 1_000_000, 1),
        "street_gallons": round(plant.street_mg * 1_000_000, 1),
        "orifice": actions,
    }


def _law(policy):
    def choose(plant, rain, step, jam, locks, jam_at):
        return policy(plant.depth, rain[step], jam)

    return choose


def _constant(opening):
    def choose(plant, rain, step, jam, locks, jam_at):
        return np.array(opening, dtype=float)

    return choose


def searched_opening(plant, rain, step, jam, locks, jam_at) -> np.ndarray:
    """Pick this step's opening, then follow the pre-drain law with the real jam clock."""
    best = None
    best_u = np.full(4, 0.5)
    axes = []
    for index in range(4):
        if jam and index in jam:
            axes.append((float(jam[index]),))
        else:
            axes.append(GRID)
    for combo in itertools.product(*axes):
        opening = np.array(combo, dtype=float)
        clone = plant.clone("search")
        clone.step(opening, rain[step], jammed=jam)
        for future in range(step + 1, len(rain)):
            future_jam = _jam(locks, jam_at, future)
            follow = policy_stormgate(clone.depth, rain[future], future_jam)
            clone.step(follow, rain[future], jammed=future_jam)
        harm = clone.cso_mg + clone.street_mg
        if best is None or harm < best - 1e-12:
            best = harm
            best_u = opening
    return best_u


def headline_rain() -> np.ndarray:
    """DS-1482 runoff scaled by 2.2 on every basin. Same shape, more water."""
    return np.array(RAIN_MG, dtype=float) * HEADLINE_SCALE


def score_schedule(rain: np.ndarray, locks, jam_at: int) -> dict:
    """Every named law, plus the searched schedule, on one tape."""
    return {
        "local": _play(rain, _law(policy_local), locks, jam_at),
        "open": _play(rain, _law(policy_open), locks, jam_at),
        "A-predrain": _play(rain, _law(policy_stormgate), locks, jam_at),
        "B-balanced": _play(rain, _constant([0.45, 0.42, 0.40, 0.62]), locks, jam_at),
        "C-retention": _play(rain, _constant([0.08, 0.08, 0.08, 0.28]), locks, jam_at),
        "D-bypass": _play(rain, _constant([1.0, 1.0, 1.0, 1.0]), locks, jam_at),
        "searched": _play(rain, searched_opening, locks, jam_at),
    }


def replay(rain: np.ndarray, orifice: list, locks, jam_at: int) -> dict:
    """Re-integrate a saved opening. The jam still overwrites a locked gate."""
    plant = Watershed("replay")
    for step, opening in enumerate(orifice):
        jam = _jam(locks, jam_at, step)
        plant.step(opening, rain[step], jammed=jam)
    return {
        "cso_gallons": round(plant.cso_mg * 1_000_000, 1),
        "street_gallons": round(plant.street_mg * 1_000_000, 1),
    }


def matrix_rain(index: int) -> np.ndarray:
    """Twenty-five deterministic shears of DS-1482. Index 0..24."""
    rain = np.array(RAIN_MG, dtype=float)
    basin = index % 4
    gain = 1.0 + (index % 5) * 0.7
    rain[:, basin] *= gain
    if index % 2 == 1:
        rain[:, (basin + 1) % 4] *= 0.5
    return rain


def _harm(row: dict) -> float:
    return float(row["cso_gallons"]) + float(row["street_gallons"])


def best_library(scored: dict) -> tuple[str, dict]:
    names = ("A-predrain", "B-balanced", "C-retention", "D-bypass")
    winner = min(names, key=lambda name: (_harm(scored[name]), name))
    return winner, scored[winner]


def run_matrix() -> list[dict]:
    rows = []
    for storm_index in range(25):
        rain = matrix_rain(storm_index)
        for fault_name, locks, jam_at in FAULTS:
            scored = score_schedule(rain, locks, jam_at)
            library_name, library = best_library(scored)
            searched = scored["searched"]
            rows.append(
                {
                    "storm": storm_index,
                    "fault": fault_name,
                    "jam_at": jam_at,
                    "locks": locks or {},
                    "local_cso": scored["local"]["cso_gallons"],
                    "local_street": scored["local"]["street_gallons"],
                    "library": library_name,
                    "library_cso": library["cso_gallons"],
                    "library_street": library["street_gallons"],
                    "searched_cso": searched["cso_gallons"],
                    "searched_street": searched["street_gallons"],
                    "searched_orifice": searched["orifice"],
                }
            )
    return rows


def summarize(rows: list[dict]) -> dict:
    wins = ties = losses = 0
    cso_prevented = street_prevented = 0.0
    for row in rows:
        library = row["library_cso"] + row["library_street"]
        searched = row["searched_cso"] + row["searched_street"]
        if searched < library - 1.0:
            wins += 1
        elif searched > library + 1.0:
            losses += 1
        else:
            ties += 1
        cso_prevented += row["local_cso"] - row["searched_cso"]
        street_prevented += row["local_street"] - row["searched_street"]
    return {
        "scenarios": len(rows),
        "searched_beats_best_library": wins,
        "ties_within_1_gallon": ties,
        "library_beats_searched": losses,
        "local_cso_minus_searched_cso_gallons": round(cso_prevented, 1),
        "local_street_minus_searched_street_gallons": round(street_prevented, 1),
        "grid": list(GRID),
        "note": (
            "Each scenario is one shear of DS-1482 and one mechanical lock. "
            "The searched opening minimizes level-pool river spill plus street spill. "
            "The library pick is the best of A-predrain, B-balanced, C-retention, and D-bypass "
            "on that same sum."
        ),
    }
