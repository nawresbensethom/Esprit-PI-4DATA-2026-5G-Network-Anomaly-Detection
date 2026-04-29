"use client";

import { useEffect, useState } from "react";
import { Badge, Icon, Kpi, Panel } from "@/components/ui";
import { AppShell } from "@/components/AppShell";
import { getModelMetrics, type ModelMetrics, type User } from "@/lib/api";

// Mirror of moe-ids/moe_ids/config.py defaults. Read-only here — the source
// of truth lives in the Python settings; this page surfaces them for the jury.
const PROMOTION_THRESHOLDS = [
  { key: "min_f1",     label: "Minimum F1",     value: 0.90, severity: "ok" as const },
  { key: "min_recall", label: "Minimum Recall", value: 0.95, severity: "ok" as const },
  { key: "min_pr_auc", label: "Minimum PR-AUC", value: 0.92, severity: "ok" as const },
];

const DRIFT_THRESHOLDS = [
  { key: "psi_threshold", label: "PSI threshold (attack-rate)", value: 0.20, note: "PSI ≥ this fires drift alert" },
  { key: "ks_p_threshold", label: "KS p-value threshold",       value: 0.05, note: "KS p < this fires distribution alert" },
];

const INFERENCE_LIMITS = [
  { key: "max_batch_file_mb", label: "Max batch file size",  value: "100 MB" },
  { key: "prediction_threshold", label: "Decision threshold (P > x → attack)", value: 0.50 },
];

function SettingsPage(_: { user: User }) {
  const [model, setModel] = useState<ModelMetrics | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const m = await getModelMetrics();
        if (!cancelled) setModel(m);
      } catch {
        if (!cancelled) setModel({ source: "fetch_failed", available: false });
      }
    })();
  }, []);

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Thresholds &amp; config</h1>
          <div className="page-desc">
            Read-only view of the values that govern training promotion, drift detection, and inference behaviour.
            The source of truth is <span className="mono">moe-ids/moe_ids/config.py</span>; edit there + redeploy to change.
          </div>
        </div>
      </div>

      {/* Model snapshot */}
      <div className="grid dash-grid">
        <div className="span-3">
          <Kpi
            label="Active model"
            value={model?.run_id ? model.run_id.slice(0, 8) : "—"}
            sub={model?.experiment ?? "unified_moe"}
            accent
          />
        </div>
        <div className="span-3">
          <Kpi
            label="Source"
            value={model?.source ?? "—"}
            sub={model?.available ? "live" : "fallback / unavailable"}
          />
        </div>
        <div className="span-3">
          <Kpi
            label="Last F1"
            value={model?.f1 != null ? model.f1.toFixed(3) : "—"}
            sub={model?.f1 != null && model.f1 >= 0.9 ? "above promotion gate" : "below gate"}
          />
        </div>
        <div className="span-3">
          <Kpi
            label="Source version"
            value={model?.run_name ?? "—"}
            sub={model?.status ?? "—"}
          />
        </div>
      </div>

      {/* Promotion thresholds */}
      <div style={{ marginTop: 12 }}>
        <Panel title="Model promotion gate" subtitle="scripts/promote.py uses these to gate Production transitions">
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Setting</th>
                  <th>Key</th>
                  <th className="num">Threshold</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {PROMOTION_THRESHOLDS.map((t) => {
                  const got = (model && (model as Record<string, unknown>)[t.key.replace("min_", "")]) as number | undefined;
                  const passes = typeof got === "number" && got >= t.value;
                  return (
                    <tr key={t.key}>
                      <td>{t.label}</td>
                      <td className="mono muted" style={{ fontSize: 12 }}>{t.key}</td>
                      <td className="num mono">{t.value.toFixed(2)}</td>
                      <td>
                        {got == null
                          ? <Badge tone="default">no run</Badge>
                          : passes
                            ? <Badge tone="ok" dot>{got.toFixed(3)} — passes</Badge>
                            : <Badge tone="critical" dot>{got.toFixed(3)} — fails</Badge>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      {/* Drift thresholds */}
      <div style={{ marginTop: 12 }}>
        <Panel title="Drift detection" subtitle="services/monitoring/routes_drift.py default thresholds">
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Setting</th>
                  <th>Key</th>
                  <th className="num">Default</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {DRIFT_THRESHOLDS.map((t) => (
                  <tr key={t.key}>
                    <td>{t.label}</td>
                    <td className="mono muted" style={{ fontSize: 12 }}>{t.key}</td>
                    <td className="num mono">{t.value.toFixed(2)}</td>
                    <td className="muted" style={{ fontSize: 12 }}>{t.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      {/* Inference limits */}
      <div style={{ marginTop: 12 }}>
        <Panel title="Inference limits" subtitle="moe_ids/config.py">
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Setting</th>
                  <th>Key</th>
                  <th className="num">Value</th>
                </tr>
              </thead>
              <tbody>
                {INFERENCE_LIMITS.map((t) => (
                  <tr key={t.key}>
                    <td>{t.label}</td>
                    <td className="mono muted" style={{ fontSize: 12 }}>{t.key}</td>
                    <td className="num mono">{String(t.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      {/* How to change */}
      <div style={{ marginTop: 12 }}>
        <Panel title="How to change these">
          <div className="alert" style={{ background: "var(--bg-subtle)" }}>
            <Icon name="warn" size={14} />
            <div className="alert-body" style={{ fontSize: 12 }}>
              These values are baked into the running services at boot via
              <span className="mono"> pydantic-settings</span>. Edit
              <span className="mono"> moe-ids/moe_ids/config.py</span>, push, let CI/CD redeploy,
              and the new thresholds take effect. A future iteration could expose live edits via
              an admin endpoint — for now, code is the source of truth.
            </div>
          </div>
        </Panel>
      </div>
    </>
  );
}

export default function SettingsRoute() {
  return (
    <AppShell crumbs={["Administration", "Thresholds & config"]} roles={["admin"]}>
      {(user) => <SettingsPage user={user} />}
    </AppShell>
  );
}
