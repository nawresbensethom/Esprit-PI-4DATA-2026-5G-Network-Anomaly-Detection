const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
const TOKEN_KEY = "sentra_token";
const USER_KEY = "sentra_user";

export type Role = "security_analyst" | "admin" | "data_scientist";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface BatchPrediction {
  request_id: string;
  model_version: string;
  schema: string;
  n_rows: number;
  predictions: number[];
  probabilities: number[];
  gate_weights: number[][];
  expert_order: string[];
  summary: {
    n_attack_predicted: number;
    n_benign_predicted: number;
    mean_probability: number;
    attack_rate: number;
  };
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setSession(token: string, user: User): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    // Auto-redirect on expired/invalid JWT — token is dead, no point staying on the page
    if (resp.status === 401 && typeof window !== "undefined" && !path.startsWith("/api/auth/")) {
      clearSession();
      window.location.href = "/login";
      throw new Error("Session expired — please sign in again");
    }
    let body: unknown;
    try { body = await resp.json(); } catch { body = await resp.text(); }

    // Unwrap FastAPI-style {"detail": ...} where ... is a string OR a dict OR an array
    let detail: unknown = body;
    if (body && typeof body === "object" && "detail" in body) {
      detail = (body as { detail: unknown }).detail;
    }

    let message: string;
    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object") {
      // Pretty-print the structured error so the user sees the real cause
      try {
        message = JSON.stringify(detail, null, 2);
      } catch {
        message = `HTTP ${resp.status}`;
      }
    } else {
      message = `HTTP ${resp.status}`;
    }

    throw new Error(`HTTP ${resp.status} — ${message}`);
  }
  return resp.json() as Promise<T>;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const data = await request<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setSession(data.access_token, data.user);
  return data;
}

export async function predictBatch(file: File): Promise<BatchPrediction> {
  const form = new FormData();
  form.append("file", file);
  return request<BatchPrediction>("/api/predict/batch", {
    method: "POST",
    body: form,
  });
}

// ── Live model metrics (from MLflow last run, or baseline_stats fallback) ──

export interface ModelMetrics {
  source: string;
  available: boolean;
  run_id?: string;
  run_name?: string;
  experiment?: string;
  end_time_ms?: number;
  status?: string;
  accuracy?: number | null;
  f1?: number | null;
  recall?: number | null;
  pr_auc?: number | null;
  auc_roc?: number | null;
  version?: string;
  error?: string;
}

export async function getModelMetrics(): Promise<ModelMetrics> {
  return request<ModelMetrics>("/api/predict/metrics");
}

// ── Local history persistence (no DB yet — Phase B) ──────────────────────

const HISTORY_KEY = "sentra_history";
const HISTORY_LIMIT = 50;

export interface HistoryEntry {
  request_id: string;
  ts: number;                 // unix ms
  filename: string;
  schema: string;
  n_rows: number;
  attack_rate: number;
  model_version: string;
  user_email: string;
  prediction: BatchPrediction;
}

export function listHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? (JSON.parse(raw) as HistoryEntry[]) : [];
  } catch {
    return [];
  }
}

export function getHistoryEntry(requestId: string): HistoryEntry | null {
  return listHistory().find((e) => e.request_id === requestId) ?? null;
}

export function appendHistory(entry: HistoryEntry): void {
  if (typeof window === "undefined") return;
  const all = listHistory();
  all.unshift(entry);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(all.slice(0, HISTORY_LIMIT)));
}

export function clearHistory(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(HISTORY_KEY);
}

// ── Training ─────────────────────────────────────────────────────────────

export interface TrainOptions {
  data_5g?: string;
  data_6g?: string;
  artefacts_dir?: string;
  seed?: number;
  ae_epochs?: number;
  gate_epochs?: number;
  xgb_n_estimators?: number;
  mlflow_tracking_uri?: string;
  experiment?: string;
  no_mlflow?: boolean;
  reload_inference?: boolean;
}

export interface TrainStartResponse {
  status: "accepted" | string;
  message: string;
}

export interface TrainStatusResponse {
  running: boolean;
  last_result: null | {
    success: boolean;
    output?: string;
    error?: string;
    reload_inference?: { status_code: number | null; ok: boolean; error?: string };
  };
}

export async function trainStart(options: TrainOptions = {}): Promise<TrainStartResponse> {
  return request<TrainStartResponse>("/api/train/start", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export async function trainStatus(): Promise<TrainStatusResponse> {
  return request<TrainStatusResponse>("/api/train/status");
}

export async function trainReload(): Promise<void> {
  await request<void>("/api/train/reload", { method: "POST" });
}

// ── Drift / monitoring ───────────────────────────────────────────────────

export interface DriftOptions {
  window_days?: number;
  psi_threshold?: number;
  ks_p_threshold?: number;
}

export interface DriftReport {
  status: "ok" | "drift_detected" | "no_data" | "no_run_yet" | string;
  window_days?: number;
  n_requests?: number;
  baseline_attack_rate?: number;
  recent_mean_attack_rate?: number;
  psi_attack_rate?: number;
  psi_threshold?: number;
  ks_statistic?: number;
  ks_p_value?: number;
  ks_p_threshold?: number;
  alerts?: string[];
}

export async function driftRun(options: DriftOptions = {}): Promise<DriftReport> {
  return request<DriftReport>("/api/drift/run", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export async function driftLast(): Promise<DriftReport> {
  return request<DriftReport>("/api/drift/last");
}