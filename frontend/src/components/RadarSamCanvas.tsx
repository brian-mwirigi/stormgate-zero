import { useEffect, useRef } from "react";
import type { TwinState } from "../types";
import { parseObjectPrompt } from "../lib/samWire";

type Props = { state: TwinState };

const BASINS = ["SU1", "SU2", "SU3", "SU4"];

export default function RadarSamCanvas({ state }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frame = Math.round((state.t_min / 90) * 36);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const image = new Image();
    image.onload = () => paint(ctx, image, state);
    image.src = `/api/radar/frame/${frame}?t=${state.step}&storm=${state.storm?.id || ""}`;
  }, [frame, state]);

  const boxes = parseObjectPrompt(state.object_prompt).length;

  return (
    <section className="panel dark">
      <div className="panel-head">
        <h2>What the radar sees</h2>
        <span>{boxes ? `SAM 3.1 boxed ${boxes} rain core${boxes === 1 ? "" : "s"}` : "SAM 3.1 · no core in frame yet"}</span>
      </div>
      <figure
        className="radar-frame"
        style={{ margin: 0 }}
        onClick={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          void fetch("/api/storm/cell", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              x: (event.clientX - rect.left) / rect.width,
              y: (event.clientY - rect.top) / rect.height,
              dbz: 60,
            }),
          });
        }}
      >
        <canvas ref={canvasRef} width={720} height={720} />
        <figcaption>
          {state.storm?.title || "radar"} · T+{state.t_min} min
          {state.storm?.id === "ida-2021-newark"
            ? " · IEM N0Q NEXRAD mosaic · Glimmer 30B: SW / SU2 (8ad068e1ef1cadad)"
            : state.storm?.id === "chicago-2023-0702"
              ? " · IEM N0Q NEXRAD mosaic · SAM 3.1: 44 boxes"
              : ""}
        </figcaption>
      </figure>
      <p className="radar-hint">Click anywhere on the radar to drop a 60 dBZ storm cell. Rain forecast per basin, next 60 min:</p>
      <div className="basin-rows">
        {BASINS.map((basin) => {
          const series = state.forecast_mm_hr[basin] || [];
          const peak = Math.max(0, ...series);
          const at = series.indexOf(peak);
          return (
            <div className="basin-row" key={basin}>
              <b>{basin}</b>
              <Spark values={series} />
              <span className="num">{peak ? `${peak.toFixed(0)} mm/hr` : "dry"}</span>
              <span className="num muted">{peak && at > 0 ? `in ${at * 5} min` : peak ? "now" : ""}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Spark({ values }: { values: number[] }) {
  if (values.length < 2) return <svg viewBox="0 0 100 22" />;
  const max = Math.max(70, ...values);
  const step = 100 / (values.length - 1);
  const points = values.map((value, index) => `${(index * step).toFixed(2)},${(21 - (value / max) * 19).toFixed(2)}`);
  return (
    <svg viewBox="0 0 100 22" preserveAspectRatio="none">
      <polygon points={`0,22 ${points.join(" ")} 100,22`} fill="rgba(127, 182, 217, 0.22)" />
      <polyline points={points.join(" ")} fill="none" stroke="#7fb6d9" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function paint(ctx: CanvasRenderingContext2D, image: HTMLImageElement, state: TwinState) {
  const { width, height } = ctx.canvas;
  ctx.clearRect(0, 0, width, height);
  ctx.drawImage(image, 0, 0, width, height);

  Object.values(state.polygons).forEach((rect, index) => {
    const [x1, y1, x2, y2] = rect;
    ctx.save();
    ctx.setLineDash([5, 5]);
    ctx.lineWidth = 1.2;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.55)";
    ctx.strokeRect(x1 * width, y1 * height, (x2 - x1) * width, (y2 - y1) * height);
    ctx.restore();
    label(ctx, `SU${index + 1}`, x1 * width + 6, y1 * height + 6, "rgba(14, 16, 18, 0.8)", "#ebe8e2");
  });

  const samBoxes = parseObjectPrompt(state.object_prompt);
  samBoxes.forEach((box, idx) => {
    const bx = box.x1 * width;
    const by = box.y1 * height;
    const bw = (box.x2 - box.x1) * width;
    const bh = (box.y2 - box.y1) * height;
    ctx.lineWidth = 4.5;
    ctx.strokeStyle = "rgba(10, 11, 13, 0.85)";
    ctx.strokeRect(bx, by, bw, bh);
    ctx.lineWidth = 2.2;
    ctx.strokeStyle = "#3ee0ff";
    ctx.strokeRect(bx, by, bw, bh);
    if (idx === 0) {
      label(ctx, `SAM 3.1 (${samBoxes.length})`, bx + 4, Math.max(4, by - 24), "#3ee0ff", "#0a0b0d");
    }
  });

  state.cores.forEach((core) => {
    const x = core.cx * width;
    const y = core.cy * height;
    ctx.beginPath();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#ffffff";
    ctx.ellipse(x, y, core.rx * width, core.ry * height, 0, 0, Math.PI * 2);
    ctx.stroke();
    const dx = core.vx_per_min * 8 * width;
    const dy = core.vy_per_min * 8 * height;
    arrow(ctx, x, y, x + dx, y + dy);
    label(ctx, `${core.dbz.toFixed(0)} dBZ`, x + 10, y - 26, "#e0a43a", "#0e1012");
  });
}

function label(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, bg: string, fg: string) {
  ctx.font = "600 15px 'IBM Plex Mono', Consolas, monospace";
  const w = ctx.measureText(text).width + 12;
  ctx.fillStyle = bg;
  ctx.fillRect(x, y, w, 22);
  ctx.fillStyle = fg;
  ctx.fillText(text, x + 6, y + 16);
}

function arrow(ctx: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number) {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  ctx.beginPath();
  ctx.lineWidth = 2;
  ctx.strokeStyle = "#ffffff";
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.lineTo(x2 - 10 * Math.cos(angle - 0.45), y2 - 10 * Math.sin(angle - 0.45));
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - 10 * Math.cos(angle + 0.45), y2 - 10 * Math.sin(angle + 0.45));
  ctx.stroke();
}
