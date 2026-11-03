"""Statutory ceiling and a labeled receiving-water estimate.

33 U.S.C. 1319(d) is a civil penalty per day per violation. 40 CFR 19.4
Table 1 sets that judicial maximum at $68,445 for penalties assessed on
or after 8 January 2025. The statute has no per-gallon cleanup multiplier,
so this module does not invent one.

The E. coli figure dilutes a planning density for untreated overflow into
a fixed receiving-water volume. It is not a grab sample.
"""

from __future__ import annotations

# 40 CFR 19.4 Table 1, 33 U.S.C. 1319(d), assessed on or after 8 Jan 2025.
CWA_JUDICIAL_USD_PER_DAY = 68_445
# EPA 2012 recreational water quality criteria, beach action value.
BEACH_ACTION_CFU_PER_100ML = 235
# Order-of-magnitude planning density for untreated CSO. Not a measured plume.
PLANNING_CSO_CFU_PER_100ML = 1_000_000
# Fixed mixing volume so a zero spill reads as zero added bacteria.
RECEIVING_MIX_GALLONS = 10_000_000


def exposure(cso_gallons: float) -> dict:
    gallons = max(0.0, float(cso_gallons))
    days = 1 if gallons > 0 else 0
    mix = gallons + RECEIVING_MIX_GALLONS
    cfu = (PLANNING_CSO_CFU_PER_100ML * gallons / mix) if gallons else 0.0
    return {
        "statutory_usd": CWA_JUDICIAL_USD_PER_DAY * days,
        "statutory_per_day_usd": CWA_JUDICIAL_USD_PER_DAY,
        "violation_days": days,
        "citation": "33 USC 1319(d); 40 CFR 19.4 Table 1 (assessed on or after 8 Jan 2025)",
        "ecoli_cfu_per_100ml": round(cfu, 1),
        "beach_action_cfu_per_100ml": BEACH_ACTION_CFU_PER_100ML,
        "planning_cso_cfu_per_100ml": PLANNING_CSO_CFU_PER_100ML,
        "above_beach_action": cfu > BEACH_ACTION_CFU_PER_100ML,
        "label": (
            "Statutory ceiling for one day if this plant spills. "
            "E. coli is a planning density diluted into 10 million gallons, not a lab result."
        ),
    }
