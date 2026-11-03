import { useEffect, useRef, useState, type ReactNode } from "react";
import type { TwinState } from "../types";

type Props = { state: TwinState };

const UPSTREAM_X = [8, 160, 312];
const TANK_W = 118;
const TANK_TOP = 34;
const TANK_H = 92;
const PIPE_Y = 166;
const SU4 = { x: 478, y: 34, w: 172, h: 142 };
const PLANT = { x: 744, y: 142, w: 148, h: 48 };
const RIVER = { x: 744, y: 54, w: 148, h: 48 };

export default function HydraulicTwin({ state }: Props) {
  const before = useLerp(state.baseline_depth);
  const after = useLerp(state.stormgate_depth);
  const jammed = Object.entries(state.jammed);
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Interceptor sewer, live</h2>
        {jammed.length > 0 ? (
          <span>
            {jammed.map(([gate, value]) => (
              <span key={gate} className="fault-chip">
                {gate} stuck at {Math.round(value * 100)}%
              </span>
            ))}
          </span>
        ) : (
          <span>Basins SU1–SU3 drain through gates OR1–OR3 into SU4. OR4 feeds the treatment plant.</span>
        )}
      </div>
      <Lane
        title="Float switch (how the city runs it today)"
        note="Holds OR4 shut until SU4 reaches 96%, then throws it open."
        depths={before}
        gates={state.baseline_orifice}
        spill={state.cso_baseline_gal}
        street={state.street_baseline_gal}
        water="var(--spill-water)"
        jammed={state.jammed}
      />
      <Lane
        title="StormGate-Zero"
        note="Reads the radar 45 minutes out and empties SU4 before the second core lands."
        depths={after}
        gates={state.stormgate_orifice}
        spill={state.cso_stormgate_gal}
        street={state.street_stormgate_gal}
        water="var(--clean-water)"
        jammed={state.jammed}
      />
    </section>
  );
}

function Lane({
  title,
  note,
  depths,
  gates,
  spill,
  street,
  water,
  jammed,
}: {
  title: string;
  note: string;
  depths: number[];
  gates: number[];
  spill: number;
  street: number;
  water: string;
  jammed: Record<string, number>;
}) {
  const overflowing = (depths[3] ?? 0) >= 0.99;
  const upstreamFlow = gates.slice(0, 3).reduce((sum, value) => sum + value, 0) / 3;
  return (
    <div className="lane">
      <div className="lane-head">
        <b>{title}</b>
        <span>{note}</span>
      </div>
      <svg viewBox="0 0 900 210" role="img" aria-label={`${title} sewer section`}>
        <line
          x1={UPSTREAM_X[0] + TANK_W / 2}
          y1={PIPE_Y}
          x2={SU4.x}
          y2={PIPE_Y}
          stroke="var(--hair-strong)"
          strokeWidth="12"
          strokeLinecap="round"
        />
        <line
          className="flow"
          x1={UPSTREAM_X[0] + TANK_W / 2}
          y1={PIPE_Y}
          x2={SU4.x}
          y2={PIPE_Y}
          stroke={water}
          strokeWidth="4"
          opacity={0.25 + 0.75 * upstreamFlow}
        />
        <text x={UPSTREAM_X[0]} y={PIPE_Y + 30} fill={street > 0 ? "var(--spill)" : "var(--muted)"} fontSize="12" fontWeight={street > 0 ? 600 : 400}>
          {street > 0 ? `${Math.round(street).toLocaleString()} gal backed up into the street` : "interceptor sewer"}
        </text>

        {UPSTREAM_X.map((x, index) => (
          <Basin
            key={index}
            x={x}
            y={TANK_TOP}
            w={TANK_W}
            h={TANK_H}
            label={`SU${index + 1}`}
            depth={depths[index] ?? 0}
            water={water}
            overflowLabel={(depths[index] ?? 0) >= 0.99 ? "street" : ""}
          >
            <Gate
              x={x + TANK_W / 2}
              y1={TANK_TOP + TANK_H}
              y2={PIPE_Y - 6}
              id={`OR${index + 1}`}
              opening={gates[index] ?? 0}
              stuck={jammed[`OR${index + 1}`]}
              water={water}
            />
          </Basin>
        ))}

        <Basin
          x={SU4.x}
          y={SU4.y}
          w={SU4.w}
          h={SU4.h}
          label="SU4"
          depth={depths[3] ?? 0}
          water={water}
          overflowLabel=""
        />

        <line x1={SU4.x + SU4.w} y1={PIPE_Y} x2={PLANT.x} y2={PIPE_Y} stroke="var(--hair-strong)" strokeWidth="12" />
        <line
          className="flow"
          x1={SU4.x + SU4.w}
          y1={PIPE_Y}
          x2={PLANT.x}
          y2={PIPE_Y}
          stroke={water}
          strokeWidth="4"
          opacity={0.2 + 0.8 * (gates[3] ?? 0)}
        />
        <HGate x={SU4.x + SU4.w + 44} y={PIPE_Y} id="OR4" opening={gates[3] ?? 0} stuck={jammed.OR4} />
        <rect x={PLANT.x} y={PLANT.y} width={PLANT.w} height={PLANT.h} rx="4" fill="var(--surface-2)" stroke="var(--hair-strong)" />
        <text x={PLANT.x + 12} y={PLANT.y + 20} fill="var(--text-2)" fontSize="12">
          Treatment plant
        </text>
        <text x={PLANT.x + 12} y={PLANT.y + 37} fill="var(--muted)" fontSize="11">
          capacity-limited
        </text>

        <path
          d={`M ${SU4.x + SU4.w} ${SU4.y + 6} C ${SU4.x + SU4.w + 40} ${SU4.y + 6}, ${RIVER.x - 30} ${RIVER.y + 10}, ${RIVER.x} ${RIVER.y + 18}`}
          fill="none"
          stroke={overflowing ? "var(--spill)" : "var(--hair-strong)"}
          strokeWidth={overflowing ? 6 : 2}
          strokeDasharray={overflowing ? undefined : "4 6"}
          className={overflowing ? "flow" : undefined}
        />
        <text x={RIVER.x} y={RIVER.y - 8} fill="var(--muted)" fontSize="11">
          over the weir
        </text>
        <rect
          x={RIVER.x}
          y={RIVER.y}
          width={RIVER.w}
          height={RIVER.h}
          rx="4"
          fill={spill > 0 ? "rgba(226, 85, 63, 0.14)" : "var(--surface-2)"}
          stroke={spill > 0 ? "var(--spill)" : "var(--hair-strong)"}
        />
        <text x={RIVER.x + 12} y={RIVER.y + 17} fill="var(--text-2)" fontSize="12">
          River
        </text>
        <text
          x={RIVER.x + 12}
          y={RIVER.y + 33}
          className="num"
          fill={spill > 0 ? "var(--spill)" : "var(--muted)"}
          fontSize="12"
          fontWeight="600"
        >
          {Math.round(spill).toLocaleString()} gal
        </text>
      </svg>
    </div>
  );
}

function Basin({
  x,
  y,
  w,
  h,
  label,
  depth,
  water,
  overflowLabel,
  children,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  depth: number;
  water: string;
  overflowLabel: string;
  children?: ReactNode;
}) {
  const fill = Math.max(0, Math.min(depth, 1));
  const level = fill * (h - 4);
  const hot = fill >= 0.9;
  return (
    <g>
      {children}
      <rect x={x} y={y} width={w} height={h} rx="4" fill="#0b0c0e" stroke="var(--hair-strong)" strokeWidth="1.5" />
      <rect x={x + 2} y={y + h - 2 - level} width={w - 4} height={level} rx="2" fill={water} />
      <text x={x} y={y - 9} fill="var(--text-2)" fontSize="13" fontWeight="600">
        {label}
      </text>
      <text
        x={x + w}
        y={y - 8}
        textAnchor="end"
        className="num"
        fill={hot ? "var(--spill)" : "var(--ink)"}
        fontSize="19"
        fontWeight="600"
      >
        {Math.round(depth * 100)}%
      </text>
      {overflowLabel && (
        <text x={x + w / 2} y={y + 18} textAnchor="middle" fill="#fff" fontSize="11" fontWeight="600">
          overflowing to {overflowLabel}
        </text>
      )}
    </g>
  );
}

function Gate({
  x,
  y1,
  y2,
  id,
  opening,
  stuck,
  water,
}: {
  x: number;
  y1: number;
  y2: number;
  id: string;
  opening: number;
  stuck?: number;
  water: string;
}) {
  const pipeW = 16;
  const midY = (y1 + y2) / 2;
  const closed = (1 - Math.max(0, Math.min(opening, 1))) * pipeW;
  const color = stuck !== undefined ? "var(--fault)" : "var(--text)";
  return (
    <g>
      <rect x={x - pipeW / 2} y={y1} width={pipeW} height={y2 - y1 + 6} fill="var(--hair-strong)" />
      <rect x={x - 2} y={y1} width={4} height={y2 - y1 + 6} fill={water} opacity={0.3 + 0.7 * opening} />
      <rect x={x - pipeW / 2 - 3} y={midY - 3} width={closed + 3} height={6} fill={color} />
      <text x={x + pipeW / 2 + 6} y={midY + 4} className="num" fill={color} fontSize="11">
        {id} {Math.round(opening * 100)}%{stuck !== undefined ? " stuck" : ""}
      </text>
    </g>
  );
}

function HGate({ x, y, id, opening, stuck }: { x: number; y: number; id: string; opening: number; stuck?: number }) {
  const pipeH = 12;
  const closed = (1 - Math.max(0, Math.min(opening, 1))) * pipeH;
  const color = stuck !== undefined ? "var(--fault)" : "var(--text)";
  return (
    <g>
      <rect x={x - 3} y={y - pipeH / 2 - 3} width={6} height={closed + 3} fill={color} />
      <text x={x} y={y + 24} textAnchor="middle" className="num" fill={color} fontSize="11">
        {id} {Math.round(opening * 100)}%
      </text>
    </g>
  );
}

function useLerp(target: number[]) {
  const [value, setValue] = useState(target);
  const from = useRef(target);
  const key = target.join(",");
  useEffect(() => {
    const origin = from.current;
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const k = Math.min(1, (now - start) / 800);
      setValue(origin.map((item, index) => item + ((target[index] ?? item) - item) * k));
      if (k < 1) frame = requestAnimationFrame(tick);
      else from.current = target;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return value;
}
