"use client";

import { useEffect, useState } from "react";
import { Badge, Button, Icon, Kpi, Panel } from "@/components/ui";
import { AppShell } from "@/components/AppShell";
import {
  driftLast,
  driftRun,
  type DriftReport,
  type User,
} from "@/lib/api";

function timeAgoOrNever(ts: number | null): string {
  if (!ts) return "never";
  const s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function driftTone(report: DriftReport | null): "ok" | "warn" | "critical" | "default" {
  if (!report) return "default";
  if (report.status === "drift_detected") return "critical";
  if (report.status === "ok") return "ok";
  if (report.status === "no_data" || report.status === "no_run_yet") return "default";
  return "warn";
}

/**
 * Visual PSI gauge. Renders a horizontal bar with two threshold marks
 * (yellow at 0.1, red at 0.2) and a needle at the current value.
 */
function PsiGauge({ value, threshold = 0.2 }: { value: number | null; threshold?: number }) {
  const cap = Math.max(threshold * 2, 0.5);
  const pct = value == null ? 0 : Math.min(value / cap, 1) * 100;
  const yellowAt = (0.1 / cap) * 100;
  const redAt = (threshold / cap) * 100;

  return (
    <div style={{ width: "100%" }}>
      <div style={{ position: "relative", height: 14, borderRadius: 6, overflow: "hidden", background: "var(--bg-subtle)" }}>
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(to right, var(--ok) 0%, var(--ok) " + yellowAt + "%, var(--warn) " + yellowAt + "%, var(--warn) " + redAt + "%, var(--critical) " + redAt + "%, var(--critical) 100%)", opacity: 0.25 }} />
        {value != null && (
          <div style={{ position: "absolute", left: `calc(${pct}% - 1px)`, top: 0, bottom: 0, width: 2, background: "var(--fg)" }} />
        )}
      </div>
      <div className="row muted" style={{ fontSize: 11, marginTop: 6, justifyContent: "space-between" }}>
        <span>0.00 (no shift)</span>
        <span>0.10 (monitor)</span>
        <span>{threshold.toFixed(2)} (alert)</span>
        <span>{cap.toFixed(2)}</span>
      </div>
    </div>
  );
}

function DriftPage({ user }: { user: User }) {
  const canRun = user.role === "admin" || user.role === "data_scientist";

  const [report, setReport] = useState<DriftReport | null>(null);
  const [lastChecked, setLastChecked] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  // Form inputs for the manual run
  const [windowDays, setWindowDays] = useState(7);
  const [psiThreshold, setPsiThreshold] = useState(0.2);
  const [ksThreshold, setKsThreshold] = useState(0.05);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      const r = await driftLast();
      setReport(r);
      if (r.status !== "no_run_yet") setLastChecked(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch drift report");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      const r = await driftRun({
        window_days: windowDays,
        psi_threshold: psiThreshold,
        ks_p_threshold: ksThreshold,
      });
      setReport(r);
      setLastChecked(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Drift check failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Drift &amp; fairness</h1>
          <div className="page-desc">
            Population Stability Index (PSI) on attack-rate distribution + KS test on probability scores.
            Compares recent prediction logs against the training baseline.
          </div>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid dash-grid">
        <div className="span-3">
          <Kpi
            label="Current PSI"
            value={report?.psi_attack_rate != null ? report.psi_attack_rate.toFixed(4) : "—"}
            sub={report?.psi_threshold != null ? `threshold ${report.psi_threshold}` : ""}
            accent={report?.status === "drift_detected"}
          />
        </div>
        <div className="span-3">
          <Panel title="Status">
            <div style={{ padding: "8px 0" }}>
              <Badge tone={driftTone(report)} dot>
                {report?.status ?? (loading ? "loading…" : "no run yet")}
              </Badge>
            </div>
          </Panel>
        </div>
        <div className="span-3">
          <Kpi
            label="Window"
            value={report?.window_days != null ? `${report.window_days}d` : "—"}
          />
        </div>
        <div className="span-3">
          <Kpi
            label="Requests in window"
            value={report?.n_requests != null ? report.n_requests.toString() : "—"}
            sub={`last checked ${timeAgoOrNever(lastChecked)}`}
          />
        </div>
      </div>

      {/* PSI gauge */}
      <div style={{ marginTop: 12 }}>
        <Panel title="PSI on attack rate" subtitle="green = stable · yellow = monitor · red = alert">
          <div style={{ padding: "12px 0" }}>
            <PsiGauge
              value={report?.psi_attack_rate ?? null}
              threshold={report?.psi_threshold ?? 0.2}
            />
          </div>
        </Panel>
      </div>

      {/* Run controls + Report details */}
      <div className="grid dash-grid" style={{ marginTop: 12 }}>
        <div className="span-5">
          <Panel
            title="Run drift check"
            subtitle={canRun ? "admin · data_scientist" : "read-only — admin/data_scientist required"}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <label className="form-row">
                <span className="muted" style={{ fontSize: 13 }}>Window (days)</span>
                <input
                  type="number"
                  min={1}
                  max={90}
                  value={windowDays}
                  disabled={!canRun || running}
                  onChange={(e) => setWindowDays(Number(e.target.value))}
                  className="form-input"
                  style={{ width: 100 }}
                />
              </label>
              <label className="form-row">
                <span className="muted" style={{ fontSize: 13 }}>PSI threshold</span>
                <input
                  type="number"
                  step={0.05}
                  min={0}
                  max={1}
                  value={psiThreshold}
                  disabled={!canRun || running}
                  onChange={(e) => setPsiThreshold(Number(e.target.value))}
                  className="form-input"
                  style={{ width: 100 }}
                />
              </label>
              <label className="form-row">
                <span className="muted" style={{ fontSize: 13 }}>KS p-threshold</span>
                <input
                  type="number"
                  step={0.01}
                  min={0}
                  max={1}
                  value={ksThreshold}
                  disabled={!canRun || running}
                  onChange={(e) => setKsThreshold(Number(e.target.value))}
                  className="form-input"
                  style={{ width: 100 }}
                />
              </label>

              <div className="row" style={{ justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
                <Button variant="ghost" onClick={refresh} disabled={loading}>
                  Refresh last report
                </Button>
                {canRun && (
                  <Button variant="primary" icon="play" onClick={handleRun} disabled={running}>
                    {running ? "Running…" : "Run drift check"}
                  </Button>
                )}
              </div>

              {!canRun && (
                <div className="muted" style={{ fontSize: 12 }}>
                  You can view drift reports but not trigger new runs. Sign in as <span className="mono">admin</span> or <span className="mono">data_scientist</span>.
                </div>
              )}
              {error && (
                <div className="alert alert-crit">
                  <Icon name="warn" size={14} />
                  <div className="alert-body" style={{ fontSize: 12 }}>{error}</div>
                </div>
              )}
            </div>
          </Panel>
        </div>

        <div className="span-7">
          <Panel
            title="Last report"
            subtitle={report?.status ?? "—"}
            actions={
              report?.alerts?.length
                ? <Badge tone="critical" dot>{report.alerts.length} alert{report.alerts.length === 1 ? "" : "s"}</Badge>
                : null
            }
          >
            {report == null || report.status === "no_run_yet" ? (
              <div className="muted" style={{ fontSize: 13, padding: "20px 0" }}>
                No drift report yet. {canRun && "Click Run drift check to generate one."}
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="muted" style={{ fontSize: 13 }}>Baseline attack rate</span>
                  <span className="mono" style={{ fontSize: 13 }}>
                    {report.baseline_attack_rate != null ? report.baseline_attack_rate.toFixed(4) : "—"}
                  </span>
                </div>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="muted" style={{ fontSize: 13 }}>Recent attack rate</span>
                  <span className="mono" style={{ fontSize: 13 }}>
                    {report.recent_mean_attack_rate != null ? report.recent_mean_attack_rate.toFixed(4) : "—"}
                  </span>
                </div>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="muted" style={{ fontSize: 13 }}>KS statistic</span>
                  <span className="mono" style={{ fontSize: 13 }}>
                    {report.ks_statistic != null ? report.ks_statistic.toFixed(4) : "—"}
                  </span>
                </div>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="muted" style={{ fontSize: 13 }}>KS p-value</span>
                  <span className="mono" style={{ fontSize: 13 }}>
                    {report.ks_p_value != null ? report.ks_p_value.toFixed(4) : "—"}
                  </span>
                </div>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span className="muted" style={{ fontSize: 13 }}>KS p-threshold</span>
                  <span className="mono" style={{ fontSize: 13 }}>
                    {report.ks_p_threshold ?? "—"}
                  </span>
                </div>

                {report.alerts?.length ? (
                  <div className="alert alert-crit" style={{ marginTop: 8 }}>
                    <Icon name="warn" size={14} />
                    <div>
                      <div className="alert-title">Alerts</div>
                      <ul style={{ margin: "4px 0 0 18px", padding: 0, fontSize: 12 }}>
                        {report.alerts.map((a, i) => <li key={i}>{a}</li>)}
                      </ul>
                    </div>
                  </div>
                ) : null}

                <details style={{ marginTop: 12 }}>
                  <summary className="muted" style={{ fontSize: 12, cursor: "pointer" }}>Raw JSON</summary>
                  <pre className="mono" style={{ fontSize: 11, marginTop: 8, padding: 12, background: "var(--bg-subtle)", borderRadius: 6, overflow: "auto", maxHeight: 200 }}>
                    {JSON.stringify(report, null, 2)}
                  </pre>
                </details>
              </div>
            )}
          </Panel>
        </div>
      </div>

      {/* Help panel */}
      <div style={{ marginTop: 12 }}>
        <Panel title="What does PSI mean?" subtitle="quick reference">
          <div className="grid dash-grid">
            <div className="span-4">
              <div className="row" style={{ alignItems: "flex-start", gap: 10 }}>
                <Badge tone="ok" dot>OK</Badge>
                <div style={{ fontSize: 12 }}>
                  <div style={{ fontWeight: 500 }}>PSI &lt; 0.1</div>
                  <div className="muted">No significant distribution shift.</div>
                </div>
              </div>
            </div>
            <div className="span-4">
              <div className="row" style={{ alignItems: "flex-start", gap: 10 }}>
                <Badge tone="warn" dot>Monitor</Badge>
                <div style={{ fontSize: 12 }}>
                  <div style={{ fontWeight: 500 }}>0.1 ≤ PSI &lt; threshold</div>
                  <div className="muted">Moderate shift — keep watching.</div>
                </div>
              </div>
            </div>
            <div className="span-4">
              <div className="row" style={{ alignItems: "flex-start", gap: 10 }}>
                <Badge tone="critical" dot>Alert</Badge>
                <div style={{ fontSize: 12 }}>
                  <div style={{ fontWeight: 500 }}>PSI ≥ threshold</div>
                  <div className="muted">Investigate, retrain, or review labels.</div>
                </div>
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </>
  );
}

export default function DriftRoute() {
  return (
    <AppShell
      crumbs={["Models", "Drift & fairness"]}
      roles={["admin", "data_scientist"]}
    >
      {(user) => <DriftPage user={user} />}
    </AppShell>
  );
}
