# StormGate-Zero

**Stop raw sewage from overflowing into city rivers during a cloudburst—using the floodgates already in the ground instead of a $300 billion concrete rebuild.**

Built for the Meta Global AI Developer Hackathon, Indie Track, theme **Push the Frontier**.

<p align="center">
  <img src="traces/nexrad/ida-2021-newark/frame_00.png" width="15%" alt="Ida 23:30 UTC" />
  <img src="traces/nexrad/ida-2021-newark/frame_02.png" width="15%" alt="Ida 00:00 UTC" />
  <img src="traces/nexrad/ida-2021-newark/frame_04.png" width="15%" alt="Ida 00:30 UTC" />
  <img src="traces/nexrad/chicago-2023-0702/frame_00.png" width="15%" alt="Chicago 21:00 UTC" />
  <img src="traces/nexrad/chicago-2023-0702/frame_01.png" width="15%" alt="Chicago 21:30 UTC" />
  <img src="traces/nexrad/chicago-2023-0702/frame_02.png" width="15%" alt="Chicago 22:00 UTC" />
</p>
<p align="center">
  <sub>Left three: IEM N0Q national mosaic over Newark during Hurricane Ida, 1–2 Sep 2021 (<code>traces/nexrad/ida-2021-newark/</code>). Right three: Chicago west side, 2 Jul 2023 (<code>traces/nexrad/chicago-2023-0702/</code>). <code>sam-3.1</code> segmented these crops in the <code>&lt;0f&gt;</code> box grammar.</sub>
</p>

---

### The problem in plain English

In more than **700 U.S. cities** (New York, Chicago, Boston, Newark, St. Louis), rainwater and household sewage share the same underground pipes. When a heavy storm hits, those tunnels fill up in minutes. To stop sewage from backing up into basements and streets, the utility opens relief weirs and dumps **850 billion gallons a year** of untreated sewage and stormwater straight into rivers, harbors, and drinking-water intakes (U.S. EPA Report to Congress `833-R-04-001`). Every day a pipe spills exposes the utility to **$68,445 per violation** under the Clean Water Act (`33 U.S.C. 1319(d)`, `40 CFR 19.4`).

Digging new storage tunnels takes 20 years and tens of billions of dollars per city. Meanwhile, the motorized sluice gates already sitting inside existing sewers are controlled by 1970s float switches: **a float switch cannot see the storm on radar.** It waits until a downstream basin is already 96% full before opening the gate—while upstream basins still have empty room—and dumps the peak of the storm over the river wall.

### What StormGate-Zero does

StormGate-Zero replaces that blind float switch with a physics-guarded control loop built on five Meta models (`sam-3.1`, `muse-spark-1.3`, `muse-wonder-1.0`, `muse-voice-transcribe-1.0`, `muse-image-1.0`) and the U.S. EPA **SWMM5** hydraulic solver:

1. **Sees the storm 45 minutes early:** `sam-3.1` tracks convective rain cores on Doppler radar (`IEM N0Q` NEXRAD mosaics) before the water hits the pavement.
2. **Pre-drains the sewer before the cloudburst arrives:** `muse-spark-1.3` sets continuous gate openings `[OR1, OR2, OR3, OR4]` every 5 minutes, emptying the downstream basin to the treatment plant ahead of the storm crest and holding early runoff in the upstream basins.
3. **Survives broken hardware:** when a field operator radios in that Sluice Gate #2 is mechanically jammed at 50%, `muse-voice-transcribe-1.0` locks that constraint in real time and `muse-wonder-1.0` computes a new gate schedule around the stuck valve.
4. **Never trusts an unsafe AI move:** every gate vector proposed by the models is simulated 60 minutes into the future across 12 parallel St. Venant hydraulic rollouts. Any move that spills a single gallon more than the physics winner is rejected before it touches the plant.

| Without StormGate-Zero (Municipal Float Switch) | With StormGate-Zero (Radar + Meta MPC + SWMM5) |
| :--- | :--- |
| Waits until Basin 4 hits **96% depth** to open the gate | Sees Core B on radar and **pre-drains Basin 4 to 14%** |
| Spills **14,820,000 gallons** of raw CSO on design storm `DS-1482` | Spills **0 gallons** (and **0 gallons** when Gate #2 jams at 50%) |
| Spills **~12.1M gal** on the Newark Ida radar mosaic & **~13.7M gal** on Chicago | Spills **0 gallons** on both radar mosaics |
| Triggers the **$68,445 / day** Clean Water Act statutory ceiling | **$0** statutory exposure · kept schedule peaks at **3.539 psi** on Junction `J3` |

---

## The scorecard

| Forcing on the 4-basin interceptor | What the tape is | Municipal float switch | All gates wide open | **StormGate-Zero** |
| --- | --- | ---: | ---: | ---: |
| **DS-1482** (design storm) | 90 min, 18 × 5-min steps, played in ~20 s | **14,820,000 gal** | ~3,100,000 gal | **0 gal** |
| **DS-1482 + OR2 jammed at 50%** | Sluice #2 mechanically locked from minute 40 | 14,820,000 gal | — | **0 gal** |
| **Hurricane Ida mosaic** (menu) | IEM N0Q crops, Newark, 1 Sep 2021, 23:30–00:45 UTC | ~12,096,528 gal | — | **0 gal** |
| **Chicago 2 Jul 2023 mosaic** (menu) | IEM N0Q crops, west side, 21:00–23:30 UTC | ~13,673,729 gal | — | **0 gal** |
| **Newark 3.24 in/hr gauge hour** | Saturation check: 8–9 p.m. local cloudburst hour | ~52.8 million gal | — | **~26.2 million gal** |
| **Chicago gauge hour** | Saturation check: gauge-shaped cloudburst hour | ~24.5 million gal | — | **~9.2 million gal** |

* **Why the float switch is worse than leaving the gates open:** the municipal float holds OR4 at 2% until Basin 4 is at 96% of crown, then throws it to 100%. It stores the first wave and dumps the second over the river weir. Leaving every gate open lets the treatment plant pass a flatter hydrograph (~3.1M gal spilled instead of 14.82M). StormGate-Zero pre-drains Basin 4 before the second convective core arrives and holds the crest off the weir.
* **Why the Newark 3.24 in/hr row still spills ~26.2M gal:** real tunnels have finite concrete volume. The mosaic menu plays the IEM palette rainfall, which sits below the gauge peak and holds at 0 gallons. The gauge-shaped reconstruction of Newark's published 3.24 in hour exceeds physical storage. A controller that claimed 0 gallons on that hour would be faking the mass balance.
* **Statutory exposure:** any combined-sewer overflow above 0 gallons triggers the **40 CFR 19.4** Clean Water Act civil penalty ceiling of **$68,445 per day per violation** (33 U.S.C. 1319(d), penalties assessed on or after 8 Jan 2025). The board's *E. coli* readout dilutes a planning density of `1,000,000 CFU / 100 mL` into `10,000,000 gallons` of receiving water against the EPA 2012 beach action value (`235 CFU / 100 mL`).
* **Dynamic-wave check:** `verify_dynamic_wave` runs SWMM5 `DYNWAVE` on the committed gate schedule. The kept `muse-spark-1.3` refine schedule on DS-1482 peaks at Junction **J3, 3.539 psi** above the crown. The pure pre-drain law on that same storm peaks at **J1, 2.51 psi**. The Ida mosaic peaks at **J1, 3.338 psi**. The Chicago mosaic peaks at **J4, 1.846 psi**. The double-lock schedule below peaks at **J3, 5.306 psi**. Level-pool gallons and these heads are two different checks.

## Where a named control law loses

DS-1482 scaled by 2.2, with OR1 locked at 5% and OR2 locked at 90% from minute 20. A receding-horizon search over continuous openings `[OR1, OR2, OR3, OR4]` — the same kind of vector `muse-spark-1.3` is allowed to return — is scored on the level-pool plant. The four named laws are scored on that same plant. The search is not a hosted model call. The hosted calls, and the steps the physics guard rejected, stay in `traces/recorded_refine_pass.json`.

| Controller | River spill | Street flood |
| --- | ---: | ---: |
| Municipal float switch | 26,498,221.5 gal | 0 |
| A-predrain (the hand-written StormGate law) | 8,534,246.3 gal | 897,741.2 gal |
| B-balanced (best of the four named laws) | 4,358,862.8 gal | 0 |
| Searched continuous schedule | **0 gal** | **0** |

Across 100 deterministic shears of DS-1482, each crossed with one of four mechanical locks, that search **never** spilled more than the best named law. It beat the best named law on **14** scenarios and tied the other **86** within a gallon. Against the float switch, the 100 tapes are **1,716,996,992.5 gallons** less river overflow. The rows, the hash chain, and the PySWMM heads are in `traces/stress_matrix_100.json`, `traces/compound_fault.json`, `traces/wave_storms.json`, and `traces/compliance_ledger.json`. Changing one gallon breaks the next SHA-256 link.

Open-weight `muse-spark-open` is not called in these files. Set `BREV_BASE_URL` and `BREV_API_KEY` after the weights are up on NVIDIA Brev. Until a response comes back from that endpoint, the repo does not claim an open-weight trace.

---

## Five Meta models on one causal path

Nothing in this app is a side tab. Every model feeds the gate command or the operator verification of that command.

```
IEM N0Q NEXRAD mosaic / DS-1482 field         SCADA war-room audio (WAV)
                 |                                        |
                 v                                        v
     sam-3.1 (POST /v1/responses)             muse-voice-transcribe-1.0
     <0f> boxes + RLE masks ∩ basins          POST /v1/asr/transcribe
                 |                            "Sluicegate 2 ... jammed at 50%"
                 +------------------+---------------------+
                                    |
                                    v
                 12 parallel 60-min St. Venant rollouts
                 A-predrain · B-balanced · C-retention · D-bypass
                                    |
                                    v
                 muse-spark-1.3  —  Turn 1 continuous [OR1..OR4]
                 muse-spark-1.3  —  Turn 2 score-conditioned refine
                                    |
                                    v
                 muse-wonder-1.0 —  jammed-gate MPC recovery (OR2 = 0.50)
                                    |
                                    v
                 Physics ranker + local freeboard interlock
                 (depth > 92% & inflow > 35 mm/hr -> force >= 60%)
                                    |
                   +----------------+----------------+
                   v                                 v
        Actuate OR1..OR4 on the plant       muse-image-1.0
        PySWMM DYNWAVE check on finish      Outfall visual twin (once)
        kept schedule J3 = 3.539 psi        14.82M gal weir vs. dry weir
```

| Model | Endpoint | Recorded proof in `traces/` |
| --- | --- | --- |
| **`sam-3.1`** | `POST /v1/responses` | DS-1482: boxes + masks at `t=40` (`[0.3792, 0.4813, 0.5417, 0.6417]`) and `t=55` (`[0.5229, 0.6083, 0.6771, 0.7604]`) in `<0f>0<\|box;x1=…\|>` grammar. Hurricane Ida mosaic: storm boxes on **4 of 6** frames. Chicago mosaic: yellow-core boxes on **5 of 6** frames (`[12, 10, 10, 0, 2, 10]` objects). |
| **`muse-spark-1.3`** | `POST /v1/responses` | Continuous `[u1, u2, u3, u4]` on keys `0\|`..`17\|` (17/18 live during the scored pass; step 16 later recorded as `resp_6ae8fa47aad163f2f96b446b`). Second-turn refinement on 17/18 steps in `traces/recorded_refine_pass.json`: **15 kept, 2 rejected by physics, 1 null**. |
| **`muse-wonder-1.0`** | `POST /v1/responses` | Fired on the step-8 mechanical jam with `reasoning.effort = "low"`. Returned `u = [0.04, 0.50, 0.04, 0.6209]` (`resp_6ae9adeac24e0d3e800f40f3`, `6.50 s`), holding `OR2` at the lock and opening `OR4` to `0.6209`. |
| **`muse-voice-transcribe-1.0`** | `POST /v1/asr/transcribe` | Multipart `request` + 16 kHz mono WAV `audio` (`audioEncoding: "WAV"`, `mode: "DIARIZATION"`). Transcribed: *"Operator 4, Sluicegate 2 is mechanically jammed at 50% open."* Parser locks `OR2 = 0.50`. |
| **`muse-image-1.0`** | `POST /v1/responses` | Rendered the side-by-side outfall plate once (`image_generation_call` WebP converted to PNG and locked behind `data/outfall/.muse_spent` so loops never re-bill). |
| **Local freeboard interlock** | Deterministic (`glimmer_edge_guard.py`) | If `depth > 92%`, `inflow > 35 mm/hr`, and a gate is pinched below `25%`, force it to `60%` unless mechanically jammed. Above `97%` depth, force `100%`. (`api.meta.ai` returns `model_not_found` for `meta-models/Muse-Glimmer-30B` and `meta-models/muse-spark-open`, so the edge interlock runs locally in Python on every step.) |

---

## Run it in 60 seconds (no API key required)

`STORMGATE_REFINE` defaults to `0`, and `traces/live_models.json` is committed. A judge can clone the repo without a Meta key and watch the exact recorded responses drive the plant.

```bash
git clone https://github.com/brian-mwirigi/stormgate-zero.git
cd stormgate-zero
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # leave MODEL_API_KEY blank for replay mode
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

Open **`http://localhost:5173`**.

```bash
python -m pytest tests -q
```

**`16 passed`**, offline (`STORMGATE_OFFLINE=1` in `tests/conftest.py`). The suite locks:
1. `14,820,000 gal` float-rule spill on DS-1482.
2. `0 gal` StormGate-Zero spill on DS-1482, both clean and with `OR2` jammed at `0.50`.
3. All-gates-open spilling less than the float switch.
4. Pre-drain ranking ahead of balanced/retention/bypass.
5. The `<0f>` object-multiplex grammar and radio fault parser.
6. IEM N0Q palette anchors (`index 150 → 45 dBZ`, `index 170 → 55 dBZ`).
7. Live 60-dBZ cell drop mutating the active runoff tape.
8. Statutory ceiling (`$0` at `0 gal`, `$68,445` above `0 gal`).
9. `keep_refinement` rejecting any second-turn vector more than 1 gallon above the physics winner.
10. `PySWMM` dynamic-wave verification returning node surcharge and three conduit fills.

---

## Repository map

```text
backend/
  config.py                         Model IDs, GIS subcatchments, STORMGATE_REFINE flag
  episode.py                        20-second twin loop, storm switching, DYNWAVE trigger
  main.py                           FastAPI + /ws/twin WebSocket + /api/storm & /api/verify/wave
  physics/
    design_storm.py                 DS-1482 two-core storm and VOLUME_SCALE calibration
    storm_catalog.py                Active forcing (ds-1482, Ida, Chicago, click-to-drop 60 dBZ)
    nexrad_mosaic.py                IEM N0Q archive downloader, 0.005° world-file crop, Z-R
    swmm_engine.py                  4-basin level-pool St. Venant plant + 12 parallel rollouts
    dynamic_wave.py                 PySWMM DYNWAVE heads, kept schedule J3 = 3.539 psi
    frontier.py                     100-scenario search against the four named laws
    compliance_ledger.py            SHA-256 chain over those measured files
    exposure.py                     33 U.S.C. 1319(d) $68,445/day ceiling + E. coli dilution
  agents/
    sam_radar_tracker.py            sam-3.1 <0f> prompt builder + <|box;...|><|mask;...|> parser
    spark_open_worker.py            muse-spark-1.3 Turn-1 vector + Turn-2 score-conditioned refine
    wonder_mpc_supervisor.py        Ranker, keep_refinement physics guard, muse-wonder-1.0 jam call
    glimmer_edge_guard.py           Local freeboard interlock (>92% depth & >35 mm/hr -> >=60%)
    voice_scada_bridge.py           16 kHz WAV converter, /v1/asr/transcribe, OR2 jam parser
    image_counterfactual.py         muse-image-1.0 outfall plate with single-spend lock
    meta_client.py                  Windows system trust store TLSv1.3 client for api.meta.ai
    model_traces.py                 Zero-rebill replay cache loader/writer
frontend/
  src/App.tsx                       SCADA command center, forcing selector, DepthStrip readout
  src/components/RadarSamCanvas.tsx NEXRAD frame viewer, <0f> SAM overlays, click-to-drop cell
  src/components/HydraulicTwin.tsx  Dual 4-basin HGL profile and orifice bars
traces/
  recorded_refine_pass.json         18-step Turn-1 -> Turn-2 -> solver accept/reject log + Wonder jam
  recorded_live_pass.json           First scored Spark (17/18), SAM (t=40,55), and Voice pass
  live_models.json                  Full replay cache used by the running server
  nexrad/                           Ida & Chicago 480x480 N0Q crops, meta.json, and rain.npy
tests/
  test_hydraulics.py                14.82M vs 0 gal, jam resilience, rollout ranking
  test_parsers.py                   <0f> grammar round-trip and radio fault extraction
  test_depth.py                     Mosaic Z-R, cell drop, $68,445 ceiling, refine guard, PySWMM wave
```
