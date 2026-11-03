# StormGate-Zero

Radar reflectivity goes in. Continuous orifice openings come out. On a four-basin combined sewer, the municipal float switch spills **14,820,000 gallons** on design storm DS-1482. StormGate-Zero spills **0**, including the case where sluice OR2 jams at 50% open.

Built for the Meta Global AI Developer Hackathon, Indie Track, theme "Push the Frontier". Deadline Wednesday, November 4, 2026, 9:00 PM EST. The recorded engineering pass is commit [`441e7b6`](https://github.com/brian-mwirigi/stormgate-zero/commit/441e7b6).

## Scorecard

| Forcing | What it is | Float switch | StormGate-Zero |
| --- | --- | ---: | ---: |
| DS-1482 | 90 min, 18 steps of 5 min, played in about 20 s | 14,820,000 gal | **0 gal** |
| DS-1482, all gates open | Same storm, no control | 3.1 million gal | — |
| DS-1482, OR2 jammed at 50% | Mechanical lock from minute 40 | 14,820,000 gal | **0 gal** |
| Ida mosaic | IEM N0Q crops, Newark, 1 Sep 2021, 23:30–00:45 UTC | ~12.1 million gal | **0 gal** |
| Chicago mosaic | IEM N0Q crops, west side, 2 Jul 2023, 21:00–23:30 UTC | ~13.7 million gal | **0 gal** |
| Newark gauge hour | Published 3.24 in/hr, 8–9 p.m. local | overflows the plant | **~26.2 million gal** |
| Chicago gauge hour | Gauge-shaped saturation reconstruction | overflows the plant | **~9.2 million gal** |

The mosaic rows are what the forcing menu plays. Palette rainfall on those crops sits under the published cloudburst hour, so the pre-drain law holds the weir. The gauge rows are the saturation check: Newark's recorded hour still exceeds this plant's physical storage, and the solver reports the spill instead of claiming a dry weir.

A finished DS-1482 schedule, replayed in PySWMM as a SWMM5 dynamic wave, puts Junction **J3 at 3.685 psi** above the crown. Level-pool CSO on that same schedule is 0 gallons. Any spill above 0 exposes the utility to the 40 CFR 19.4 ceiling of **$68,445 per day per violation** (33 U.S.C. 1319(d), penalties assessed on or after 8 Jan 2025). The board's E. coli figure is a planning density of 1,000,000 CFU/100 mL diluted into 10,000,000 gallons of receiving water, read against the EPA 2012 beach action value of 235 CFU/100 mL.

## Submission copy

StormGate-Zero closes a single causal loop from radar reflectivity to continuous orifice actuation on a four-basin combined sewer ([github.com/brian-mwirigi/stormgate-zero](https://github.com/brian-mwirigi/stormgate-zero), commit `441e7b6`). On the 90-minute design storm DS-1482 (18 five-minute steps played in 20s), the municipal float switch holds the downstream orifice shut until the crown and spills 14,820,000 gallons (and 3.1M gallons with all gates wide open), triggering the 40 CFR 19.4 Clean Water Act statutory ceiling of $68,445 per day per violation (33 U.S.C. 1319(d)). StormGate-Zero pre-drains Basin 4 ahead of the second convective core and spills 0 gallons—including when sluice gate OR2 mechanically jams at 50% mid-storm. Operators can switch the board to real radar mosaic frames from Hurricane Ida (spilling ~12.1M gal under the float switch vs. 0 gal with StormGate-Zero) and the July 2023 Chicago flood (where `sam-3.1` tracks yellow-core boxes across 5 of 6 frames, cutting a ~13.7M gal float spill to 0 gal), or click the radar to drop a live 60-dBZ cell; separate gauge-shaped saturation hours (including Newark's 3.24 in/hr Ida peak at ~26.2M gal and Chicago's gauge hour at ~9.2M gal) benchmark physical storage limits beyond plant capacity. In `traces/recorded_refine_pass.json` against `api.meta.ai/v1`, `sam-3.1` segments storm cores in the `<0f>` grammar, `muse-spark-1.3` generates Turn-1 continuous orifice openings and Turn-2 score-conditioned refinements across the 18-step pass (with the physics guard keeping 15 refinements, rejecting steps 7 and 11 for higher spill, and handling a null vector on step 10 to hold 0 gallons spilled), `muse-voice-transcribe-1.0` transcribes the radio fault locking OR2 at 50%, `muse-wonder-1.0` computes the jammed recovery vector (holding OR2 at 0.50 and setting OR4 to 0.62), and `muse-image-1.0` renders the solver-locked outfall plate. A local freeboard interlock overrides pinched gates above 92% depth and 35 mm/hr inflow unless mechanically locked, and `PySWMM` dynamic-wave verification on the completed DS-1482 schedule confirms Junction J3 peaks at 3.685 psi above crown with 0 gallons spilled. Subsequent loops replay the captured traces with `STORMGATE_REFINE=0` by default for zero-key reproducibility.

## One causal loop

Every model sits on the actuation path.

```
IEM N0Q mosaic  or  DS-1482 Z-R field          SCADA radio (WAV)
        |                                              |
        v                                              v
 sam-3.1   POST /v1/responses                muse-voice-transcribe-1.0
 <0f> boxes ∩ four basin quadrants           POST /v1/asr/transcribe
        |                                              |
        +---------------- rain on SU1..SU4 -----------+
                                 |
                                 v
              12 parallel 60-minute level-pool futures
              A-predrain · B-balanced · C-retention · D-bypass
                                 |
                                 v
                    muse-spark-1.3   Turn 1
                    continuous u = [OR1, OR2, OR3, OR4]
                                 |
                                 v
                    muse-spark-1.3   Turn 2   (recorded once)
                    mutates u after it sees the rollout scores
                                 |
                                 v
                    physics guard
                    keep the vector only if lookahead CSO
                    is within 1 gallon of the physics winner
                                 |
                                 v
                    muse-wonder-1.0
                    one recovery vector on the OR2 jam
                                 |
                                 v
                    local freeboard interlock
                    depth > 92% and inflow > 35 mm/hr
                    forces a pinched gate to 60%
                    unless the valve is mechanically locked
                                 |
                +----------------+----------------+
                v                                 v
     level-pool storage routing           muse-image-1.0
     SU1..SU4 · OR1..OR4 · OF1..OF4       outfall plate, once
     then PySWMM dynamic wave on
     the finished schedule
```

The four named strategies are the audit. The model does not pick from a menu. It proposes a continuous opening, and the ranker keeps the lowest combined-sewer overflow, then the lowest street flooding, then Wonder, then Spark, then a name that starts with A-.

## Receipts

`traces/recorded_refine_pass.json` is the second-turn log. `traces/recorded_live_pass.json` is the first scored Spark, SAM, and voice pass. The server replays both from `traces/live_models.json`. `STORMGATE_REFINE` defaults to `0`, so a looping board does not bill the same step again.

| Model | What the files show |
| --- | --- |
| `muse-spark-1.3` | Turn 1 vector, commentary, latency, and a `resp_*` id on keys `0\|` through `17\|`. The scored pass executed the model on 17 steps. Step 16 of that pass fell back to A-predrain when the call did not return. A later step-16 response is in the file (`resp_6ae8fa47aad163f2f96b446b`). Turn 2, in the refine file, returned a vector on 17 of 18 steps. |
| Physics guard | Kept 15 refinements. Rejected step 7 and step 11 (`rejected-spilled-more`). Step 10 is `no-vector`. The kept sequence spills 0 gallons. Stitching the two rejected vectors back into the 90 minutes spills about 3.4 million gallons. The guard is a 60-minute lookahead. |
| `sam-3.1` | DS-1482 frames at 0, 40, and 55 minutes. Minute 0 came back empty. Minute 40 box `[0.3792, 0.4813, 0.5417, 0.6417]`. Minute 55 box `[0.5229, 0.6083, 0.6771, 0.7604]`. Raw text is `<0f>` plus `<\|box;x1=…\|>`. Ida crops: boxes on 4 of 6 frames for "red storm cell". Chicago crops: boxes on 5 of 6 frames for "yellow storm cell". |
| `muse-voice-transcribe-1.0` | "Operator 4, Sluicegate 2 is mechanically jammed at 50% open." Parser locks OR2 at 0.50. |
| `muse-wonder-1.0` | One call on the jam at step 8. Vector `[0.04, 0.50, 0.04, 0.6209]`, selected `W-wonder`, `resp_6ae9adeac24e0d3e800f40f3`. OR2 stays at the mechanical lock. OR4 opens to 0.62 to pre-drain Basin 4. |
| `muse-image-1.0` | One outfall plate, stored as PNG. The board serves that file on later loops. |
| PySWMM 2.2.0 | `verify_dynamic_wave` on the finished 18-step schedule. Worst node J3, 3.685 psi above crown, `steps_commanded` 18. |

Hosted calls go to `POST https://api.meta.ai/v1/responses`, except voice, which is multipart `POST /v1/asr/transcribe`. The live control model is `muse-spark-1.3`. The partner id `meta-models/muse-spark-open` and `meta-models/Muse-Glimmer-30B` return `model_not_found` on that host. Glimmer in this loop is the local numeric interlock: above 92% depth, inflow over 35 mm/hr, and a gate under 25% open, the gate is forced to 60% unless it is jammed. Above 97% depth a gate under 90% open is forced fully open, again unless it is jammed.

## The plant

Four storage units on a short interceptor. OR1–OR3 discharge into SU4. SU4's orifice is the treatment plant. Above full depth, SU4 spills to the river and SU1–SU3 spill to the street.

The float switch leaves the upstream gates open and holds OR4 at 2% until the basin reaches 96%, then throws it fully open. That stores the peak and dumps it over the weir, which is why the float switch spills more than an all-gates-open plant on DS-1482. StormGate spends plant capacity before the rain, holds the upstream basins, and lets SU4 crest near 91% instead of the weir. On this storm the 5-minute level-pool step realizes about a 14% minimum and a 93% crest.

Volume, orifice capacity, plant capacity, and runoff share one scale factor, `VOLUME_SCALE` in `backend/physics/design_storm.py`, so the float-rule integral is exactly 14,820,000 gallons and the depths stay on that path. The live fan-out is twelve cloned 60-minute level-pool rollouts per control step, on a 1.15-second beat. `write_interceptor_inp` writes a real SWMM5 network. The dynamic-wave check runs on a verification interceptor after the episode finishes: junctions can carry surcharge head, conduits are capped at the pipe diameter, and the scorecard the tests lock remains the level-pool integral.

EPA Report to Congress 833-R-04-001 counts more than 700 U.S. municipalities and about 43,000 combined-sewer overflows a year, on the order of 850 billion gallons. The concrete replacement is a multi-hundred-billion-dollar program. The gates already in the ground move after the water is at the crown. A convective core is visible on radar before that.

## Forcing on the board

The command center is a dark SCADA twin at `http://localhost:5173`. The selector and the radar canvas share one active tape.

| Control | Result |
| --- | --- |
| DS-1482 | Synthetic two-core design storm. The 14,820,000 vs 0 scorecard. |
| Hurricane Ida mosaic | Six IEM national N0Q frames, 1.2° window on (40.69, −74.17). Quadrants are NW SU1, SW SU2, NE SU3, SE SU4. |
| Chicago mosaic | Six frames on (41.85, −87.75). NWS daily gauges that day include Berwyn 8.96 in and Midway 4.68 in. |
| Click the radar | Drops a 60 dBZ cell. Marshall-Palmer Z-R, then the same million-gallon conversion as the design storm. |

Mosaic frames are IEM national composites. Pixel scale is 0.005°, origin longitude −126, latitude 50. Palette index 150 reads as 45 dBZ and index 170 as 55 dBZ. Each tape is a 1.2° window centered on the gauge, with the four basins laid on as quadrants. The depth strip under the hydraulic twin shows level-pool gallons, the $68,445 ceiling, the planning E. coli dilution, and the PySWMM head once the episode has finished.

## Prize tracks

| Track | What this build puts on the table |
| --- | --- |
| Indie Grand Prize | Closed loop from reflectivity to a PDE-checked gate schedule. 14.82 million gallons to 0 on DS-1482, jam included. Real mosaic hours on the same law. A gauge hour that still overflows, reported as overflow. |
| Agentic use | Spark proposes `[u1, u2, u3, u4]` every DS-1482 step, then a second turn conditioned on rollout scores. Wonder adds one recovery vector when voice locks OR2. Both are dropped when the lookahead spills more than the physics winner. |
| Creative build | `muse-image-1.0` renders the solver-locked outfall once: the float-switch weir beside the same concrete, dry. |
| Open-weight | The library trajectories (A-predrain, B-balanced, C-retention, D-bypass) and the freeboard interlock run locally on every step. Hosted open-weight ids are not what this loop calls. |

## Repository

```
backend/config.py                         keys, model ids, STORMGATE_REFINE
backend/episode.py                        live loop, forcing switch, wave check
backend/main.py                           FastAPI, WebSocket twin, storm routes
backend/physics/design_storm.py           DS-1482 and VOLUME_SCALE
backend/physics/storm_catalog.py          DS-1482, mosaics, gauge fallbacks, cell drop
backend/physics/nexrad_mosaic.py          IEM N0Q download, crop, Z-R
backend/physics/swmm_engine.py            level-pool plant and 12 rollouts
backend/physics/dynamic_wave.py           PySWMM DYNWAVE verification
backend/physics/exposure.py               $68,445/day and planning E. coli
backend/agents/sam_radar_tracker.py       sam-3.1 and the <0f> parser
backend/agents/spark_open_worker.py       Turn 1 vector and Turn 2 refine
backend/agents/wonder_mpc_supervisor.py   ranker and physics guard
backend/agents/glimmer_edge_guard.py      local freeboard interlock
backend/agents/voice_scada_bridge.py      WAV transcribe and jam parser
backend/agents/image_counterfactual.py    outfall plate
backend/agents/model_traces.py            replay cache
frontend/                                 React SCADA command center
traces/recorded_live_pass.json            first Spark, SAM, and voice pass
traces/recorded_refine_pass.json          Turn 1, Turn 2, accept or reject
traces/live_models.json                   bytes the server replays
traces/nexrad/                            Ida and Chicago crops, rain, SAM boxes
tests/                                    16 offline tests, STORMGATE_OFFLINE=1
```

## Run it

Python 3.10+ and Node 20+. A Meta key is optional. With no key, and after the traces are on disk, the board replays the recorded pass.

```bash
cd stormgate-zero
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # MODEL_API_KEY only if you intend to call the API
python scripts/generate_demo_assets.py
python scripts/run_benchmark.py
uvicorn backend.main:app --port 8000
```

Second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The episode starts on its own. Switch the forcing, click the radar to drop a 60 dBZ cell, inject the OR2 jam from the bottom bar, and render the outfall twin.

```bash
python -m pytest tests -q
```

Sixteen tests pass offline. They lock the 14,820,000 gallon float-rule integral, the 0 gallon StormGate result with OR2 jammed, the ranker, the `<0f>` parser, the daily penalty ceiling, the second-turn spill guard, and a real PySWMM dynamic-wave return. Leave `STORMGATE_REFINE` unset. Setting it to `1` calls `muse-spark-1.3` again on a cache miss.

## Three-minute demo

DS-1482 runs 18 steps and then loops. Reset before you hit record so the first loop starts at minute 0.

**0:00–0:25. Dry weir.** Leave the jam off.

> The left sewer is the float switch. It holds the downstream gate shut until the tank is at the crown. The right sewer sees Core A on Basin 1, spends the plant before the rain, and drops Basin 4 before Core B around minute 55. The counters lock at 14,820,000 gallons and 0 gallons. An all-gates-open plant spills about 3.1 million. The float switch is worse because it stores the peak and then dumps it.

**0:25–1:10. The jam.** On the restart, before Core B reaches Basin 4, press **Inject Gate #2 Mechanical Jam (50%)**.

> That button feeds the same radio line the voice model transcribed: OR2 locked at 50%. Wonder's recorded recovery holds OR2 at 0.50 and opens OR4 to 0.62. A jammed gate cannot be moved. Above 92% full and 35 mm/hr, the local interlock forces any other pinched gate to 60%. The green counter stays at 0.

**1:10–2:10. The guard and the storms.** Open `traces/recorded_refine_pass.json` on step 7 and step 11, then switch the forcing to Ida and Chicago.

> Spark proposed a second opening after it saw the scores. The solver threw two of them out because the lookahead spilled more, and step 10 returned nothing. The kept sequence still spills 0. The Ida and Chicago menus play real mosaic frames. The float switch spills about 12.1 million and 13.7 million. The same pre-drain law holds 0. The gauge-shaped Newark hour, 3.24 inches, still overflows this plant by about 26.2 million gallons. That number is the storage limit.

**2:10–2:45. Head and plate.** Let the DS-1482 loop finish so the depth strip fills in, then press **Render Outfall Visual Twin**.

> PySWMM ran the committed schedule as a dynamic wave. Junction J3 peaked at 3.685 psi above the crown, with 0 gallons over the weir. The plate is the Muse Image render already on disk. Left weir is 14.82 million gallons. Right weir is the same concrete, dry.

**2:45–3:00. Hold the counters.** Red at 14,820,000. Green at 0. OR2 still locked. The statutory ceiling on the red side is $68,445 for that day. The green side is $0.
