"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Badge, Button, Icon, Kpi, Panel, fmtN, fmtPct } from "@/components/ui";
import { AppShell } from "@/components/AppShell";
import {
  getHistoryEntry,
  type HistoryEntry,
  type User,
} from "@/lib/api";

function fmtDate(ms: number): string {
  return new Date(ms).toLocaleString();
}

function ResultPage(_: { user: User }) {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id ?? "";
  const [entry, setEntry] = useState<HistoryEntry | null | undefined>(undefined);

  useEffect(() => {
    if (!id) return;
    setEntry(getHistoryEntry(id));
  }, [id]);

  if (entry === undefined) {
    return <div className="muted" style={{ fontSize: 13, padding: "40px 0" }}>Loading…</div>;
  }

  if (entry === null) {
    return (
      <>
        <div className="page-head">
          <div>
            <h1 className="page-title">Result not found</h1>
            <div className="page-desc">Request id <span className="mono">{id}</span> isn't in this browser's local history.</div>
          </div>
        </div>
        <Panel title="Where did the data go?">
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div className="muted" style={{ fontSize: 12 }}>
              History is currently stored client-side in <span className="mono">localStorage</span>.
              Possible reasons this entry isn't here:
              <ul style={{ marginTop: 8, paddingLeft: 18 }}>
                <li>You're on a different browser or device than where the scan was run.</li>
                <li>localStorage was cleared (history rotated past the 50-entry cap, manual clear, or browser privacy mode).</li>
                <li>The link came from someone else's session.</li>
              </ul>
            </div>
            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
              <Button variant="ghost" onClick={() => router.push("/history")}>Back to History</Button>
              <Link href="/upload" className="btn btn-primary btn-md">New scan</Link>
            </div>
          </div>
        </Panel>
      </>
    );
  }

  const r = entry.prediction;

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Scan result</h1>
          <div className="page-desc">
            <span className="mono">{entry.filename}</span>
            <span className="muted"> · {fmtDate(entry.ts)} · by {entry.user_email}</span>
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          <Button variant="ghost" onClick={() => router.push("/history")}>← History</Button>
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="grid dash-grid">
        <div className="span-3"><Kpi label="Rows scored" value={fmtN(r.n_rows)} accent /></div>
        <div className="span-3">
          <Kpi
            label="Attacks detected"
            value={fmtN(r.summary.n_attack_predicted)}
            sub={fmtPct(r.summary.attack_rate) + " of traffic"}
          />
        </div>
        <div className="span-3"><Kpi label="Mean probability" value={r.summary.mean_probability.toFixed(3)} /></div>
        <div className="span-3"><Kpi label="Schema" value={r.schema} /></div>
      </div>

      {/* Meta panel */}
      <div style={{ marginTop: 12 }}>
        <Panel title="Run metadata" subtitle={`request ${r.request_id}`}>
          <div className="grid dash-grid">
            <div className="span-4">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="muted" style={{ fontSize: 13 }}>Model version</span>
                <span className="mono" style={{ fontSize: 13 }}>{r.model_version}</span>
              </div>
            </div>
            <div className="span-4">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="muted" style={{ fontSize: 13 }}>Schema</span>
                <Badge tone="default">{r.schema}</Badge>
              </div>
            </div>
            <div className="span-4">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <span className="muted" style={{ fontSize: 13 }}>Verdict mix</span>
                <span className="mono" style={{ fontSize: 13 }}>
                  {r.summary.n_attack_predicted}A / {r.summary.n_benign_predicted}B
                </span>
              </div>
            </div>
          </div>
        </Panel>
      </div>

      {/* Predictions table */}
      <div style={{ marginTop: 12 }}>
        <Panel title="Predictions" subtitle={`${r.n_rows} rows · ${r.expert_order.length} experts`}>
          <div className="tbl-wrap" style={{ maxHeight: 600, overflow: "auto" }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Verdict</th>
                  <th className="num">Probability</th>
                  <th>Dominant expert</th>
                  {r.expert_order.map((e) => <th key={e} className="num">{e}</th>)}
                </tr>
              </thead>
              <tbody>
                {r.predictions.map((pred, i) => {
                  const weights = r.gate_weights[i] ?? [];
                  const dom = weights.indexOf(Math.max(...weights));
                  return (
                    <tr key={i}>
                      <td className="mono muted">{String(i).padStart(4, "0")}</td>
                      <td>
                        <Badge tone={pred === 1 ? "critical" : "benign"} dot>
                          {pred === 1 ? "attack" : "benign"}
                        </Badge>
                      </td>
                      <td className="num">{r.probabilities[i].toFixed(4)}</td>
                      <td><span className="mono muted">{r.expert_order[dom]}</span></td>
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

      {/* Raw JSON for debugging / export */}
      <div style={{ marginTop: 12 }}>
        <Panel title="Raw JSON">
          <details>
            <summary className="muted" style={{ fontSize: 12, cursor: "pointer" }}>Expand prediction payload</summary>
            <pre className="mono" style={{ fontSize: 11, marginTop: 8, padding: 12, background: "var(--bg-subtle)", borderRadius: 6, overflow: "auto", maxHeight: 320 }}>
              {JSON.stringify(r, null, 2)}
            </pre>
          </details>
        </Panel>
      </div>
    </>
  );
}

export default function ResultRoute() {
  return (
    <AppShell crumbs={["Workspace", "History", "Result"]}>
      {(user) => <ResultPage user={user} />}
    </AppShell>
  );
}
