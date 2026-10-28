"""Score the design storm: uncontrolled vs local rules vs StormGate-Zero."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.physics.swmm_engine import run_episode  # noqa: E402


def _gallons(value: float) -> str:
    return f"{value:15,.0f}"


def main() -> None:
    rows = [
        ("Uncontrolled (gates open)", run_episode("uncontrolled")),
        ("Local static float rules", run_episode("local")),
        ("StormGate-Zero", run_episode("stormgate")),
        ("StormGate-Zero, OR2 jammed 50% at t=40 min", run_episode("stormgate", jammed_at=8)),
    ]
    print("StormGate-Zero  ·  design storm DS-1482  ·  90 min  ·  5 min steps")
    print("Level-pool St. Venant storage routing, plant-limited orifice at SU4")
    print()
    header = f"{'Controller':<42} {'CSO gallons':>15} {'Street gal':>12} {'max SU1':>8} {'max SU4':>8} {'min SU4':>8}"
    print(header)
    print("-" * len(header))
    for label, result in rows:
        depths_max = result["max_depth"]
        depths_min = result["min_depth"]
        print(
            f"{label:<42} {_gallons(result['cso_gallons'])} "
            f"{result['street_gallons']:12,.0f} "
            f"{depths_max[0]:8.0%} {depths_max[3]:8.0%} {depths_min[3]:8.0%}"
        )
    print()
    local = rows[1][1]["cso_gallons"]
    controlled = rows[2][1]["cso_gallons"]
    print(f"Captured vs local rules: {local - controlled:,.0f} gallons kept out of the river.")


if __name__ == "__main__":
    main()
