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
};
