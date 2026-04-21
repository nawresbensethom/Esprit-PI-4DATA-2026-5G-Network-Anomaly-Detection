"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";
import { useRouter } from "next/navigation";
import { Badge, Button, Icon, Kpi, Mark, Panel, cls, fmtN, fmtPct } from "@/components/ui";
import { clearSession, getUser, predictBatch, type BatchPrediction, type User } from "@/lib/api";

type Stage = "idle" | "ready" | "running" | "done" | "error";

export default function UploadPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BatchPrediction | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const u = getUser();
    if (!u) router.replace("/login");
    else setUser(u);
  }, [router]);

  function pick() { inputRef.current?.click(); }

  function handleFile(f: File | null | undefined) {
    if (!f) return;
    setFile(f);
    setStage("ready");
    setError(null);
    setResult(null);
  }

  function reset() {
    setFile(null);
    setStage("idle");
    setError(null);
    setResult(null);
  }

  async function runPrediction() {
    if (!file) return;
    setStage("running");
    setError(null);
    try {
      const r = await predictBatch(file);
      setResult(r);
      setStage("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Prediction failed");
      setStage("error");
    }
  }

  function signOut() {
    clearSession();
    router.push("/login");
  }

  if (!user) return null;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <Mark size={20} />
          <div className="brand-name">RESINET</div>
          <div className="brand-tag">v0.1</div>
        </div>
        <div className="nav-section-label">Workspace</div>
        <div className={cls("nav-item", "active")}>
          <Icon name="upload" size={15} />
          <span>New scan</span>
        </div>
        <div className="sidebar-footer">
          <div className="user-card" onClick={signOut} title="Sign out">
            <div className="avatar">
              {user.full_name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
            </div>
            <div className="user-info">
              <div className="user-name">{user.full_name}</div>
              <div className="user-role">{user.role}</div>
            </div>
            <Icon name="x" size={14} />
          </div>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="crumbs">
            <span>Workspace</span>
            <span className="sep">/</span>
            <span className="cur">New scan</span>
          </div>
          <div className="topbar-spacer" />
          <Badge tone="ok" dot>backend live</Badge>
        </div>

        <div className="content">
          <div className="page-head">
            <div>
              <h1 className="page-title">New scan</h1>
              <div className="page-desc">Upload a CSV of 5G/6G network flows. Routed through the gateway → inference-svc → MoE model.</div>
            </div>
          </div>

          <div className="grid dash-grid">
            <div className="span-8">
              <Panel title="Upload" padding={false}>
                <div style={{ padding: 16 }}>
                  {(stage === "idle" || stage === "ready") && (
                    <div
                      className={cls("dropzone", dragging && "active")}
                      onClick={pick}
                      onDragOver={(e: DragEvent) => { e.preventDefault(); setDragging(true); }}
                      onDragLeave={() => setDragging(false)}
                      onDrop={(e: DragEvent) => {
                        e.preventDefault();
                        setDragging(false);
                        handleFile(e.dataTransfer.files?.[0]);
                      }}
                    >
                      <input
                        ref={inputRef}
                        type="file"
                        accept=".csv"
                        style={{ display: "none" }}
                        onChange={(e) => handleFile(e.target.files?.[0])}
                      />
                      <div className="dropzone-icon"><Icon name="upload" size={20} /></div>
                      <div style={{ fontSize: 14, fontWeight: 500 }}>Drop CSV file here</div>
                      <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                        or click to browse · accepts <span className="mono">.csv</span> up to 50 MB
                      </div>
                    </div>
                  )}

                  {file && (
                    <div className="panel" style={{ marginTop: 14, border: "1px solid var(--line)" }}>
                      <div className="row" style={{ padding: 12, gap: 12 }}>
                        <div style={{ width: 36, height: 36, borderRadius: 6, background: "var(--bg-subtle)", display: "grid", placeItems: "center", color: "var(--fg-muted)", flexShrink: 0 }}>
                          <Icon name="file" size={18} />
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div className="mono" style={{ fontSize: 12, fontWeight: 500 }}>{file.name}</div>
                          <div className="muted" style={{ fontSize: 11 }}>
                            {(file.size / 1024 / 1024).toFixed(2)} MB
                            {stage === "running" && <> · <span style={{ color: "var(--accent)" }}>scoring…</span></>}
                            {stage === "done" && result && <> · <span style={{ color: "var(--ok)" }}>{result.n_rows} rows scored</span></>}
                            {stage === "error" && <> · <span style={{ color: "var(--critical)" }}>{error}</span></>}
                          </div>
                        </div>
                        <button className="icon-btn" onClick={reset}><Icon name="x" /></button>
                      </div>
                    </div>
                  )}

                  {stage === "error" && (
                    <div className="alert alert-crit" style={{ marginTop: 10 }}>
                      <Icon name="warn" size={16} />
                      <div>
                        <div className="alert-title">Prediction failed</div>
                        <div className="alert-body">{error}</div>
                      </div>
                    </div>
                  )}

                  <div className="row" style={{ marginTop: 14, justifyContent: "flex-end", gap: 8 }}>
                    {stage === "ready" && (
                      <>
                        <Button variant="ghost" onClick={reset}>Cancel</Button>
                        <Button variant="primary" icon="play" onClick={runPrediction}>Start prediction</Button>
                      </>
                    )}
                    {stage === "running" && <Button variant="primary" disabled>Scoring…</Button>}
                    {(stage === "done" || stage === "error") && (
                      <Button variant="default" onClick={reset}>New scan</Button>
                    )}
                  </div>
                </div>
              </Panel>
            </div>

            <div className="span-4">
              <Panel title="Detection model" subtitle="active endpoint">
                <div className="mono" style={{ fontSize: 12, lineHeight: 1.9 }}>
                  <div className="row"><span className="muted">model</span><span style={{ marginLeft: "auto" }}>{result?.model_version ?? "moe-ids unified"}</span></div>
                  <div className="row"><span className="muted">algorithm</span><span style={{ marginLeft: "auto" }}>MoE · 5 experts</span></div>
                  <div className="row"><span className="muted">schema</span><span style={{ marginLeft: "auto" }}>{result?.schema ?? "auto-detect"}</span></div>
                  <div className="row"><span className="muted">endpoint</span><Badge tone="ok" dot>healthy</Badge></div>
                </div>
              </Panel>
            </div>
          </div>

          {result && (
            <>
              <div className="grid dash-grid" style={{ marginTop: 12 }}>
                <div className="span-3"><Kpi label="Rows scored" value={fmtN(result.n_rows)} /></div>
                <div className="span-3"><Kpi label="Attacks detected" value={fmtN(result.summary.n_attack_predicted)} sub={fmtPct(result.summary.attack_rate) + " of traffic"} /></div>
                <div className="span-3"><Kpi label="Mean probability" value={result.summary.mean_probability.toFixed(3)} /></div>
                <div className="span-3"><Kpi label="Schema" value={result.schema} accent /></div>
              </div>

              <div style={{ marginTop: 12 }}>
                <Panel title="Predictions" subtitle={`${result.n_rows} rows · request ${result.request_id.slice(0, 8)}`}>
                  <div className="tbl-wrap" style={{ maxHeight: 480, overflow: "auto" }}>
                    <table className="tbl">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Verdict</th>
                          <th className="num">Probability</th>
                          <th>Dominant expert</th>
                          {result.expert_order.map((e) => <th key={e} className="num">{e}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {result.predictions.map((pred, i) => {
                          const weights = result.gate_weights[i] ?? [];
                          const dom = weights.indexOf(Math.max(...weights));
                          return (
                            <tr key={i}>
                              <td className="mono muted">{String(i).padStart(4, "0")}</td>
                              <td>
                                <Badge tone={pred === 1 ? "critical" : "benign"} dot>
                                  {pred === 1 ? "attack" : "benign"}
                                </Badge>
                              </td>
                              <td className="num">{result.probabilities[i].toFixed(4)}</td>
                              <td><span className="mono muted">{result.expert_order[dom]}</span></td>
                              {weights.map((w, k) => (
                                <td key={k} className="num" style={{ color: k === dom ? "var(--accent)" : undefined }}>
                                  {w.toFixed(3)}
                                </td>
                              ))}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Panel>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}