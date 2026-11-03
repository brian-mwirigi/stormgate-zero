import type { TwinState } from "../types";

type Props = { state: TwinState };

export default function AgentCommentary({ state }: Props) {
  const maxCso = Math.max(1, ...state.rollouts.map((item) => item.total_cso_overflow_gallons));
  return (
    <section className="sg-panel">
      <p className="sg-kicker">Muse Spark Open intent · Wonder MPC · Glimmer edge</p>
      {state.rollouts.length === 0 && <p className="sg-note">Rollout tree arms on the first control step.</p>}
      {state.rollouts.map((rollout) => {
        const winner = rollout.name === state.selected;
        const width = Math.max(2, (rollout.total_cso_overflow_gallons / maxCso) * 100);
        return (
          <div className="sg-rollout" key={rollout.name}>
            <header className={winner ? "winner" : ""}>
              <span>{winner ? "▸ " : ""}{rollout.name}</span>
              <span>{Math.round(rollout.total_cso_overflow_gallons).toLocaleString()} gal</span>
            </header>
            <div className={rollout.total_cso_overflow_gallons === 0 ? "sg-bar zero" : "sg-bar"}>
              <span style={{ width: `${width}%` }} />
            </div>
            <div className="font-mono text-[10px] text-[#7f97a3]">
              peak fill {(rollout.max_basin_fill_pct * 100).toFixed(0)}% · street{" "}
              {Math.round(rollout.street_flooding_gallons).toLocaleString()} gal · plant{" "}
              {rollout.downstream_wwtp_utilization_pct.toFixed(0)}%
            </div>
          </div>
        );
      })}
      <p className="sg-commentary">{state.commentary}</p>
      {state.wonder_note && <p className="sg-note">{state.wonder_note}</p>}
      {state.refine_note && <p className="sg-note">{state.refine_note}</p>}
      <div className={state.glimmer.approved ? "sg-badge" : "sg-badge adjust"}>
        {state.glimmer.approved ? "EDGE INTERLOCK PASSED" : "EDGE INTERLOCK ADJUSTED"}
      </div>
      <p className="sg-note">{state.glimmer.summary}</p>
    </section>
  );
}
