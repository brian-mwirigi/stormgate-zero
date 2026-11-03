export type ModelState = {
  status: string;
  latency_ms: number | null;
};

export type Rollout = {
  name: string;
  total_cso_overflow_gallons: number;
  max_basin_fill_pct: number;
  street_flooding_gallons: number;
  downstream_wwtp_utilization_pct: number;
  first_action?: number[];
};

export type Core = {
  id: number;
  name: string;
  cx: number;
  cy: number;
  rx: number;
  ry: number;
  dbz: number;
  vx_per_min: number;
  vy_per_min: number;
};

export type Turn = {
  speaker: string;
  role: string;
  text: string;
  t_min?: number;
};

export type Fault = {
  type: string;
  orifice_id?: string;
  locked_setting?: number;
  speaker?: string;
  role?: string;
  raw?: string;
};

export type TwinState = {
  t_min: number;
  step: number;
  steps_total: number;
  running: boolean;
  done: boolean;
  cso_baseline_gal: number;
  cso_stormgate_gal: number;
  street_baseline_gal: number;
  street_stormgate_gal: number;
  baseline_depth: number[];
  stormgate_depth: number[];
  baseline_orifice: number[];
  stormgate_orifice: number[];
  jammed: Record<string, number>;
  forecast_mm_hr: Record<string, number[]>;
  coverage: Record<string, number>;
  cores: Core[];
  object_prompt: string;
  rollouts: Rollout[];
  selected: string | null;
  commentary: string;
  wonder_note: string;
  glimmer: { approved: boolean; summary: string; source?: string };
  models: Record<string, ModelState>;
  transcript: Turn[];
  faults: Fault[];
  depth_history: { baseline: number[][]; stormgate: number[][] };
  outfall_ready: boolean;
  polygons: Record<string, number[]>;
  storm: { id: string; title: string; kind: string; note: string };
  refine_note: string;
  exposure: {
    baseline: Exposure;
    stormgate: Exposure;
  };
  wave: WaveReport | null;
};

export type Exposure = {
  statutory_usd: number;
  statutory_per_day_usd: number;
  violation_days: number;
  citation: string;
  ecoli_cfu_per_100ml: number;
  beach_action_cfu_per_100ml: number;
  above_beach_action: boolean;
  label: string;
};

export type WavePipe = {
  link: string;
  max_depth_ft: number;
  diameter_ft: number;
  surcharge_ft: number;
  surcharge_m: number;
  surcharge_psi: number;
};

export type WaveReport = {
  ok: boolean;
  engine?: string;
  error?: string;
  worst_link?: string;
  worst_surcharge_ft?: number;
  worst_surcharge_m?: number;
  worst_surcharge_psi?: number;
  pipes?: WavePipe[];
  note?: string;
};
