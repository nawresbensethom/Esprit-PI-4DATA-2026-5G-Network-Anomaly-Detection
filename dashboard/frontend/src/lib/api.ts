const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
const TOKEN_KEY = "sentra_token";
const USER_KEY = "sentra_user";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "analyst" | "admin" | "ml_engineer";
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
    let detail: unknown;
    try { detail = await resp.json(); } catch { detail = await resp.text(); }
    const message = typeof detail === "object" && detail && "detail" in detail
      ? String((detail as { detail: unknown }).detail)
      : `HTTP ${resp.status}`;
    throw new Error(message);
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