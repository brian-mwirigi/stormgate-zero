import type { TwinState } from "../types";

type Props = { state: TwinState };

const PLAN_NAMES: Record<string, string> = {
  "A-predrain": "Pre-drain SU4, hold upstream",
  "B-balanced": "Throttle by depth",
  "C-retention": "Keep gates shut",
  "D-bypass": "Open every gate",
  "S-spark": "Muse Spark proposal",
  "W-wonder": "Muse Wonder recovery",
  "R-refine": "Muse Spark refinement",
};

function firstSentence(text: string) {
  const end = text.search(/\.\s/);
  return end > 0 ? text.slice(0, end + 1) : text;
}

export default function AgentCommentary({ state }: Props) {
  const ranked = [...state.rollouts].sort(
    (a, b) =>
      Number(b.name === state.selected) - Number(a.name === state.selected) ||
      a.total_cso_overflow_gallons - b.total_cso_overflow_gallons,
  );
  const maxCso = Math.max(1, ...ranked.map((item) => item.total_cso_overflow_gallons));
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>This step's decision</h2>
        <span>each plan simulated 60 min ahead</span>
      </div>
      {ranked.length === 0 && <p className="prose">Press Run. The first plans are scored on the first 5-minute step.</p>}
      {ranked.map((rollout) => {
        const win = rollout.name === state.selected;
        const width = rollout.total_cso_overflow_gallons > 0 ? Math.max(3, (rollout.total_cso_overflow_gallons / maxCso) * 100) : 0;
        return (
          <div className={win ? "option win" : "option"} key={rollout.name}>
            <div className="option-line">
              <span className="name">
                {PLAN_NAMES[rollout.name] || rollout.name}
                {win && <span className="tag">chosen</span>}
              </span>
              <span className={rollout.total_cso_overflow_gallons === 0 ? "num option-zero" : "num"}>
                {Math.round(rollout.total_cso_overflow_gallons).toLocaleString()} gal
              </span>
            </div>
            <div className="option-bar">
              <span style={{ width: `${width}%` }} />
            </div>
            <div className="option-meta">
              peak fill {(rollout.max_basin_fill_pct * 100).toFixed(0)}% · street {Math.round(rollout.street_flooding_gallons).toLocaleString()} gal
            </div>
          </div>
        );
      })}
      {state.rollouts.length > 0 && state.commentary && (
        <p className="prose" style={{ marginTop: 12 }}>
          {firstSentence(state.commentary)}
        </p>
      )}
      {state.wonder_note && <p className="prose">{state.wonder_note}</p>}
      {state.refine_note && <p className="prose">{state.refine_note}</p>}
      <div className={state.glimmer.approved ? "verdict" : "verdict adjust"}>
        <i className="mark" />
        <div>
          <b>{state.glimmer.approved ? "Safety interlock: passed" : "Safety interlock: overrode the gate"}</b>
          <p>{state.glimmer.summary}</p>
        </div>
      </div>
    </section>
  );
}
