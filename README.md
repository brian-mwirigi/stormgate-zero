# StormGate-Zero

### **14,820,000 gallons spilled → 0 gallons spilled.**
**Even when sluice gate OR2 jams at 50% open at minute 40.**

Radar reflectivity goes in. Continuous orifice openings `[OR1, OR2, OR3, OR4]` come out. A 60-minute level-pool St. Venant lookahead checks every vector the model proposes and drops any move that spills more than the physics winner. When the 90-minute storm finishes, **PySWMM 2.2.0** runs the committed gate schedule as a full **SWMM5 dynamic wave**: Junction **J3 peaks at 3.685 psi** above the crown, and the weir stays dry.

Built for the **Meta Global AI Developer Hackathon** (Indie Track, *Push the Frontier*).

---

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
* **Dynamic-wave check:** on the finished 18-step DS-1482 schedule, `verify_dynamic_wave` runs SWMM5 `DYNWAVE` (20-second routing step). Worst node is Junction **J3 at 3.685 psi** above the crown, with 0 gallons spilled.

---

## Why a judge should believe this repo

Most agent demos let the language model narrate a win. Here the model's own mistakes are checked into git, and the solver catches them.

Open [`traces/recorded_refine_pass.json`](traces/recorded_refine_pass.json). On every 5-minute step of DS-1482:

1. **Turn 1 (`muse-spark-1.3`):** proposes a continuous gate vector `u = [OR1, OR2, OR3, OR4]`.
2. **Physics audit:** runs 12 parallel 60-minute level-pool trajectories (`A-predrain`, `B-balanced`, `C-retention`, `D-bypass`, plus the model's vector).
3. **Turn 2 (`muse-spark-1.3`):** sees the rollout scores and mutates `u`.
4. **The guard:** keeps Turn 2 only if its 60-minute lookahead spills within 1 gallon of the physics winner.

Across the 18 steps, the solver **accepted 15** Turn-2 vectors, **rejected 2** (`step 7` and `step 11`), and fell back on **1** (`step 10`, where Turn 2 returned no vector). Look at `step 11` in the file:

```json
{
  "step": 11,
  "turn1": {
    "model": "muse-spark-1.3",
    "u": [1.0, 1.0, 1.0, 1.0],
    "response_id": "resp_6ae8f9065afd862bf9544fcb"
  },
  "turn2": {
    "model": "muse-spark-1.3",
    "turn": 2,
    "u": [0.08, 0.06, 0.05, 0.0087],
    "intent_commentary": "Slightly opening upstream gates to trim peak storage while holding downstream to preserve zero overflow.",
    "latency_ms": 17150.0,
    "response_id": "resp_6ae9ad396726d96c8d724c8e"
  },
  "solver": "rejected-spilled-more"
}
```

Look at what the model tried to do on Turn 2: it pinched the treatment-plant orifice `OR4` down to `0.0087` while the text claimed *"preserve zero overflow."* The 60-minute St. Venant rollout proved that pinching `OR4` there overflows the weir later in the storm, so the guard rejected `resp_6ae9ad396726d96c8d724c8e` on the spot.

* **Replaying the 15 kept vectors** (with `S-spark` on step 7 and `A-predrain` on steps 10–11): **0 gallons spilled.**
* **Forcing all 17 raw Turn-2 vectors into the plant** (ignoring the guard on steps 7 and 11): **3,409,695 gallons spilled.**

That 3.41-million-gallon gap is the difference between an LLM wrapper and a physics-guarded controller.

And when the operator radio call locks Sluice Gate 2 at 50% open at step 8, **`muse-wonder-1.0`** computes the recovery in one shot (`resp_6ae9adeac24e0d3e800f40f3`, `6495.4 ms`):

```json
{
  "model": "muse-wonder-1.0",
  "u": [0.04, 0.5, 0.04, 0.6209],
  "selected": "W-wonder",
  "recovery_note": "With OR2 jammed at 0.5, the winner compensates by holding OR1 and OR3 at 0.04 to keep flow stored in SU1 and SU3 rather than overloading the interceptor through the stuck opening. It also opens OR4 to 0.6209 to pre-drain Basin 4, creating downstream capacity before the peak arrives.",
  "latency_ms": 6495.4,
  "response_id": "resp_6ae9adeac24e0d3e800f40f3"
}
```

---

## Cerebral Valley submission copy

StormGate-Zero closes a single causal loop from radar reflectivity to continuous orifice actuation on a four-basin combined sewer ([github.com/brian-mwirigi/stormgate-zero](https://github.com/brian-mwirigi/stormgate-zero)). On the 90-minute design storm DS-1482 (18 five-minute steps played in 20s), the municipal float switch holds the downstream orifice shut until the crown and spills 14,820,000 gallons (and 3.1M gallons with all gates wide open), triggering the 40 CFR 19.4 Clean Water Act statutory ceiling of $68,445 per day per violation (33 U.S.C. 1319(d)). StormGate-Zero pre-drains Basin 4 ahead of the second convective core and spills 0 gallons—including when sluice gate OR2 mechanically jams at 50% mid-storm. Operators can switch the board to real radar mosaic frames from Hurricane Ida (spilling ~12.1M gal under the float switch vs. 0 gal with StormGate-Zero) and the July 2023 Chicago flood (where `sam-3.1` tracks yellow-core boxes across 5 of 6 frames, cutting a ~13.7M gal float spill to 0 gal), or click the radar to drop a live 60-dBZ cell; separate gauge-shaped saturation hours (including Newark's 3.24 in/hr Ida peak at ~26.2M gal and Chicago's gauge hour at ~9.2M gal) benchmark physical storage limits beyond plant capacity. In `traces/recorded_refine_pass.json` against `api.meta.ai/v1`, `sam-3.1` segments storm cores in the `<0f>` grammar, `muse-spark-1.3` generates Turn-1 continuous orifice openings and Turn-2 score-conditioned refinements across the 18-step pass (with the physics guard keeping 15 refinements, rejecting steps 7 and 11 for higher spill, and handling a null vector on step 10 to hold 0 gallons spilled), `muse-voice-transcribe-1.0` transcribes the radio fault locking OR2 at 50%, `muse-wonder-1.0` computes the jammed recovery vector (holding OR2 at 0.50 and setting OR4 to 0.62), and `muse-image-1.0` renders the solver-locked outfall plate. A local freeboard interlock overrides pinched gates above 92% depth and 35 mm/hr inflow unless mechanically locked, and `PySWMM` dynamic-wave verification on the completed DS-1482 schedule confirms Junction J3 peaks at 3.685 psi above crown with 0 gallons spilled. Subsequent loops replay the captured traces with `STORMGATE_REFINE=0` by default for zero-key reproducibility.

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
        J3 = 3.685 psi · 0 gal CSO          14.82M gal weir vs. dry weir
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

## Three-minute judge walkthrough

DS-1482 runs 18 five-minute steps in ~20 seconds and loops. Click **Reset** before recording so Loop 1 starts at `t = 0 min`.

* **0:00–0:25 — 14,820,000 vs. 0.** Leave the jam off. Watch the left twin (municipal float switch) hold `OR4` at 2% while upstream basins fill, then dump **14,820,000 gallons** over the weir when Core B hits at minute 55. Watch the right twin (`muse-spark-1.3` + St. Venant lookahead) pre-drain Basin 4 down toward 14% before the core arrives and crest near 93% with **0 gallons** spilled.
* **0:25–1:10 — Jam Sluice Gate #2 at 50%.** On the restart, before minute 40, click **Inject Gate #2 Mechanical Jam (50%)**. That feeds the exact radio line transcribed by `muse-voice-transcribe-1.0`. `OR2` locks at `0.50`. At step 8, `muse-wonder-1.0` holds `OR1` and `OR3` at `0.04` and opens `OR4` to `0.6209` (`resp_6ae9adeac24e0d3e800f40f3`). The green counter stays at **0**.
* **1:10–2:10 — Switch to Hurricane Ida & Chicago, then drop a 60-dBZ cell.** Use the forcing selector in the top bar:
  * **Ida (1 Sep 2021, Newark):** real IEM N0Q mosaic frames; float switch spills `~12.1M gal`, StormGate-Zero holds **`0 gal`**.
  * **Chicago (2 Jul 2023):** `sam-3.1` yellow-core boxes on 5 of 6 frames; float switch spills `~13.7M gal`, StormGate-Zero holds **`0 gal`**.
  * **Click anywhere on the radar canvas** to drop a live **60-dBZ** convective cell through the Marshall-Palmer Z-R converter (`I = (10^(dBZ/10) / 200)^(1/1.6)`).
* **2:10–3:00 — Dynamic-wave surcharge, statutory fine, and Outfall Twin.** Let a DS-1482 pass complete and read the depth strip below the hydraulic twin:
  * **Level-pool CSO:** `14,820,000 gal` vs. `0 gal`.
  * **40 CFR 19.4 ceiling:** `$68,445 / day` exposed vs. `$0`.
  * **PySWMM DYNWAVE:** Junction **`J3` at `3.685 psi`** above crown.
  * Click **Render Outfall Visual Twin** to open the `muse-image-1.0` plate comparing the overflowing weir against the dry controlled wall.

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
    dynamic_wave.py                 PySWMM 2.2.0 SWMM5 DYNWAVE verification (J3 = 3.685 psi)
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
