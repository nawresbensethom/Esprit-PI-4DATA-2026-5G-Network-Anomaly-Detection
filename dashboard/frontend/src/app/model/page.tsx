"use client";

import { useEffect, useRef, useState } from "react";
import { Badge, Button, Icon, Kpi, Panel, fmtPct } from "@/components/ui";
import { AppShell } from "@/components/AppShell";
import {
  getModelMetrics,
  trainReload,
  trainStart,
  trainStatus,
  type ModelMetrics,
  type TrainOptions,
  type TrainStatusResponse,
  type User,
} from "@/lib/api";

function timeAgo(ms: number): string {
  const s = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function ModelPage({ user }: { user: User }) {
  const isAdmin = user.role === "admin";

  const [model, setModel] = useState<ModelMetrics | null>(null);
  const [status, setStatus] = useState<TrainStatusResponse | null>(null);

  // Train form state
  const [aeEpochs, setAeEpochs] = useState(10);
  const [gateEpochs, setGateEpochs] = useState(10);
  const [xgbEstimators, setXgbEstimators] = useState(100);
  const [experiment, setExperiment] = useState("unified_moe");
  const [noMlflow, setNoMlflow] = useState(false);
  const [reloadInference, setReloadInference] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [submitMsg, setSubmitMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Reload state
  const [reloading, setReloading] = useState(false);
  const [reloadMsg, setReloadMsg] = useState<string | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Initial + periodic refresh of model metrics
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const m = await getModelMetrics();
        if (!cancelled) setModel(m);
      } catch {
        if (!cancelled) setModel({ source: "fetch_failed", available: false });
      }
    };
    load();
    const id = setInterval(load, 30000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Initial fetch of training status, then 5s poll if running
  useEffect(() => {
    refreshStatus();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startPolling() {
    if (pollRef.current) return;
    pollRef.current = setInterval(refreshStatus, 5000);
  }

  function stopPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }

  async function refreshStatus() {
    try {
      const s = await trainStatus();
      setStatus(s);
      if (s.running) startPolling(); else stopPolling();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch training status");
    }
  }

  async function handleTrain() {
    setSubmitting(true);
    setError(null);
    setSubmitMsg(null);
    try {
      const opts: TrainOptions = {
        ae_epochs: aeEpochs,
        gate_epochs: gateEpochs,
        xgb_n_estimators: xgbEstimators,
        experiment,
        no_mlflow: noMlflow,
        reload_inference: reloadInference,
      };
      const res = await trainStart(opts);
      setSubmitMsg(res.message);
      startPolling();
      await refreshStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start training");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReload() {
    if (!confirm("Hot-reload the model from disk on the inference service?")) return;
    setReloading(true);
    setReloadMsg(null);
    try {
      await trainReload();
      setReloadMsg("Reload OK — inference service swapped artefacts.");
    } catch (err) {
      setReloadMsg(err instanceof Error ? err.message : "Reload failed");
    } finally {
      setReloading(false);
    }
  }

  const running = status?.running ?? false;
  const last = status?.last_result;

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Model registry</h1>
          <div className="page-desc">
            Trigger training runs, watch live status, and hot-reload the inference service after a successful run.
            All metrics land in MLflow at <span className="mono">/unified_moe</span>.
          </div>
        </div>
      </div>

      {/* KPI strip — current model */}
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

      {/* Train form + Live status */}
      <div className="grid dash-grid" style={{ marginTop: 12 }}>
        <div className="span-5">
          <Panel
            title="Start a training run"
            subtitle="logs to MLflow + auto-reloads inference on success"
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <label className="form-row">
                <span className="muted" style={{ fontSize: 13 }}>AE epochs</span>
                <input
                  type="number" min={1} max={200}
                  value={aeEpochs}
                  disabled={submitting || running}
                  onChange={(e) => setAeEpochs(Number(e.target.value))}
                  className="form-input"
                  style={{ width: 100 }}
                />
              </label>
              <label className="form-row">
                <span className="muted" style={{ fontSize: 13 }}>Gate epochs</span>
                <input
                  type="number" min={1} max={200}
                  value={gateEpochs}
                  disabled={submitting || running}
                  onChange={(e) => setGateEpochs(Number(e.target.value))}
                  className="form-input"
                  style={{ width: 100 }}
                />
              </label>
              <label className="form-row">
                <span className="muted" style={{ fontSize: 13 }}>XGB n_estimators</span>
                <input
                  type="number" min={5} max={500}
                  value={xgbEstimators}
                  disabled={submitting || running}
                  onChange={(e) => setXgbEstimators(Number(e.target.value))}
                  className="form-input"
                  style={{ width: 100 }}
                />
              </label>
              <label className="form-row">
                <span className="muted" style={{ fontSize: 13 }}>Experiment</span>
                <input
                  type="text"
                  value={experiment}
                  disabled={submitting || running}
                  onChange={(e) => setExperiment(e.target.value)}
                  className="form-input"
                  style={{ width: 220 }}
                />
              </label>

              <details>
                <summary className="muted" style={{ fontSize: 12, cursor: "pointer" }}>Advanced</summary>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
                  <label className="row" style={{ gap: 8, fontSize: 12 }}>
                    <input
                      type="checkbox"
                      checked={noMlflow}
                      disabled={submitting || running}
                      onChange={(e) => setNoMlflow(e.target.checked)}
                    />
                    Skip MLflow logging (offline mode)
                  </label>
                  <label className="row" style={{ gap: 8, fontSize: 12 }}>
                    <input
                      type="checkbox"
                      checked={reloadInference}
                      disabled={submitting || running}
                      onChange={(e) => setReloadInference(e.target.checked)}
                    />
                    Auto-reload inference service on success
                  </label>
                </div>
              </details>

              <div className="row" style={{ justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
                <Button variant="ghost" onClick={refreshStatus} disabled={submitting}>
                  Refresh status
                </Button>
                <Button
                  variant="primary"
                  icon="play"
                  onClick={handleTrain}
                  disabled={submitting || running}
                >
                  {running ? "Training in progress…" : submitting ? "Submitting…" : "Start training"}
                </Button>
              </div>

              {submitMsg && !error && (
                <div className="muted" style={{ fontSize: 12, color: "var(--ok)" }}>{submitMsg}</div>
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
            title="Live training status"
            subtitle={running ? "polling every 5s" : "idle"}
            actions={
              <Badge tone={running ? "warn" : last?.success ? "ok" : last ? "critical" : "default"} dot>
                {running ? "running" : last?.success ? "success" : last ? "failed" : "no run yet"}
              </Badge>
            }
          >
            {!status ? (
              <div className="muted" style={{ fontSize: 13, padding: "20px 0" }}>
                Loading status…
              </div>
            ) : !last && !running ? (
              <div className="muted" style={{ fontSize: 13, padding: "20px 0" }}>
                No training run yet. Configure parameters on the left and click Start training.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {running ? (
                  <div className="alert" style={{ background: "var(--bg-subtle)" }}>
                    <Icon name="play" size={14} />
                    <div className="alert-body" style={{ fontSize: 12 }}>
                      Training in progress — page polls every 5 s. Don't close this tab.
                    </div>
                  </div>
                ) : null}

                {last?.reload_inference && (
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <span className="muted" style={{ fontSize: 13 }}>Auto-reload after success</span>
                    <Badge tone={last.reload_inference.ok ? "ok" : "critical"} dot>
                      {last.reload_inference.ok ? "reloaded" : "reload failed"}
                      {last.reload_inference.status_code != null && ` (${last.reload_inference.status_code})`}
                    </Badge>
                  </div>
                )}

                {last?.success && last.output && (
                  <details open>
                    <summary className="muted" style={{ fontSize: 12, cursor: "pointer" }}>Output (tail)</summary>
                    <pre className="mono" style={{ fontSize: 11, marginTop: 8, padding: 12, background: "var(--bg-subtle)", borderRadius: 6, overflow: "auto", maxHeight: 280 }}>
                      {last.output}
                    </pre>
                  </details>
                )}
                {last && !last.success && last.error && (
                  <details open>
                    <summary className="muted" style={{ fontSize: 12, cursor: "pointer", color: "var(--critical)" }}>Error (tail)</summary>
                    <pre className="mono" style={{ fontSize: 11, marginTop: 8, padding: 12, background: "var(--bg-subtle)", borderRadius: 6, overflow: "auto", maxHeight: 280, color: "var(--critical)" }}>
                      {last.error}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </Panel>
        </div>
      </div>

      {/* Actions row */}
      <div className="grid dash-grid" style={{ marginTop: 12 }}>
        <div className="span-6">
          <Panel
            title="Hot-reload model"
            subtitle="admin only · swaps artefacts on the inference service without restart"
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div className="muted" style={{ fontSize: 12 }}>
                Use this after dropping new artefacts directly onto the volume,
                or to verify the inference container picks up a fresh registry promotion.
              </div>
              <div className="row" style={{ justifyContent: "flex-end" }}>
                <Button
                  variant="default"
                  icon="play"
                  onClick={handleReload}
                  disabled={!isAdmin || reloading}
                >
                  {reloading ? "Reloading…" : "Hot-reload"}
                </Button>
              </div>
              {!isAdmin && (
                <div className="muted" style={{ fontSize: 12 }}>
                  Reload requires the <span className="mono">admin</span> role. Logged in as <span className="mono">{user.role}</span>.
                </div>
              )}
              {reloadMsg && (
                <div className="muted" style={{ fontSize: 12 }}>{reloadMsg}</div>
              )}
            </div>
          </Panel>
        </div>

        <div className="span-6">
          <Panel
            title="MLflow registry"
            subtitle="experiments · runs · model versions"
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div className="muted" style={{ fontSize: 12 }}>
                Browse experiments, compare runs, and inspect logged artefacts in the MLflow UI.
                The CD pipeline auto-promotes runs that pass the F1 / recall / PR-AUC thresholds to <span className="mono">Production</span>.
              </div>
              <div className="row" style={{ justifyContent: "flex-end" }}>
                <a
                  href="http://localhost:5000"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-default btn-md"
                >
                  Open MLflow ↗
                </a>
              </div>
            </div>
          </Panel>
        </div>
      </div>

      {/* Help row */}
      <div style={{ marginTop: 12 }}>
        <Panel title="Roles &amp; access" subtitle="who can do what">
          <div className="grid dash-grid">
            <div className="span-4">
              <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
                <Badge tone="default">security_analyst</Badge>
              </div>
              <ul className="muted" style={{ fontSize: 12, margin: 0, paddingLeft: 18 }}>
                <li>No access to this page (gated by AppShell).</li>
                <li>Can run scans on /upload.</li>
              </ul>
            </div>
            <div className="span-4">
              <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
                <Badge tone="accent">data_scientist</Badge>
              </div>
              <ul className="muted" style={{ fontSize: 12, margin: 0, paddingLeft: 18 }}>
                <li>Trigger training, watch status.</li>
                <li>Cannot hot-reload the model.</li>
              </ul>
            </div>
            <div className="span-4">
              <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 6 }}>
                <Badge tone="critical">admin</Badge>
              </div>
              <ul className="muted" style={{ fontSize: 12, margin: 0, paddingLeft: 18 }}>
                <li>All training actions.</li>
                <li>Hot-reload, manage users &amp; thresholds.</li>
              </ul>
            </div>
          </div>
        </Panel>
      </div>
    </>
  );
}

export default function ModelRoute() {
  return (
    <AppShell
      crumbs={["Models", "Model registry"]}
      roles={["admin", "data_scientist"]}
    >
      {(user) => <ModelPage user={user} />}
    </AppShell>
  );
}
