"""Storm tapes, the statutory ceiling, and the second-turn guard."""

import numpy as np

from backend.agents.wonder_mpc_supervisor import keep_refinement
from backend.physics.design_storm import RAIN_MG
from backend.physics.nexrad_mosaic import index_to_dbz
from backend.physics.dynamic_wave import verify_dynamic_wave
from backend.physics.exposure import CWA_JUDICIAL_USD_PER_DAY, exposure
from backend.physics.storm_catalog import active_rain, select, spawn_cell


def test_ida_tape_is_not_the_scorecard_storm():
    from backend.physics.storm_catalog import current

    storm = select("ida-2021-newark")
    assert storm["id"] == "ida-2021-newark"
    assert not np.allclose(active_rain(), RAIN_MG)
    assert current()["kind"] in {"nexrad-mosaic", "gauge-anchored"}


def test_palette_anchor_reads_gold_as_45_dbz():
    values = index_to_dbz(np.array([0, 150, 170]))
    assert values[0] == 0
    assert values[1] == 45
    assert values[2] == 55


def test_dropped_cell_changes_the_tape():
    spawn_cell(0.70, 0.75, 60)
    assert active_rain().shape == (18, 4)
    assert float(active_rain().sum()) > 0
    assert not np.allclose(active_rain(), RAIN_MG)


def test_scorecard_tape_is_restored():
    select("chicago-2023-0702")
    select("ds-1482")
    assert np.allclose(active_rain(), RAIN_MG)


def test_penalty_is_the_daily_ceiling_not_a_per_gallon_fine():
    dry = exposure(0)
    wet = exposure(14_820_000)
    assert dry["statutory_usd"] == 0
    assert dry["ecoli_cfu_per_100ml"] == 0
    assert wet["statutory_usd"] == CWA_JUDICIAL_USD_PER_DAY
    assert wet["statutory_usd"] == 68_445
    assert wet["above_beach_action"] is True


def test_second_turn_cannot_spill_more_than_the_physics_winner():
    assert keep_refinement(0, 0)
    assert keep_refinement(1, 0)
    assert not keep_refinement(1.1, 0)


def test_dynamic_wave_reports_surcharge_or_a_real_error():
    rain = np.zeros((4, 4))
    rain[:, 3] = 1.0
    series = [[0.2, 0.2, 0.2, 0.4]] * 4
    report = verify_dynamic_wave(series, rain)
    assert report["ok"], report.get("error")
    assert "worst_surcharge_psi" in report
    assert len(report["pipes"]) == 3
