import { useEffect, useState } from "react";
import AgentCommentary from "./components/AgentCommentary";
import HydraulicTwin from "./components/HydraulicTwin";
import OutfallCounterfactual from "./components/OutfallCounterfactual";
import RadarSamCanvas from "./components/RadarSamCanvas";
import VoiceWarRoom from "./components/VoiceWarRoom";
import type { TwinState } from "./types";

const MODEL_ORDER = [
  ["sam-3.1", "SAM 3.1"],
  ["muse-wonder-1.0", "Wonder 1.0"],
  ["muse-spark-open", "Spark Open"],
  ["muse-glimmer-30b", "Glimmer 30B"],
  ["muse-voice-transcribe-1.0", "Voice"],
  ["muse-image-1.0", "Image 1.0"],
] as const;

export default function App() {
  const [state, setState] = useState<TwinState | null>(null);
  const [showOutfall, setShowOutfall] = useState(false);
  const [offline, setOffline] = useState("");

  useEffect(() => {
    let cancelled = false;
    const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/twin`);
    socket.onmessage = (event) => {
      if (cancelled) return;
      setState(JSON.parse(event.data) as TwinState);
      setOffline("");
    };
    socket.onerror = () => {
      if (!cancelled) setOffline("SCADA bus offline. Start uvicorn backend.main:app --port 8000.");
    };
    return () => {
      cancelled = true;
      socket.close();
    };
  }, []);

  async function renderOutfall() {
    await fetch("/api/outfall", { method: "POST" });
    setShowOutfall(true);
  }

  async function toggle() {
    if (!state) return;
    if (state.done) {
      await fetch("/api/episode/reset", { method: "POST" });
      return;
    }
    await fetch(state.running ? "/api/episode/pause" : "/api/episode/start", { method: "POST" });
  }

  return (
    <div className="sg-root">
      <header className="sg-header">
        <div className="sg-title">
          <h1>STORMGATE-ZERO</h1>
          <p>Vision-to-PDE autonomous sewer overflow controller</p>
        </div>
        <div className="sg-counters">
          <div className="sg-counter bad">
            <span>Uncontrolled municipal baseline CSO</span>
            <strong>
              {Math.round(state?.cso_baseline_gal ?? 0).toLocaleString()}
              <em>GAL</em>
            </strong>
          </div>
          <div className="sg-counter good">
            <span>StormGate-Zero controlled CSO</span>
            <strong>
              {Math.round(state?.cso_stormgate_gal ?? 0).toLocaleString()}
              <em>GAL</em>
            </strong>
          </div>
        </div>
        <div className="sg-pills">
          {MODEL_ORDER.map(([id, label]) => {
            const model = state?.models[id];
            const live = (model?.status || "").includes("LIVE") || (model?.status || "").includes("FALLBACK");
            return (
              <div key={id} className={live ? "sg-pill live" : "sg-pill"}>
                <i />
                <b>{label}</b> {model?.status || "STANDBY"}
                {model?.latency_ms ? ` ${Math.round(model.latency_ms)}ms` : ""}
              </div>
            );
          })}
        </div>
      </header>
      {offline && <p className="fault-banner">{offline}</p>}
      {state && (
        <>
          <div className="sg-top">
            <RadarSamCanvas state={state} />
            <AgentCommentary state={state} />
          </div>
          <HydraulicTwin state={state} />
          <VoiceWarRoom
            state={state}
            onOutfall={() => void renderOutfall()}
            onReset={() => void fetch("/api/episode/reset", { method: "POST" })}
            onToggle={() => void toggle()}
          />
        </>
      )}
      {showOutfall && <OutfallCounterfactual onClose={() => setShowOutfall(false)} />}
    </div>
  );
}
