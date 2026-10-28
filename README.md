# StormGate-Zero

**Closing the perception-to-physics loop: autonomous urban combined sewer overflow control via Meta SAM 3.1, Muse Wonder 1.0, Muse Spark Open, Muse Glimmer, and the US EPA SWMM St. Venant solver.**

Built for the Meta Global AI Developer Hackathon, Indie Track, theme "Push the Frontier".

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
                    reasoning.effort = high
                                 |
                                 v
                    Muse Spark Open
                    4 PySWMM / level-pool rollouts
                    + intent commentary channel
                                 |
                                 v
                    Muse Glimmer 30B
                    local freeboard interlock
                                 |
                +----------------+----------------+
                v                                 v
     St. Venant storage routing          Muse Image 1.0
     SU1..SU4, OR1..OR4, OF1..OF4        anchored outfall twin
     14,820,000 gal -> 0 gal
```

The quantitative hyetograph on the demo tape is the calibrated Z-R product of design storm DS-1482. SAM's job on that tape is the tracked core, the `<0f>` seed, and the polygon intersection the operator sees. Hosted models are called when `MODEL_API_KEY` is set. With no key, the same loop still runs: geometric box seeding, the physics ranker, the local freeboard invariant, and a solver-locked outfall plate. A hosted pick that would spill more than the physics winner is rejected.

## 3. Prize-track alignment

| Prize track | How this build qualifies |
| --- | --- |
| Indie Grand Prize | Closed-loop vision-to-PDE control of an interceptor. On DS-1482 the float-rule baseline spills 14.82 million gallons and StormGate-Zero spills none, including a mid-storm mechanical jam. |
| Best build on Meta open-weight models | Spark Open proposes and explains the rollout library. Glimmer is the single-GPU edge interlock that can veto a pinched gate when depth is above 92% and inflow exceeds 35 mm/hr. Both talk to an open-weight compatible endpoint (`OPEN_WEIGHT_BASE_URL`). |
| Best agentic use | Wonder fans four candidate trajectories across cloned 60-minute St. Venant rollouts and rebuilds the plan when voice transcription locks OR2 at 0.50. |
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
backend/agents/spark_open_worker.py       four trajectories + commentary
backend/agents/glimmer_edge_guard.py      freeboard interlock
backend/agents/voice_scada_bridge.py      realtime proxy, file ASR, fault parser
backend/agents/image_counterfactual.py    anchored outfall plate
backend/main.py                           FastAPI + WebSocket twin
frontend/                                 React SCADA command center
scripts/generate_demo_assets.py           radar MP4, reference plate, .inp
scripts/run_benchmark.py                  uncontrolled vs local vs StormGate
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

## 6. Three-minute demo spine

- **0:00–0:18** Split hydraulic section. Left weir climbing toward 14,820,000 gal. Right weir at 0.
- **0:18–0:55** SAM masks on the two cores. Spark commentary names the pre-drain. Basin 4 is already down near its target before the core arrives, then crests under the weir.
- **0:55–1:40** Live SCADA button, or the jam injector: "Sluice Gate 2 is mechanically jammed at 50 percent." Wonder rebuilds the rollouts with OR2 locked. Glimmer reports the interlock. Spill stays 0.
- **1:40–2:20** Outfall twin. Mention Spark Open on the rollout worker and Glimmer on the basin PC, because a floodgate command should not depend on a closed cloud solely.
- **2:20–3:00** `python scripts/run_benchmark.py` scorecard, then back to the live board.

## 7. What the solver is

Four storage units on a short interceptor. Upstream orifices OR1–OR3 discharge into SU4. SU4's orifice is capped by the treatment plant. Above full depth, SU4 spills to the river (CSO) and SU1–SU3 spill to the street. The municipal baseline leaves upstream gates open and holds OR4 shut until the basin is at 96% — the float switch that reacts after the tank is already gone. StormGate does the opposite: it spends plant capacity before the rain, holds the upstream basins near 86%, and lets SU4 refill toward a 91% crest instead of the weir.

Volume, orifice capacity, plant capacity, and runoff are scaled together so depths stay on that path and the float-rule integral is exactly 14,820,000 gallons. That scale is `VOLUME_SCALE` in `backend/physics/design_storm.py`.
