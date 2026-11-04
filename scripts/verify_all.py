"""Verify all recorded proofs, response IDs, PySWMM heads, and the SHA-256 ledger.

    python scripts/verify_all.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("STORMGATE_OFFLINE", "1")

from backend.agents.glimmer_edge_guard import local_interlock
from backend.config import ROOT
from backend.physics.compliance_ledger import load, verify
from backend.physics.frontier import HEADLINE_JAM_AT, HEADLINE_LOCKS, headline_rain, replay
from backend.physics.swmm_engine import run_episode

TRACE = ROOT / "traces"


def main() -> None:
    local_ep = run_episode("local")
    open_ep = run_episode("uncontrolled")
    sg_ep = run_episode("stormgate")
    sg_jam = run_episode("stormgate", jammed_at=8, lock=0.50)

    compound = json.loads((TRACE / "compound_fault.json").read_text(encoding="utf-8"))
    closed = json.loads((TRACE / "double_lock_closed_loop.json").read_text(encoding="utf-8"))
    blind = json.loads((TRACE / "double_lock_hosted.json").read_text(encoding="utf-8"))
    unaided = json.loads((TRACE / "wonder_unaided_recovery.json").read_text(encoding="utf-8"))
    matrix = json.loads((TRACE / "stress_matrix_100.json").read_text(encoding="utf-8"))
    waves = json.loads((TRACE / "wave_storms.json").read_text(encoding="utf-8"))
    glimmer_nv = json.loads((TRACE / "glimmer_nvidia.json").read_text(encoding="utf-8"))
    glimmer_rad = json.loads((TRACE / "glimmer_radar.json").read_text(encoding="utf-8"))
    ledger = load(TRACE / "compliance_ledger.json")

    rain = headline_rain()
    closed_replay = replay(rain, [step["applied"] for step in closed["steps"]], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    spark_blind_replay = replay(rain, blind["spark_play"]["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    wonder_blind_replay = replay(rain, blind["wonder_play"]["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    wonder_unaided_replay = replay(rain, unaided["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    ruling = local_interlock(glimmer_nv["proposed_action"], glimmer_nv["depth"], glimmer_nv["rain_mmhr"])

    assert abs(local_ep["cso_gallons"] - 14_820_000.0) < 1.0
    assert sg_ep["cso_gallons"] == 0.0
    assert sg_jam["cso_gallons"] == 0.0
    assert closed_replay["cso_gallons"] == 0.0
    assert closed_replay["street_gallons"] == 0.0
    assert wonder_unaided_replay["cso_gallons"] == 0.0
    assert wonder_unaided_replay["street_gallons"] == 0.0
    assert spark_blind_replay["cso_gallons"] == 4_333_880.8
    assert wonder_blind_replay["cso_gallons"] == 6_966_494.7
    assert ruling["safe_action"] == glimmer_nv["safe_action"]
    assert verify(ledger), "SHA-256 compliance ledger failed verification"

    print("=" * 78)
    print("STORMGATE-ZERO — VERIFICATION SCORECARD (OFFLINE REPLAY + SHA-256 AUDIT)")
    print("=" * 78)
    print(f"1. DS-1482 float switch CSO      : {local_ep['cso_gallons']:>13,.1f} gal")
    print(f"   DS-1482 all gates open CSO    : {open_ep['cso_gallons']:>13,.1f} gal")
    print(f"   DS-1482 StormGate-Zero CSO    : {sg_ep['cso_gallons']:>13,.1f} gal")
    print(f"   DS-1482 + OR2 jammed 50% CSO  : {sg_jam['cso_gallons']:>13,.1f} gal")
    print("-" * 78)
    print("2. Compound Fault (DS-1482 x 2.2, OR1=0.05 & OR2=0.90 from minute 20)")
    print(f"   Municipal float switch        : {compound['policies']['local']['cso_gallons']:>13,.1f} gal CSO")
    print(
        f"   A-predrain (hand-written law) : {compound['policies']['A-predrain']['cso_gallons']:>13,.1f} gal CSO"
        f" + {compound['policies']['A-predrain']['street_gallons']:,.1f} gal street"
    )
    print(f"   B-balanced (best named law)   : {compound['policies']['B-balanced']['cso_gallons']:>13,.1f} gal CSO")
    print(
        f"   muse-spark-1.3 blind 18-step  : {spark_blind_replay['cso_gallons']:>13,.1f} gal CSO"
        f" ({blind['spark']['response_id']} -> {blind['spark_verdict']})"
    )
    print(
        f"   muse-wonder-1.0 blind 18-step : {wonder_blind_replay['cso_gallons']:>13,.1f} gal CSO"
        f" ({blind['wonder']['response_id']} -> {blind['wonder_verdict']})"
    )
    print(
        f"   muse-wonder-1.0 unaided step4 : {wonder_unaided_replay['cso_gallons']:>13,.1f} gal CSO"
        f" + {wonder_unaided_replay['street_gallons']:,.1f} gal street"
        f" ({unaided['response_id']}, u={unaided['proposed_u']}, no grid shown)"
    )
    print(
        f"   muse-spark-1.3 closed-loop    : {closed_replay['cso_gallons']:>13,.1f} gal CSO"
        f" + {closed_replay['street_gallons']:,.1f} gal street"
        f" (18 calls: {closed['steps'][0]['turn1']['response_id']}..{closed['steps'][-1]['turn1']['response_id']})"
    )
    print("-" * 78)
    s = matrix["summary"]
    print(
        f"3. 100-Scenario Stress Matrix    : {s['searched_beats_best_library']} wins / "
        f"{s['ties_within_1_gallon']} ties / {s['library_beats_searched']} losses "
        f"({s['local_cso_minus_searched_cso_gallons']:,.1f} gal saved vs float)"
    )
    print("-" * 78)
    print(
        "4. PySWMM 5 DYNWAVE Surcharge    : "
        f"DS-1482={waves['ds-1482']['worst_surcharge_psi']} psi ({waves['ds-1482']['worst_link']}) | "
        f"Kept-Refine={waves['ds-1482-kept-refine']['worst_surcharge_psi']} psi ({waves['ds-1482-kept-refine']['worst_link']}) | "
        f"Ida={waves['ida-2021-newark']['worst_surcharge_psi']} psi | "
        f"Chicago={waves['chicago-2023-0702']['worst_surcharge_psi']} psi | "
        f"Compound={waves['compound-fault']['worst_surcharge_psi']} psi"
    )
    print("-" * 78)
    rad_parsed = json.loads(glimmer_rad["content"])
    print(
        "5. meta/muse-glimmer-30b (NIM)   : "
        f"freeboard={glimmer_nv['response_id']} (safe_action={glimmer_nv['safe_action']}) | "
        f"Ida radar={glimmer_rad['response_id']} (quadrant={rad_parsed['hottest_quadrant']}, basin={rad_parsed['basin']})"
    )
    print("-" * 78)
    print(f"6. SHA-256 Compliance Ledger     : VERIFIED ({len(ledger)} blocks, tip={ledger[-1]['hash'][:16]})")
    print("=" * 78)


if __name__ == "__main__":
    main()
