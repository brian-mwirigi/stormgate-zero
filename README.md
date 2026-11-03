# StormGate-Zero

**Closing the perception-to-physics loop: autonomous urban combined sewer overflow control via Meta SAM 3.1, Muse Wonder 1.0, Muse Spark Open, Muse Glimmer, and the US EPA SWMM St. Venant solver.**

Built for the Meta Global AI Developer Hackathon, Indie Track, theme "Push the Frontier". Submission deadline Wednesday, November 4, 2026, 9:00 PM EST.

## Submission blurb

StormGate-Zero closes a single causal loop from radar reflectivity to continuous orifice actuation on a four-basin combined sewer. On the 90-minute design storm DS-1482 (18 five-minute steps played in about 20 seconds), the municipal float switch spills 14,820,000 gallons. An all-gates-open plant spills about 3.1 million. Either spill exposes the utility to the 40 CFR 19.4 Clean Water Act statutory ceiling of $68,445 per day per violation (33 USC 1319(d), penalties assessed on or after 8 Jan 2025). StormGate-Zero pre-drains Basin 4 ahead of the second convective core and spills 0 gallons, including when sluice OR2 jams at 50% open. Twelve 60-minute futures are scored on a level-pool St. Venant storage routing. PySWMM then runs the committed schedule as a SWMM5 dynamic wave. On the finished DS-1482 pass, junction J3 peaked at 3.685 psi above the crown.

`muse-spark-1.3` returns a continuous opening `[u1, u2, u3, u4]`. The four named strategies are the physics audit, not a menu the model picks from. A second turn, captured in `traces/recorded_refine_pass.json`, mutates that vector after it sees the rollout scores. The solver kept 15 of 18. It rejected step 7 and step 11 because they spilled more. Step 10 returned no vector. The kept sequence still spills 0 gallons. Putting the two rejected vectors back in spills about 3.4 million. `STORMGATE_REFINE` defaults off, so the live loop replays that file and does not bill again.

Operators can switch the forcing. The Ida and Chicago entries play real IEM N0Q mosaic frames. `sam-3.1` returned storm boxes on 4 of 6 Ida crops and yellow-core boxes on 5 of 6 Chicago crops. Quadrant rainfall from that palette spills about 12.1 million gallons on the Ida float switch and about 13.7 million on the Chicago float switch. The same pre-drain law holds both at 0, because those palette rates sit below the published cloudburst hour. The gauge-shaped reconstruction of Newark's 3.24 in hour (8–9 p.m., 1 Sep 2021) still overflows this plant by about 26.2 million gallons under StormGate. The Chicago gauge shape spills about 9.2 million. A click on the radar drops a 60 dBZ cell through the same Z-R. None of these tapes is a Level-II volume scan or those cities' sewers.

`sam-3.1` also segmented the DS-1482 tape at minutes 40 and 55. `muse-voice-transcribe-1.0` transcribed the radio line that locks OR2 at 50%. `muse-wonder-1.0` answered that jam with its own opening, OR4 at 0.62 and OR2 held at 0.50 (`resp_6ae9adeac24e0d3e800f40f3`). `muse-image-1.0` rendered the outfall plate once. A local freeboard interlock forces a pinched gate open above 92% depth and 35 mm/hr unless the valve is mechanically locked. The E. coli figure dilutes a planning density into 10 million gallons of receiving water. It is not a grab sample. Later loops replay `traces/live_models.json` and `traces/recorded_live_pass.json`.

## 1. The frontier problem

According to the U.S. Environmental Protection Agency Report to Congress (EPA 833-R-04-001), more than 700 U.S. municipalities experience about 43,000 combined sewer overflow events every year. Those events discharge on the order of 850 billion gallons of untreated sewage and stormwater, and hundreds of millions of pounds of pollutants, into rivers, lakes, and coastal waters.

Replacing the concrete is a multi-hundred-billion-dollar program. During a cloudburst the gates that already exist are usually blind: a downstream basin overflows while an upstream basin still has room, because the float switch only moves after the water is at the crown.

Two gaps kept earlier PySWMM controllers (deep RL, LQR) off real plants:

1. **Spatial blindness.** A rain-gauge number arrives after the water is on the ground. A convective core is a 2-D object moving across subcatchments, and it is visible on NEXRAD tens of minutes earlier.
2. **Black-box liability.** A civil engineer cannot hand a floodgate to a network that cannot say why it is pre-draining Basin 4, and cannot recover when a sluice jams.

StormGate-Zero puts SAM 3.1 object multiplex on the Doppler radar tape and wires Muse Wonder, Muse Spark Open, and Muse Glimmer into a 1-D St. Venant storage routing of a four-basin interceptor. The law targets a 12% pre-drain on the downstream basin and a 91% crest. On design storm DS-1482 the 5-minute level-pool step realizes a 14% minimum and a 93% crest. The municipal float-rule weir integrates to **14,820,000 gallons**. StormGate-Zero integrates to **0 gallons**, including a case where orifice OR2 jams at 50% open at minute 40.

## 2. One causal pipeline

Every model sits on the actuation path. Nothing is a disconnected tab.

```
NOAA-style NEXRAD MP4                         SCADA war-room audio
        |                                              |
        v                                              v
 SAM 3.1  POST /v1/responses                Muse Voice Transcribe 1.0
 object multiplex, or Frame-0 <0f> boxes    wss /v1/asr/realtime  +  POST /v1/asr/transcribe
 masks ∩ GIS subcatchments                  speaker turns -> valve-jam constraints
        |                                              |
        +---------------- 45-min runoff vector -------+
                                 |
                                 v
                    Muse Wonder 1.0  supervisory MPC
                    hosted on the OR2 jam, physics guard
                                 |
                                 v
                    muse-spark-1.3
                    live orifice vector [u1, u2, u3, u4]
                    scored against 4 library rollouts
                                 |
                                 v
                    Muse Glimmer
                    local freeboard interlock
                                 |
                +----------------+----------------+
                v                                 v
     St. Venant storage routing          Muse Image 1.0
     SU1..SU4, OR1..OR4, OF1..OF4        anchored outfall twin
     14,820,000 gal -> 0 gal
```

The quantitative hyetograph on the demo tape is the calibrated Z-R product of design storm DS-1482. SAM's job on that tape is the tracked core. The recorded pass called `sam-3.1` on the frames at 0, 40, and 55 minutes. Minutes 40 and 55 returned a storm box and a mask blob (`<0f>` plus the pipe-box grammar). Minute 0 came back empty, so that instant still draws the geometric core. The live board does not send the MP4 on every frame. With no key, or after the trace is on disk, the loop replays `traces/live_models.json`: the same Spark vectors, the same SAM boxes, the physics ranker, the local freeboard invariant, and the cached outfall plate.

### Recorded live pass

`traces/recorded_live_pass.json` is the frozen artifact from that run. The server replays the same bytes from `traces/live_models.json`, so a looping board does not bill the same step again.

| Model | What the file shows |
| --- | --- |
| `muse-spark-1.3` | An orifice vector, commentary, latency, and `resp_*` id on every step key `0\|` through `17\|`. The scored pass executed the model on 17 steps. Step 16 of that pass fell back to A-predrain when the call did not return; controlled spill stayed 0 gallons. A later successful step-16 response is in the file (`resp_6ae8fa47aad163f2f96b446b`, about 22.9 s). |
| `sam-3.1` | `ok: true`, 8609.6 ms, three frames. t=40 box `[0.3792, 0.4813, 0.5417, 0.6417]`. t=55 box `[0.5229, 0.6083, 0.6771, 0.7604]`. t=0 excerpt is empty. |
| `muse-voice-transcribe-1.0` | Transcript: "Operator 4, Sluicegate 2 is mechanically jammed at 50% open." Parsed fault: OR2 locked at 0.50. |
| `muse-wonder-1.0` | `wonder` is `{}` in this file because the 18-step recording was unjammed. On a jam, Wonder is called once and its vector is kept only when the rollout spills no more than the physics winner. |
| `muse-image-1.0` | Rendered the outfall plate once, before this pass. The board serves that PNG. It is not regenerated on replay. |

Hosted Spark is asked for `{"u":[or1,or2,or3,or4],"intent_commentary"}` on `POST /v1/responses`. The ranker still prefers the lowest spill, then street flooding, then W-wonder, S-spark, and names starting with A-. A hosted pick that spills more than the physics winner is dropped. Wonder fires once per process, on the first beat after OR2 jams, with `reasoning.effort = low`. Muse Image fires once per install. The response is an `image_generation_call` WebP, converted to PNG, then served again without another call. On this machine `httpx` had to use the Windows certificate store. The certifi bundle failed TLS with `CERTIFICATE_VERIFY_FAILED` before any model ran. That client lives in `backend/agents/meta_client.py`. Glimmer is still the local numeric interlock. `api.meta.ai` returns `model_not_found` for `meta-models/muse-spark-open` and `meta-models/Muse-Glimmer-30B`.

## 3. Prize-track alignment

| Prize track | How this build qualifies |
| --- | --- |
| Indie Grand Prize | Closed-loop vision-to-PDE control of an interceptor. On DS-1482 the float-rule baseline spills 14.82 million gallons and StormGate-Zero spills none, including a mid-storm mechanical jam. |
| Best build on Meta open-weight models | The live control step calls hosted `muse-spark-1.3` for the orifice vector, then still scores the Spark Open library (A-predrain, B-balanced, C-retention, D-bypass) and the Glimmer freeboard invariant locally. The partner model string is `meta-models/muse-spark-open` (Baseten base `https://inference.baseten.co/v1`, Groq base `https://api.groq.com/openai/v1`). `api.meta.ai` returns `model_not_found` for that id and for `meta-models/Muse-Glimmer-30B`. A Groq key on this machine returns `model_terms_required` until the org accepts terms. The numeric interlock still runs on every step. |
| Best agentic use | `muse-spark-1.3` proposes `[u1, u2, u3, u4]` every control step. Wonder adds a recovery vector when voice transcription locks OR2 at 0.50. Both are scored on cloned 60-minute St. Venant rollouts and dropped if they spill more than the physics winner. |
| Best creative build | Image 1.0 anchored composition, with a solver-locked fallback plate, turns the hydrograph into a side-by-side outfall: raw sewage versus a dry weir. |
| Most viral on X | The command center is the shot: red weir versus a dry weir, SAM masks on the radar, a jam injected by voice, the counter stuck at 0 gal. |

## 4. Repository map

```
backend/config.py                         keys, model ids, GIS polygons
backend/physics/swmm_engine.py            dual plant, rollouts, SWMM .inp
backend/physics/design_storm.py           DS-1482 hydrograph and radar cores
backend/physics/radar_synthesizer.py      NEXRAD frames and MP4
backend/agents/sam_radar_tracker.py       SAM 3.1 stream + <0f> parser + HSV seed
backend/agents/wonder_mpc_supervisor.py   supervisory MPC
backend/agents/spark_open_worker.py       muse-spark-1.3 vector + four library trajectories
backend/agents/glimmer_edge_guard.py      freeboard interlock
backend/agents/voice_scada_bridge.py      realtime proxy, file ASR, fault parser
backend/agents/image_counterfactual.py    anchored outfall plate
backend/agents/model_traces.py            replay cache for api.meta.ai responses
backend/main.py                           FastAPI + WebSocket twin
frontend/                                 React SCADA command center
scripts/generate_demo_assets.py           radar MP4, reference plate, .inp
scripts/record_live_models.py             one DS-1482 pass that fills the trace
scripts/run_benchmark.py                  uncontrolled vs local vs StormGate
traces/recorded_live_pass.json            frozen Spark, SAM, and Voice payloads
traces/live_models.json                   the same payloads, replayed by the server
```

## 5. Quickstart

Python 3.10+ and Node.js 20+. A Meta key is optional; the design storm runs without one.

```bash
cd stormgate-zero
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # set MODEL_API_KEY if you have one
python scripts/generate_demo_assets.py
python scripts/run_benchmark.py
uvicorn backend.main:app --reload --port 8000
```

Second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The episode auto-starts. Inject the OR2 jam from the bottom bar, then render the outfall twin.

PySWMM is listed and the `.inp` is a real SWMM5 network. The live MPC fan-out uses level-pool continuity (the storage-node routing inside SWMM) so twelve clones finish inside a control step even when the EPA dynamic-wave DLL is not installed. `commit_with_pyswmm` replays a committed orifice series when the engine imports.

## 6. Three-minute demo

DS-1482 finishes 18 steps, 90 simulated minutes, in about 20 seconds, then loops. Record one clean loop, then the jam, then the plate and the tests. Reset the storm before you hit record so Loop 1 starts at minute 0.

**Loop 1, 0:00–0:25.** Leave the jam off. Let the board run from the opening frame to the lock.

> The left sewer is the municipal float switch. It leaves the upstream gates open and holds the downstream gate shut until the tank is already at the crown. The right sewer sees Core A on Basin 1, spends the plant before the rain, and drops Basin 4 before Core B arrives around minute 55. The counters are whole gallons. They lock at 14,820,000 on the left and 0 on the right. An all-gates-open plant spills about 3.1 million. The float switch is worse, because it stores the peak and then dumps it over the weir.

**Loop 2, 0:25–1:35.** As the loop restarts, before Core B reaches Basin 4, press **Inject Gate #2 Mechanical Jam (50%)**. That button parses the radio line. It does not invent a second code path.

> Sluice Gate 2 is mechanically jammed at 50 percent. The recorded voice pass already transcribed that line and locked OR2 at 0.50. Wonder gets one call on the jam, and it may only keep a plan whose rollout spills no more than the physics winner. A jammed gate cannot be moved. Glimmer is the local interlock under that plan: above 92 percent full, inflow over 35 millimeters an hour, and a gate pinched below 25 percent, the gate is forced to 60 percent. The green counter stays at 0.

**Outfall and proof, 1:35–2:45.** Press **Render Outfall Visual Twin**. The plate is the Muse Image render already on disk. Then cut to a terminal.

> Left weir is the 14.82 million gallons the float switch discharged. Right weir is the same concrete, dry. `muse-spark-1.3` wrote the gate openings on 17 of the 18 steps in `traces/recorded_live_pass.json`. The solver kept them because they did not spill more than the physics winner. Glimmer is the local check that can veto a pinched gate. The cloud proposes the number. It does not get to move a gate the physics rejected.

```bash
python -m pytest tests -q
python scripts/run_benchmark.py
```

Nine tests pass. The benchmark prints uncontrolled, local, StormGate, and StormGate with OR2 jammed.

**Close, 2:45–3:00.** Back to the board. Red counter at 14,820,000. Green counter at 0. OR2 still locked.

## 7. What the solver is

Four storage units on a short interceptor. Upstream orifices OR1–OR3 discharge into SU4. SU4's orifice is capped by the treatment plant. Above full depth, SU4 spills to the river (CSO) and SU1–SU3 spill to the street. The municipal baseline leaves upstream gates open and holds OR4 shut until the basin is at 96% — the float switch that reacts after the tank is already gone. StormGate does the opposite: it spends plant capacity before the rain, holds the upstream basins near 86%, and lets SU4 refill toward a 91% crest instead of the weir.

Volume, orifice capacity, plant capacity, and runoff are scaled together so depths stay on that path and the float-rule integral is exactly 14,820,000 gallons. That scale is `VOLUME_SCALE` in `backend/physics/design_storm.py`.

The live fan-out is twelve cloned 60-minute level-pool rollouts per control step, which is why the board stays on a 1.15-second beat. `write_interceptor_inp` writes a real SWMM5 network, and `commit_with_pyswmm` replays a committed orifice series on the EPA dynamic-wave engine when that DLL imports. PySWMM is installed here. The scorecard the tests lock is the level-pool integral, not a second hidden counter.
