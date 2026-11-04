import { useEffect, useRef, useState } from "react";
import AgentCommentary from "./components/AgentCommentary";
import HydraulicTwin from "./components/HydraulicTwin";
import OutfallCounterfactual from "./components/OutfallCounterfactual";
import RadarSamCanvas from "./components/RadarSamCanvas";
import SpillRace from "./components/SpillRace";
import VoiceWarRoom from "./components/VoiceWarRoom";
import type { TwinState } from "./types";

const MODELS = [
  ["sam-3.1", "SAM 3.1"],
  ["muse-spark-open", "Muse Spark 1.3"],
  ["muse-wonder-1.0", "Muse Wonder 1.0"],
  ["muse-glimmer-30b", "Glimmer 30B"],
  ["muse-voice-transcribe-1.0", "Muse Voice"],
  ["muse-image-1.0", "Muse Image 1.0"],
] as const;

const STORMS = [
  ["ida-2021-newark", "Hurricane Ida · Newark (Real NEXRAD)"],
  ["chicago-2023-0702", "Chicago · 2 Jul 2023 (Real NEXRAD)"],
  ["ds-1482", "DS-1482 (Calibration Benchmark)"],
] as const;

const PROVENANCE: Record<
  string,
  {
    badge: string;
    radar: string;
    vision: string;
    result: string;
  }
> = {
  "ida-2021-newark": {
    badge: "REAL NEXRAD N0Q MOSAIC · 1 SEP 2021",
    radar:
      "6 real IEM N0Q radar frames over Newark (23:30–00:45 UTC, 40.69°N 74.17°W). Basin rainfall is integrated directly from the radar pixels via Marshall-Palmer Z-R.",
    vision:
      "Segmented by sam-3.1 (traces/live_models.json → sam_events.ida-2021-newark) and read directly by meta/muse-glimmer-30b (response 8ad068e1ef1cadad → SW quadrant / basin SU2, 28.08 mm/hr).",
    result:
      "Full 90-min replay: Municipal float switch spills 12,096,528 gal · StormGate-Zero spills 0 gal · SWMM5 DYNWAVE peak 3.338 psi on Junction J1.",
  },
  "chicago-2023-0702": {
    badge: "REAL NEXRAD N0Q MOSAIC · 2 JUL 2023",
    radar:
      "6 real IEM N0Q radar frames over West Chicago (21:00–23:30 UTC, 41.85°N 87.75°W). Basin rainfall is integrated directly from the radar pixels via Marshall-Palmer Z-R.",
    vision:
      "Segmented by sam-3.1 in the <0f> box grammar across 5/6 frames (44 rain-core boxes in traces/live_models.json → sam_events.chicago-2023-0702).",
    result:
      "Full 90-min replay: Municipal float switch spills 13,673,729 gal · StormGate-Zero spills 0 gal · SWMM5 DYNWAVE peak 1.846 psi on Junction J4.",
  },
  "ds-1482": {
    badge: "CALIBRATED 18-STEP BENCHMARK · LIVE TRACE REPLAY",
    radar:
      "Controlled 90-minute two-core benchmark scaled so the municipal float switch spills exactly 14,820,000 gal.",
    vision:
      "Replays 18 step-by-step muse-spark-1.3 gate vectors (0|..17|), sam-3.1 core boxes, and muse-wonder-1.0 jam recovery (resp_6ae9adeac24e0d3e800f40f3).",
    result:
      "Full 90-min replay: Municipal float switch spills 14,820,000 gal · StormGate-Zero spills 0 gal (and 0 gal with Gate OR2 jammed at 50%) · SWMM5 DYNWAVE peak 3.539 psi on J3.",
  },
};

type Point = { t: number; before: number; after: number; jam: boolean };

const gal = (value: number) => Math.round(value).toLocaleString();

export default function App() {
  const [state, setState] = useState<TwinState | null>(null);
  const [showOutfall, setShowOutfall] = useState(false);
  const [offline, setOffline] = useState("");
  const [history, setHistory] = useState<Point[]>([]);
  const lastStep = useRef(-1);
  const bootSelected = useRef(false);

  useEffect(() => {
    let cancelled = false;
    const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/twin`);
    socket.onmessage = (event) => {
      if (cancelled) return;
      const next = JSON.parse(event.data) as TwinState;
      if (!bootSelected.current) {
        bootSelected.current = true;
        if (next.storm?.id === "ds-1482") {
          void fetch("/api/storm", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: "ida-2021-newark" }),
          });
        }
      }
      setState(next);
      setOffline("");
      const point = {
        t: next.t_min,
        before: next.cso_baseline_gal,
        after: next.cso_stormgate_gal,
        jam: Object.keys(next.jammed).length > 0,
      };
      if (next.step < lastStep.current || next.step === 0) {
        setHistory([point]);
      } else if (next.step !== lastStep.current) {
        setHistory((rows) => (rows.length ? [...rows, point] : [{ t: 0, before: 0, after: 0, jam: false }, point]));
      }
      lastStep.current = next.step;
    };
    socket.onerror = () => {
      if (!cancelled) setOffline("Can't reach the plant. Start the API: python -m uvicorn backend.main:app --port 8000");
    };
    return () => {
      cancelled = true;
      socket.close();
    };
  }, []);

  useEffect(() => {
    if (state && state.step >= 4 && !state.wave && (!state.running || state.done)) {
      void fetch("/api/verify/wave", { method: "POST" });
    }
  }, [state]);

  async function toggle() {
    if (!state) return;
    if (state.done) {
      await fetch("/api/episode/reset", { method: "POST" });
      await fetch("/api/episode/start", { method: "POST" });
      return;
    }
    await fetch(state.running ? "/api/episode/pause" : "/api/episode/start", { method: "POST" });
  }

  async function renderOutfall() {
    await fetch("/api/outfall", { method: "POST" });
    setShowOutfall(true);
  }

  const jamPoint = history.find((point) => point.jam);
  const saved = Math.max(0, (state?.cso_baseline_gal ?? 0) - (state?.cso_stormgate_gal ?? 0));
  const stormId = state?.storm?.id;
  const prov = (stormId && PROVENANCE[stormId]) || PROVENANCE["ida-2021-newark"];
  const spillSteps = new Set(
    history.filter((point, index) => index > 0 && point.before > history[index - 1].before).map((point) => point.t / 5 - 1),
  );

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden>
            <svg width="16" height="16" viewBox="0 0 16 16">
              <path d="M2 10 Q5 6 8 10 T14 10" fill="none" stroke="#0a0b0d" strokeWidth="1.8" />
              <rect x="6.6" y="2" width="2.8" height="6" fill="#0a0b0d" />
            </svg>
          </div>
          <h1>StormGate-Zero</h1>
          <span>Radar-guided sewer gates</span>
        </div>
        <div className="storms" role="tablist" aria-label="Storm">
          {STORMS.map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={stormId === id ? "on" : ""}
              onClick={() =>
                fetch("/api/storm", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ id }),
                })
              }
            >
              {label}
            </button>
          ))}
          {stormId === "custom-cell" && (
            <button type="button" className="on">
              Your 60 dBZ cell
            </button>
          )}
        </div>
        <div className="controls">
          <button className="btn primary" type="button" onClick={() => void toggle()} disabled={!state}>
            {state?.running ? "Pause" : state?.done ? "Replay storm" : "Run storm"}
          </button>
          <button className="btn" type="button" onClick={() => fetch("/api/episode/reset", { method: "POST" })}>
            Reset
          </button>
          <button className="btn" type="button" onClick={() => void renderOutfall()}>
            Outfall image
          </button>
        </div>
      </header>

      {offline && <p className="offline">{offline}</p>}

      {state && (
        <>
          <section className="provenance">
            <div className="prov-badge">{prov.badge}</div>
            <div className="prov-cols">
              <div>
                <b>Radar & Hydrology</b>
                <p>{prov.radar}</p>
              </div>
              <div>
                <b>Recorded Meta Vision Traces</b>
                <p>{prov.vision}</p>
              </div>
              <div>
                <b>Verified 90-Minute Outcome</b>
                <p>{prov.result}</p>
              </div>
            </div>
          </section>

          <section className="lede">
            <div>
              <h2>
                {state.step === 0 ? (
                  <>
                    Same pipes, same rain. Run the storm and watch which gates keep sewage out of the river.
                  </>
                ) : (
                  <>
                    Today's float switch has put <em>{gal(state.cso_baseline_gal)} gallons</em> of raw sewage in the
                    river. StormGate-Zero has put in <strong>{gal(state.cso_stormgate_gal)}</strong>.
                  </>
                )}
              </h2>
              <p>{state.storm?.title}. Both sewers get identical rainfall every 5 minutes; only the gate control differs.</p>
            </div>
            <div className="timeline">
              <div className="timeline-head">
                <span>
                  Storm clock · <span style={{ color: "var(--spill)" }}>red underline</span> = float switch spilling
                  {jamPoint ? <span style={{ color: "var(--fault)" }}> · amber = gate jammed</span> : null}
                </span>
                <b>
                  T+{state.t_min} min
                  {state.done ? " · finished" : state.running ? "" : " · paused"}
                </b>
              </div>
              <div className="ticks" aria-hidden>
                {Array.from({ length: state.steps_total }, (_, index) => {
                  const jam = jamPoint && index * 5 >= jamPoint.t && index < state.step;
                  const cls = jam ? "jam" : index < state.step ? "done" : index === state.step ? "now" : "";
                  return <i key={index} className={`${cls}${spillSteps.has(index) ? " spill" : ""}`} />;
                })}
              </div>
              <div className="timeline-scale">
                <span>0</span>
                <span>30</span>
                <span>60</span>
                <span>{state.steps_total * 5} min</span>
              </div>
            </div>
          </section>

          <section className="score">
            <div className="bad">
              <div className="score-label">
                <i style={{ background: "var(--spill)" }} />
                Float switch · raw sewage over the river weir
              </div>
              <div className="score-value">
                {gal(state.cso_baseline_gal)}
                <small>gal</small>
              </div>
              <div className="score-sub">Street flooding {gal(state.street_baseline_gal)} gal</div>
            </div>
            <div className="good">
              <div className="score-label">
                <i style={{ background: "var(--clean)" }} />
                StormGate-Zero · same pipes, same rain
              </div>
              <div className="score-value">
                {gal(state.cso_stormgate_gal)}
                <small>gal</small>
              </div>
              <div className="score-sub">Street flooding {gal(state.street_stormgate_gal)} gal</div>
            </div>
            <div className="delta">
              <div className="score-label">Kept out of the river so far</div>
              <div className="score-value">
                {gal(saved)}
                <small>gal</small>
              </div>
              <div className="score-sub">{state.storm?.title}</div>
            </div>
          </section>

          <div className="grid-main">
            <HydraulicTwin state={state} />
            <RadarSamCanvas state={state} />
          </div>

          <div className="grid-lower">
            <SpillRace history={history} minutes={state.steps_total * 5} jamAt={jamPoint ? jamPoint.t : null} />
            <AgentCommentary state={state} />
            <VoiceWarRoom state={state} />
          </div>

          <Facts state={state} />

          <footer className="models">
            {MODELS.map(([id, label]) => {
              const model = state.models[id];
              const status = model?.status || "STANDBY";
              const live = status.includes("LIVE") || status.includes("MUSE VOICE");
              return (
                <div key={id} className={live ? "live" : ""}>
                  <i />
                  <b>{label}</b>
                  <span>
                    {status.toLowerCase()}
                    {model?.latency_ms ? ` · ${(model.latency_ms / 1000).toFixed(1)} s` : ""}
                  </span>
                </div>
              );
            })}
          </footer>
        </>
      )}

      {showOutfall && <OutfallCounterfactual onClose={() => setShowOutfall(false)} />}
    </div>
  );
}

function Facts({ state }: { state: TwinState }) {
  const before = state.exposure?.baseline;
  const after = state.exposure?.stormgate;
  const wave = state.wave;
  return (
    <section className="facts">
      <div>
        <h3>Clean Water Act penalty ceiling</h3>
        <div className="pair">
          <span>Float switch</span>
          <span className="num">${gal(before?.statutory_usd ?? 0)}</span>
        </div>
        <div className="pair">
          <span>StormGate-Zero</span>
          <span className="num">${gal(after?.statutory_usd ?? 0)}</span>
        </div>
        <p className="fine">$68,445 per day per violation, 33 U.S.C. 1319(d). Applies when a spill breaks a permit or consent-decree term.</p>
      </div>
      <div>
        <h3>E. coli in the receiving water</h3>
        <div className="pair">
          <span>Float switch</span>
          <span className="num">{gal(before?.ecoli_cfu_per_100ml ?? 0)} CFU</span>
        </div>
        <div className="pair">
          <span>StormGate-Zero</span>
          <span className="num">{gal(after?.ecoli_cfu_per_100ml ?? 0)} CFU</span>
        </div>
        <p className="fine">Per 100 mL, planning dilution. EPA beach action value is 235.</p>
      </div>
      <div>
        <h3>SWMM5 dynamic-wave check</h3>
        {wave?.ok ? (
          <>
            <div className="pair">
              <span>Worst pipe</span>
              <span className="num">{wave.worst_link}</span>
            </div>
            <div className="pair">
              <span>Head above crown</span>
              <span className="num">{wave.worst_surcharge_psi} psi</span>
            </div>
          </>
        ) : (
          <p className="fine">{wave?.error || "Runs on the committed gate schedule when the storm finishes."}</p>
        )}
      </div>
      <div>
        <h3>Data & plant boundary</h3>
        <p className="fine" style={{ marginTop: 0 }}>
          {state.storm?.note}
        </p>
      </div>
    </section>
  );
}
