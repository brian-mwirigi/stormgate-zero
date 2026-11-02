import { useEffect, useRef, useState } from "react";
import type { TwinState } from "../types";

type Props = { state: TwinState };

export default function HydraulicTwin({ state }: Props) {
  const left = useLerp(state.baseline_depth);
  const right = useLerp(state.stormgate_depth);
  const jammed = state.jammed.OR2;
  return (
    <section className="sg-panel sg-hero">
      <p className="sg-kicker">Hydraulic grade line · SU1–SU4 · OR1–OR4 · river weir OF4</p>
      {jammed !== undefined && (
        <div className="fault-banner">FAULT · OR2 LOCKED AT {Math.round(jammed * 100)}%</div>
      )}
      <div className="sg-hgl">
        <svg viewBox="0 0 540 310" role="img" aria-label="Municipal local-control sewer section">
          <Side
            title="STANDARD MUNICIPAL LOCAL CONTROL"
            depths={left}
            gates={state.baseline_orifice}
            spill={state.cso_baseline_gal}
            accent="#ff3355"
            water="#9a3a2a"
            jammed={jammed !== undefined}
          />
        </svg>
        <svg viewBox="0 0 540 310" role="img" aria-label="StormGate closed-loop sewer section">
          <Side
            title="STORMGATE-ZERO CLOSED LOOP"
            depths={right}
            gates={state.stormgate_orifice}
            spill={state.cso_stormgate_gal}
            accent="#1dff9a"
            water="#1c8f86"
            jammed={jammed !== undefined}
          />
        </svg>
      </div>
    </section>
  );
}

function Side({
  title,
  depths,
  gates,
  spill,
  accent,
  water,
  jammed,
}: {
  title: string;
  depths: number[];
  gates: number[];
  spill: number;
  accent: string;
  water: string;
  jammed: boolean;
}) {
  return (
    <g>
      <text x="16" y="28" fill={accent} fontFamily="Consolas, monospace" fontSize="13">
        {title}
      </text>
      <text x="16" y="48" fill="#7f97a3" fontFamily="Consolas, monospace" fontSize="11">
        WEIR {Math.round(spill).toLocaleString()} GAL
      </text>
      {depths.map((depth, index) => {
        const bx = 24 + index * 112;
        const full = 150;
        const h = Math.min(depth, 1) * full;
        const gate = gates[index] ?? 0;
        const gateH = (1 - gate) * 70;
        const spilling = depth >= 0.995 && index === 3;
        return (
          <g key={index} transform={`translate(${bx},70)`}>
            <rect x="0" y="0" width="78" height="160" fill="#10161c" stroke="#2a4550" />
            <rect x="4" y={156 - h} width="70" height={h} fill={water} opacity="0.92" />
            <rect x="78" y={90 - gateH / 2} width="10" height={Math.max(gateH, 4)} fill={jammed && index === 1 ? "#ff3355" : "#d5dde2"} />
            <text x="4" y="178" fill="#d7e4ec" fontFamily="Consolas, monospace" fontSize="12">
              SU{index + 1} {Math.round(depth * 100)}%
            </text>
            <text x="4" y="194" fill="#7f97a3" fontFamily="Consolas, monospace" fontSize="11">
              OR{index + 1} {Math.round(gate * 100)}%
            </text>
            {spilling && (
              <polygon points="70,150 110,210 40,210" fill="#ff3355" opacity="0.85" />
            )}
          </g>
        );
      })}
      <rect x="20" y="268" width="490" height="10" fill="#24343c" />
      <text x="250" y="292" fill="#7f97a3" fontFamily="Consolas, monospace" fontSize="11">
        INTERCEPTOR → RIVER
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
