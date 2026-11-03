"""Run the measured proofs once and write the trace files.

    python scripts/build_frontier_proof.py
"""

from __future__ import annotations

import json
import os

os.environ.setdefault("STORMGATE_OFFLINE", "1")

from pathlib import Path

import numpy as np

from backend.config import ROOT
from backend.physics.compliance_ledger import seal
from backend.physics.design_storm import RAIN_MG
from backend.physics.dynamic_wave import verify_dynamic_wave
from backend.physics.frontier import (
    HEADLINE_JAM_AT,
    HEADLINE_LOCKS,
    best_library,
    headline_rain,
    run_matrix,
    score_schedule,
    summarize,
)
from backend.physics.storm_catalog import active_rain, current, select
from backend.physics.swmm_engine import Watershed, policy_stormgate

TRACE = ROOT / "traces"


def _feedback(rain: np.ndarray) -> list[list[float]]:
    plant = Watershed("feedback")
    series = []
    for step in range(len(rain)):
        opening = policy_stormgate(plant.depth, rain[step], None)
        plant.step(opening, rain[step])
        series.append([round(float(value), 4) for value in plant.orifice_history[-1]])
    return series


def _public(row: dict) -> dict:
    return {key: value for key, value in row.items() if key != "orifice"}


def main() -> None:
    TRACE.mkdir(exist_ok=True)
    select("ds-1482")
    print("headline search", flush=True)
    headline = score_schedule(headline_rain(), HEADLINE_LOCKS, HEADLINE_JAM_AT)
    headline_out = {
        "rain": "DS-1482 runoff x 2.2 on every basin",
        "scale": 2.2,
        "locks": {"OR1": 0.05, "OR2": 0.90},
        "jam_at_step": HEADLINE_JAM_AT,
        "policies": {name: _public(row) | {"orifice": row["orifice"]} for name, row in headline.items()},
    }
    (TRACE / "compound_fault.json").write_text(json.dumps(headline_out, indent=2), encoding="utf-8")
    for name, row in headline.items():
        print(f"  {name:12} cso={row['cso_gallons']:.1f} street={row['street_gallons']:.1f}", flush=True)

    print("matrix", flush=True)
    rows = run_matrix()
    summary = summarize(rows)
    slim = [{key: value for key, value in row.items() if key != "searched_orifice"} for row in rows]
    (TRACE / "stress_matrix_100.json").write_text(
        json.dumps({"summary": summary, "rows": slim}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2), flush=True)

    print("dynamic wave", flush=True)
    waves = {}
    waves["ds-1482"] = verify_dynamic_wave(_feedback(np.array(RAIN_MG, dtype=float)), RAIN_MG)
    print("  ds-1482", waves["ds-1482"].get("worst_surcharge_psi"), waves["ds-1482"].get("worst_link"), flush=True)
    for storm_id in ("ida-2021-newark", "chicago-2023-0702"):
        select(storm_id)
        rain = np.array(active_rain(), dtype=float)
        kind = current()["kind"]
        result = verify_dynamic_wave(_feedback(rain), rain)
        result["storm"] = storm_id
        result["kind"] = kind
        waves[storm_id] = result
        print(f"  {storm_id} {kind} {result.get('worst_surcharge_psi')} {result.get('error', '')}", flush=True)
        select("ds-1482")
    waves["compound-fault"] = verify_dynamic_wave(headline["searched"]["orifice"], headline_rain())
    print("  compound", waves["compound-fault"].get("worst_surcharge_psi"), flush=True)
    refine_raw = json.loads((TRACE / "recorded_refine_pass.json").read_text(encoding="utf-8"))
    refine_series = [
        item["turn2"]["u"] if item.get("solver") == "accepted" and item.get("turn2") else item["turn1"]["u"]
        for item in refine_raw["steps"]
    ]
    waves["ds-1482-kept-refine"] = verify_dynamic_wave(refine_series, RAIN_MG)
    print("  kept-refine", waves["ds-1482-kept-refine"].get("worst_surcharge_psi"), flush=True)
    (TRACE / "wave_storms.json").write_text(json.dumps(waves, indent=2), encoding="utf-8")

    closed = json.loads((TRACE / "double_lock_closed_loop.json").read_text(encoding="utf-8"))
    hosted_blind = json.loads((TRACE / "double_lock_hosted.json").read_text(encoding="utf-8"))
    wonder_unaided = json.loads((TRACE / "wonder_unaided_recovery.json").read_text(encoding="utf-8"))
    glimmer_nv = json.loads((TRACE / "glimmer_nvidia.json").read_text(encoding="utf-8"))
    glimmer_rad = json.loads((TRACE / "glimmer_radar.json").read_text(encoding="utf-8"))
    glimmer_rad_parsed = json.loads(glimmer_rad["content"])

    library_name, library_row = best_library(headline)
    records = [
        {
            "kind": "compound-fault",
            "local_cso": headline["local"]["cso_gallons"],
            "best_library": library_name,
            "library_cso": library_row["cso_gallons"],
            "library_street": library_row["street_gallons"],
            "predrain_cso": headline["A-predrain"]["cso_gallons"],
            "predrain_street": headline["A-predrain"]["street_gallons"],
            "searched_cso": headline["searched"]["cso_gallons"],
            "searched_street": headline["searched"]["street_gallons"],
        },
        {
            "kind": "stress-matrix",
            "scenarios": summary["scenarios"],
            "searched_beats_best_library": summary["searched_beats_best_library"],
            "ties_within_1_gallon": summary["ties_within_1_gallon"],
            "library_beats_searched": summary["library_beats_searched"],
            "local_cso_minus_searched_cso_gallons": summary["local_cso_minus_searched_cso_gallons"],
        },
        {
            "kind": "dynamic-wave",
            "ds1482_psi": waves["ds-1482"].get("worst_surcharge_psi"),
            "ds1482_node": waves["ds-1482"].get("worst_link"),
            "ida_psi": waves["ida-2021-newark"].get("worst_surcharge_psi"),
            "ida_ok": waves["ida-2021-newark"].get("ok"),
            "chicago_psi": waves["chicago-2023-0702"].get("worst_surcharge_psi"),
            "chicago_ok": waves["chicago-2023-0702"].get("ok"),
            "compound_psi": waves["compound-fault"].get("worst_surcharge_psi"),
            "compound_ok": waves["compound-fault"].get("ok"),
            "refine_kept_psi": waves["ds-1482-kept-refine"].get("worst_surcharge_psi"),
            "refine_kept_node": waves["ds-1482-kept-refine"].get("worst_link"),
        },
        {
            "kind": "hosted-model-audit",
            "closed_loop_model": closed["model"],
            "closed_loop_steps": len(closed["steps"]),
            "closed_loop_first_id": closed["steps"][0]["turn1"]["response_id"],
            "closed_loop_last_id": closed["steps"][-1]["turn1"]["response_id"],
            "closed_loop_cso": closed["cso_gallons"],
            "closed_loop_street": closed["street_gallons"],
            "blind_spark_id": hosted_blind["spark"]["response_id"],
            "blind_spark_cso": hosted_blind["spark_play"]["cso_gallons"],
            "blind_spark_verdict": hosted_blind["spark_verdict"],
            "blind_wonder_id": hosted_blind["wonder"]["response_id"],
            "blind_wonder_cso": hosted_blind["wonder_play"]["cso_gallons"],
            "blind_wonder_verdict": hosted_blind["wonder_verdict"],
            "wonder_unaided_id": wonder_unaided["response_id"],
            "wonder_unaided_u": wonder_unaided["proposed_u"],
            "wonder_unaided_cso": wonder_unaided["cso_gallons"],
            "wonder_unaided_street": wonder_unaided["street_gallons"],
            "glimmer_model": glimmer_nv["model"],
            "glimmer_freeboard_id": glimmer_nv["response_id"],
            "glimmer_safe_action": glimmer_nv["safe_action"],
            "glimmer_radar_id": glimmer_rad["response_id"],
            "glimmer_radar_basin": glimmer_rad_parsed["basin"],
        },
    ]
    sealed = seal(records)
    (TRACE / "compliance_ledger.json").write_text(json.dumps(sealed, indent=2), encoding="utf-8")
    print("ledger", sealed[-1]["hash"][:16], flush=True)


if __name__ == "__main__":
    main()
