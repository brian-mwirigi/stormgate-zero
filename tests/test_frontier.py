"""Replay the measured frontier proofs. The search itself is not repeated here."""

from __future__ import annotations

import json
from pathlib import Path

from backend.config import ROOT
from backend.physics.compliance_ledger import load, verify
from backend.physics.frontier import (
    HEADLINE_JAM_AT,
    HEADLINE_LOCKS,
    headline_rain,
    replay,
)

TRACE = ROOT / "traces"


def test_searched_schedule_holds_the_double_lock_and_the_best_law_does_not():
    payload = json.loads((TRACE / "compound_fault.json").read_text(encoding="utf-8"))
    policies = payload["policies"]
    rain = headline_rain()
    searched = replay(rain, policies["searched"]["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    library = replay(rain, policies["B-balanced"]["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    predrain = replay(rain, policies["A-predrain"]["orifice"], HEADLINE_LOCKS, HEADLINE_JAM_AT)
    assert searched["cso_gallons"] == 0.0
    assert searched["street_gallons"] == 0.0
    assert library["cso_gallons"] > 4_000_000
    assert predrain["cso_gallons"] > 8_000_000
    assert predrain["street_gallons"] > 800_000
    assert abs(searched["cso_gallons"] - policies["searched"]["cso_gallons"]) < 1.0
    assert abs(library["cso_gallons"] - policies["B-balanced"]["cso_gallons"]) < 1.0


def test_stress_matrix_covers_one_hundred_and_replays():
    payload = json.loads((TRACE / "stress_matrix_100.json").read_text(encoding="utf-8"))
    rows = payload["rows"]
    summary = payload["summary"]
    assert len(rows) == 100
    assert summary["scenarios"] == 100
    accounted = (
        summary["searched_beats_best_library"]
        + summary["ties_within_1_gallon"]
        + summary["library_beats_searched"]
    )
    assert accounted == 100
    assert summary["searched_beats_best_library"] == 14
    assert summary["ties_within_1_gallon"] == 86
    assert summary["library_beats_searched"] == 0
    assert summary["local_cso_minus_searched_cso_gallons"] > 1_000_000_000


def test_compliance_ledger_recomputes_and_rejects_a_changed_gallon():
    path = TRACE / "compliance_ledger.json"
    records = load(path)
    assert verify(records)
    assert records[0]["searched_cso"] == 0.0
    assert records[0]["library_cso"] > 4_000_000
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered[0]["searched_cso"] = 1.0
    assert verify(tampered) is False


def test_dynamic_wave_ran_on_the_three_tapes():
    waves = json.loads((TRACE / "wave_storms.json").read_text(encoding="utf-8"))
    for key in ("ds-1482", "ida-2021-newark", "chicago-2023-0702", "compound-fault"):
        assert waves[key]["ok"] is True
        assert waves[key]["worst_surcharge_psi"] >= 0
    assert waves["ds-1482"]["worst_link"] == "J1"
    assert abs(waves["ds-1482"]["worst_surcharge_psi"] - 2.51) < 0.01
    assert waves["ds-1482-kept-refine"]["worst_link"] == "J3"
    assert abs(waves["ds-1482-kept-refine"]["worst_surcharge_psi"] - 3.539) < 0.01
    assert abs(waves["ida-2021-newark"]["worst_surcharge_psi"] - 3.338) < 0.01
    assert abs(waves["chicago-2023-0702"]["worst_surcharge_psi"] - 1.846) < 0.01
    assert waves["compound-fault"]["worst_link"] == "J3"
    assert abs(waves["compound-fault"]["worst_surcharge_psi"] - 5.306) < 0.01
