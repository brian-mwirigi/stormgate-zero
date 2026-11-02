import { useEffect, useRef } from "react";
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Legend, Tooltip } from "chart.js";
import { Line } from "react-chartjs-2";
import type { TwinState } from "../types";
import { parseObjectPrompt } from "../lib/samWire";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Legend, Tooltip);

const COLORS = ["#3ee0ff", "#ffb020", "#ff3ec8", "#ff5a3c"];

type Props = { state: TwinState };

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
    image.src = `/api/radar/frame/${frame}?t=${state.step}`;
  }, [frame, state]);

  const labels = (state.forecast_mm_hr.SU4 || []).map((_, index) => `+${index * 5}`);
  const chartData = {
    labels,
    datasets: ["SU1", "SU2", "SU3", "SU4"].map((basin, index) => ({
      label: basin,
      data: state.forecast_mm_hr[basin] || [],
      borderColor: COLORS[index],
      backgroundColor: COLORS[index],
      pointRadius: 0,
      borderWidth: 1.6,
      tension: 0.25,
    })),
  };

  return (
    <section className="sg-panel">
      <p className="sg-kicker">SAM 3.1 · NEXRAD object multiplex · 45 min lookahead</p>
      <div className="sg-radar-layout">
        <div>
          <div className="sg-canvas-wrap">
            <canvas ref={canvasRef} width={480} height={480} />
          </div>
          <p className="sg-prompt" title={state.object_prompt}>
            seed {state.object_prompt || "awaiting frame 0"}
          </p>
        </div>
        <div>
          <div className="sg-chart">
            <Line
              data={chartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: { labels: { color: "#9fb4bf", boxWidth: 10, font: { size: 10 } } },
                  tooltip: { enabled: true },
                },
                scales: {
                  x: { ticks: { color: "#7f97a3", maxTicksLimit: 5 }, grid: { color: "#132028" } },
                  y: {
                    ticks: { color: "#7f97a3" },
                    grid: { color: "#132028" },
                    title: { display: true, text: "mm/hr", color: "#7f97a3" },
                    suggestedMax: 70,
                  },
                },
              }}
            />
          </div>
          <div className="mt-2 font-mono text-[11px] text-[#9fb4bf]">
            {Object.entries(state.coverage).map(([name, value]) => (
              <div key={name} className="flex justify-between">
                <span>{name.replaceAll("_", " ")}</span>
                <span>{Math.round(value * 100)}% mask</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function paint(ctx: CanvasRenderingContext2D, image: HTMLImageElement, state: TwinState) {
  const { width, height } = ctx.canvas;
  ctx.clearRect(0, 0, width, height);
  ctx.drawImage(image, 0, 0, width, height);
  const boxes = parseObjectPrompt(state.object_prompt);
  ctx.lineWidth = 1.5;
  boxes.forEach((box) => {
    ctx.strokeStyle = "rgba(255, 62, 200, 0.9)";
    ctx.strokeRect(box.x1 * width, box.y1 * height, (box.x2 - box.x1) * width, (box.y2 - box.y1) * height);
  });
  Object.entries(state.polygons).forEach(([name, rect], index) => {
    const [x1, y1, x2, y2] = rect;
    ctx.strokeStyle = COLORS[index % COLORS.length];
    ctx.strokeRect(x1 * width, y1 * height, (x2 - x1) * width, (y2 - y1) * height);
    ctx.fillStyle = COLORS[index % COLORS.length];
    ctx.font = "12px Consolas, monospace";
    ctx.fillText(name.split("_")[1] || name, x1 * width + 6, y1 * height + 16);
  });
  state.cores.forEach((core) => {
    const x = core.cx * width;
    const y = core.cy * height;
    ctx.beginPath();
    ctx.strokeStyle = core.dbz > 54 ? "rgba(255, 62, 200, 0.95)" : "rgba(62, 224, 255, 0.95)";
    ctx.lineWidth = 2;
    ctx.ellipse(x, y, core.rx * width, core.ry * height, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.strokeStyle = "rgba(255,255,255,0.8)";
    const dx = core.vx_per_min * 8 * width;
    const dy = core.vy_per_min * 8 * height;
    ctx.moveTo(x, y);
    ctx.lineTo(x + dx, y + dy);
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.font = "11px Consolas, monospace";
    ctx.fillText(`${core.dbz.toFixed(0)} dBZ`, x + 8, y - 8);
  });
}
