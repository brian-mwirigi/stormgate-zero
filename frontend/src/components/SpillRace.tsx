type Point = { t: number; before: number; after: number };

type Props = { history: Point[]; minutes: number; jamAt: number | null };

const W = 520;
const H = 210;
const PAD = { l: 48, r: 12, t: 12, b: 26 };

export default function SpillRace({ history, minutes, jamAt }: Props) {
  const top = Math.max(1_000_000, ...history.map((point) => Math.max(point.before, point.after)));
  const scaleTop = niceCeil(top);
  const x = (t: number) => PAD.l + (t / minutes) * (W - PAD.l - PAD.r);
  const y = (gal: number) => H - PAD.b - (gal / scaleTop) * (H - PAD.t - PAD.b);
  const line = (key: "before" | "after") => history.map((point) => `${x(point.t).toFixed(1)},${y(point[key]).toFixed(1)}`).join(" ");
  const last = history[history.length - 1];
  const ticks = [0, 0.5, 1].map((k) => k * scaleTop);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Sewage in the river, cumulative</h2>
        <span>gallons over the 90-minute storm</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }} role="img" aria-label="Cumulative overflow">
        {ticks.map((value) => (
          <g key={value}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(value)} y2={y(value)} stroke="var(--hair)" />
            <text x={PAD.l - 8} y={y(value) + 4} textAnchor="end" className="num" fill="var(--muted)" fontSize="10.5">
              {short(value)}
            </text>
          </g>
        ))}
        {[0, 30, 60, 90].map((t) => (
          <text key={t} x={x(t)} y={H - 8} textAnchor="middle" className="num" fill="var(--muted)" fontSize="10.5">
            {t} min
          </text>
        ))}
        {jamAt !== null && (
          <g>
            <line x1={x(jamAt)} x2={x(jamAt)} y1={PAD.t} y2={H - PAD.b} stroke="var(--fault)" strokeDasharray="3 4" />
            <text x={x(jamAt) + 5} y={PAD.t + 10} fill="var(--fault)" fontSize="11">
              gate jams
            </text>
          </g>
        )}
        {history.length > 1 && (
          <>
            <polyline points={line("before")} fill="none" stroke="var(--spill)" strokeWidth="2.5" />
            <polyline points={line("after")} fill="none" stroke="var(--clean)" strokeWidth="2.5" />
          </>
        )}
        {last && (
          <>
            <circle cx={x(last.t)} cy={y(last.before)} r="4" fill="var(--spill)" />
            <circle cx={x(last.t)} cy={y(last.after)} r="4" fill="var(--clean)" />
          </>
        )}
      </svg>
      <div className="models legend">
        <div>
          <i style={{ background: "var(--spill)" }} />
          <b>Float switch</b>
        </div>
        <div>
          <i style={{ background: "var(--clean)" }} />
          <b>StormGate-Zero</b>
        </div>
      </div>
    </section>
  );
}

function niceCeil(value: number) {
  const exp = 10 ** Math.floor(Math.log10(value));
  const m = value / exp;
  const nice = m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10;
  return nice * exp;
}

function short(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value % 1_000_000 ? 1 : 0)}M`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}k`;
  return `${Math.round(value)}`;
}
