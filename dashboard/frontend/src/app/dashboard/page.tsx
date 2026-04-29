"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, Button, Icon, Kpi, Panel, fmtN, fmtPct } from "@/components/ui";
import { AppShell } from "@/components/AppShell";
import {
  driftLast,
  driftRun,
  getModelMetrics,
  listHistory,
  type DriftReport,
  type HistoryEntry,
  type ModelMetrics,
  type User,
} from "@/lib/api";

type HealthState = "ok" | "down" | "loading";

function timeAgo(ms: number): string {
  const s = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function todayCounts(history: HistoryEntry[]): { runs: number; rows: number; attacks: number } {
  const startOfDay = new Date();
  startOfDay.setHours(0, 0, 0, 0);
  const cutoff = startOfDay.getTime();
  const today = history.filter((h) => h.ts >= cutoff);
  return {
    runs: today.length,
    rows: today.reduce((acc, h) => acc + h.n_rows, 0),
    attacks: today.reduce(
      (acc, h) => acc + Math.round(h.n_rows * h.attack_rate),
      0,
    ),
  };
}

function driftTone(report: DriftReport | null): "ok" | "warn" | "critical" | "default" {
  if (!report) return "default";
  if (report.status === "drift_detected") return "critical";
  if (report.status === "ok") return "ok";
  if (report.status === "no_data" || report.status === "no_run_yet") return "default";
  return "warn";
}

function HealthBadge({ state }: { state: HealthState }) {
  if (state === "loading") return <Badge tone="default" dot>checking…</Badge>;
  if (state === "ok") return <Badge tone="ok" dot>healthy</Badge>;
  return <Badge tone="critical" dot>unreachable</Badge>;
}

function DashboardPage({ user }: { user: User }) {
  const canRunDrift = user.role === "admin" || user.role === "data_scientist";

  const [model, setModel] = useState<ModelMetrics | null>(null);
  const [drift, setDrift] = useState<DriftReport | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [gwHealth, setGwHealth] = useState<HealthState>("loading");
  const [infHealth, setInfHealth] = useState<HealthState>("loading");
  const [runningDrift, setRunningDrift] = useState(false);
  const [driftError, setDriftError] = useState<string | null>(null);

  useEffect(() => { setHistory(listHistory()); }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const m = await getModelMetrics();
        if (!cancelled) setModel(m);
      } catch {
        if (!cancelled) setModel({ source: "fetch_failed", available: false });
      }
      try {
        const d = await driftLast();
        if (!cancelled) setDrift(d);
      } catch {
        if (!cancelled) setDrift(null);
      }
    };
    load();
    const id = setInterval(load, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8090";
    const token = (typeof window !== "undefined" && localStorage.getItem("sentra_token")) || "";

    const probe = async (path: string, withAuth: boolean) => {
      try {
        const headers: Record<string, string> = {};
        if (withAuth && token) headers["Authorization"] = `Bearer ${token}`;
        const r = await fetch(`${apiBase}${path}`, { headers });
        return r.ok ? "ok" : "down";
      } catch { return "down"; }
    };

    (async () => {
      setGwHealth((await probe("/health", false)) as HealthState);
      setInfHealth((await probe("/api/predict/health", true)) as HealthState);
    })();
  }, []);

  async function handleRunDrift() {
    setRunningDrift(true);
    setDriftError(null);
    try {
      const report = await driftRun({});
      setDrift(report);
    } catch (err) {
      setDriftError(err instanceof Error ? err.message : "Drift check failed");
    } finally {
      setRunningDrift(false);
    }
  }

  const today = todayCounts(history);

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <div className="page-desc">
            Live model quality, recent activity, and system health for the unified MoE IDS platform.
          </div>
        </div>
      </div>

      {/* Row 1 — Model quality */}
      <div className="grid dash-grid">
        <div className="span-3">
          <Kpi
            label="Model accuracy"
            value={model?.accuracy != null ? fmtPct(model.accuracy) : "—"}
            sub={model?.run_name ?? model?.source ?? "fetching…"}
            accent
          />
        </div>
        <div className="span-3">
          <Kpi label="F1" value={model?.f1 != null ? model.f1.toFixed(3) : "—"} />
        </div>
        <div className="span-3">
          <Kpi label="ROC AUC" value={model?.auc_roc != null ? model.auc_roc.toFixed(3) : "—"} />
        </div>
        <div className="span-3">
          <Kpi
            label="Last training"
            value={model?.end_time_ms ? timeAgo(model.end_time_ms) : "—"}
            sub={model?.run_id ? model.run_id.slice(0, 8) : "no runs yet"}
          />
        </div>
      </div>

      {/* Row 2 — Operational KPIs */}
      <div className="grid dash-grid" style={{ marginTop: 12 }}>
        <div className="span-3">
          <Kpi label="Scans today" value={fmtN(today.runs)} sub={`${fmtN(today.rows)} rows`} />
        </div>
        <div className="span-3">
          <Kpi
            label="Attacks today"
            value={fmtN(today.attacks)}
            sub={today.rows ? fmtPct(today.attacks / today.rows) + " of traffic" : "no traffic"}
          />
        </div>
        <div className="span-3">
          <Kpi
            label="Drift PSI"
            value={drift?.psi_attack_rate != null ? drift.psi_attack_rate.toFixed(3) : "—"}
            sub={drift?.status ?? "no run yet"}
          />
        </div>
        <div className="span-3">
          <Kpi
            label="History entries"
            value={fmtN(history.length)}
            sub="local cache (Phase B → DB)"
          />
        </div>
      </div>

      {/* Row 3 — Recent activity + Drift status */}
      <div className="grid dash-grid" style={{ marginTop: 12 }}>
        <div className="span-8">
          <Panel
            title="Recent scans"
            subtitle={history.length ? `${history.length} in local history` : "no scans yet"}
            actions={
              user.role === "security_analyst" || user.role === "admin" ? (
                <Link href="/upload"><Button variant="primary" icon="upload">New scan</Button></Link>
              ) : null
            }
          >
            {history.length === 0 ? (
              <div className="muted" style={{ fontSize: 13, padding: "20px 0" }}>
                No scans yet. Run one from <Link href="/upload" style={{ color: "var(--accent)" }}>New scan</Link> to see results here.
              </div>
            ) : (
              <div className="tbl-wrap" style={{ maxHeight: 360, overflow: "auto" }}>
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>File</th>
                      <th>Schema</th>
                      <th className="num">Rows</th>
                      <th className="num">Attack rate</th>
                      <th>By</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.slice(0, 5).map((h) => (
                      <tr key={h.request_id}>
                        <td className="muted">{timeAgo(h.ts)}</td>
                        <td className="mono" style={{ fontSize: 12 }}>{h.filename}</td>
                        <td><Badge tone="default">{h.schema}</Badge></td>
                        <td className="num">{fmtN(h.n_rows)}</td>
                        <td className="num">{fmtPct(h.attack_rate)}</td>
                        <td className="muted" style={{ fontSize: 12 }}>{h.user_email}</td>
                        <td>
                          <Link href={`/results/${h.request_id}`} style={{ color: "var(--accent)", fontSize: 12 }}>
                            View →
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        <div className="span-4">
          <Panel
            title="Drift status"
            subtitle={drift?.window_days ? `last ${drift.window_days}d window` : ""}
            actions={
              canRunDrift ? (
                <Button
                  variant="default"
                  icon="play"
                  onClick={handleRunDrift}
                  disabled={runningDrift}
                >
                  {runningDrift ? "Running…" : "Run check"}
                </Button>
              ) : null
            }
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="muted" style={{ fontSize: 13 }}>Status</span>
                <Badge tone={driftTone(drift)} dot>
                  {drift?.status ?? "no run yet"}
                </Badge>
              </div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="muted" style={{ fontSize: 13 }}>PSI (attack rate)</span>
                <span className="mono" style={{ fontSize: 13 }}>
                  {drift?.psi_attack_rate != null ? drift.psi_attack_rate.toFixed(4) : "—"}
                </span>
              </div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="muted" style={{ fontSize: 13 }}>Threshold</span>
                <span className="mono" style={{ fontSize: 13 }}>{drift?.psi_threshold ?? "—"}</span>
              </div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="muted" style={{ fontSize: 13 }}>Recent / baseline</span>
                <span className="mono" style={{ fontSize: 13 }}>
                  {drift?.recent_mean_attack_rate != null && drift?.baseline_attack_rate != null
                    ? `${drift.recent_mean_attack_rate.toFixed(3)} / ${drift.baseline_attack_rate.toFixed(3)}`
                    : "—"}
                </span>
              </div>
              {drift?.alerts?.length ? (
                <div className="alert alert-crit" style={{ marginTop: 4 }}>
                  <Icon name="warn" size={14} />
                  <div>
                    <div className="alert-body" style={{ fontSize: 12 }}>
                      {drift.alerts.join(" · ")}
                    </div>
                  </div>
                </div>
              ) : null}
              {driftError ? (
                <div className="muted" style={{ fontSize: 12, color: "var(--critical)" }}>{driftError}</div>
              ) : null}
            </div>
          </Panel>
        </div>
      </div>

      {/* Row 4 — System health */}
      <div className="grid dash-grid" style={{ marginTop: 12 }}>
        <div className="span-3">
          <Panel title="Gateway" subtitle=":8090">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="muted" style={{ fontSize: 13 }}>/health</span>
              <HealthBadge state={gwHealth} />
            </div>
          </Panel>
        </div>
        <div className="span-3">
          <Panel title="Inference upstream" subtitle="moe-inference-svc">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="muted" style={{ fontSize: 13 }}>/api/predict/health</span>
              <HealthBadge state={infHealth} />
            </div>
          </Panel>
        </div>
        <div className="span-3">
          <Panel title="MLflow" subtitle=":5000">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="muted" style={{ fontSize: 13 }}>open in tab</span>
              <a href="http://localhost:5000" target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent)", fontSize: 13 }}>
                Open ↗
              </a>
            </div>
          </Panel>
        </div>
        <div className="span-3">
          <Panel title="Grafana" subtitle=":3001">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span className="muted" style={{ fontSize: 13 }}>open in tab</span>
              <a href="http://localhost:3001" target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent)", fontSize: 13 }}>
                Open ↗
              </a>
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}

export default function DashboardRoute() {
  return (
    <AppShell crumbs={["Workspace", "Dashboard"]}>
      {(user) => <DashboardPage user={user} />}
    </AppShell>
  );
}
