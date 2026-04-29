"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Icon, Kpi, Panel, fmtN, fmtPct } from "@/components/ui";
import { AppShell } from "@/components/AppShell";
import {
  clearHistory,
  listHistory,
  type HistoryEntry,
  type User,
} from "@/lib/api";

function timeAgo(ms: number): string {
  const s = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function fmtDate(ms: number): string {
  const d = new Date(ms);
  return d.toLocaleString();
}

type SchemaFilter = "all" | string;

function HistoryPage(_: { user: User }) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [filter, setFilter] = useState<SchemaFilter>("all");
  const [search, setSearch] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);

  function refresh() { setEntries(listHistory()); }

  useEffect(() => { refresh(); }, []);

  const schemas = useMemo(
    () => Array.from(new Set(entries.map((e) => e.schema))).sort(),
    [entries],
  );

  const visible = useMemo(() => {
    return entries.filter((e) => {
      if (filter !== "all" && e.schema !== filter) return false;
      if (search) {
        const s = search.toLowerCase();
        if (
          !e.filename.toLowerCase().includes(s)
          && !e.user_email.toLowerCase().includes(s)
          && !e.request_id.toLowerCase().includes(s)
        ) return false;
      }
      return true;
    });
  }, [entries, filter, search]);

  const totals = useMemo(() => ({
    runs: visible.length,
    rows: visible.reduce((a, e) => a + e.n_rows, 0),
    attacks: visible.reduce((a, e) => a + Math.round(e.n_rows * e.attack_rate), 0),
    avgRate: visible.length
      ? visible.reduce((a, e) => a + e.attack_rate, 0) / visible.length
      : 0,
  }), [visible]);

  function handleClear() {
    if (!confirmClear) { setConfirmClear(true); return; }
    clearHistory();
    refresh();
    setConfirmClear(false);
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">History</h1>
          <div className="page-desc">
            Past prediction runs persisted in your browser (localStorage). Click any row to re-open the full result.
            Phase B will move this to a Postgres-backed history.
          </div>
        </div>
      </div>

      {/* KPI summary of the filtered subset */}
      <div className="grid dash-grid">
        <div className="span-3"><Kpi label="Runs" value={fmtN(totals.runs)} sub={filter !== "all" ? `filtered: ${filter}` : "all schemas"} accent /></div>
        <div className="span-3"><Kpi label="Rows scored" value={fmtN(totals.rows)} /></div>
        <div className="span-3"><Kpi label="Attacks detected" value={fmtN(totals.attacks)} sub={totals.rows ? fmtPct(totals.attacks / totals.rows) + " of traffic" : "—"} /></div>
        <div className="span-3"><Kpi label="Avg attack rate" value={visible.length ? fmtPct(totals.avgRate) : "—"} /></div>
      </div>

      {/* Filters + table */}
      <div style={{ marginTop: 12 }}>
        <Panel
          title="Past scans"
          subtitle={`${visible.length} of ${entries.length} entries`}
          actions={
            <div className="row" style={{ gap: 8 }}>
              <Button variant="ghost" onClick={refresh}>Refresh</Button>
              <Button
                variant={confirmClear ? "danger" : "default"}
                onClick={handleClear}
                disabled={entries.length === 0}
              >
                {confirmClear ? "Confirm clear all?" : "Clear history"}
              </Button>
            </div>
          }
        >
          <div className="row" style={{ gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
            <input
              type="text"
              placeholder="Search filename, email, request id…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="form-input"
              style={{ flex: 1, minWidth: 260 }}
            />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="form-select"
              style={{ width: 160 }}
            >
              <option value="all">All schemas</option>
              {schemas.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          {entries.length === 0 ? (
            <div className="muted" style={{ fontSize: 13, padding: "20px 0" }}>
              No history yet. Run a scan from <Link href="/upload" style={{ color: "var(--accent)" }}>New scan</Link> to populate it.
            </div>
          ) : visible.length === 0 ? (
            <div className="muted" style={{ fontSize: 13, padding: "20px 0" }}>
              No entries match the current filters.
            </div>
          ) : (
            <div className="tbl-wrap" style={{ maxHeight: 540, overflow: "auto" }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>File</th>
                    <th>Schema</th>
                    <th className="num">Rows</th>
                    <th className="num">Attacks</th>
                    <th className="num">Attack rate</th>
                    <th>Model</th>
                    <th>By</th>
                    <th>Request ID</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((e) => (
                    <tr key={e.request_id}>
                      <td className="muted" title={fmtDate(e.ts)}>{timeAgo(e.ts)}</td>
                      <td className="mono" style={{ fontSize: 12 }}>{e.filename}</td>
                      <td><Badge tone="default">{e.schema}</Badge></td>
                      <td className="num">{fmtN(e.n_rows)}</td>
                      <td className="num">{fmtN(Math.round(e.n_rows * e.attack_rate))}</td>
                      <td className="num">
                        <Badge tone={e.attack_rate > 0.3 ? "critical" : e.attack_rate > 0.1 ? "warn" : "benign"}>
                          {fmtPct(e.attack_rate)}
                        </Badge>
                      </td>
                      <td className="mono muted" style={{ fontSize: 11 }}>{e.model_version}</td>
                      <td className="muted" style={{ fontSize: 12 }}>{e.user_email}</td>
                      <td className="mono muted" style={{ fontSize: 11 }}>{e.request_id.slice(0, 8)}</td>
                      <td>
                        <Link href={`/results/${e.request_id}`} style={{ color: "var(--accent)", fontSize: 12 }}>
                          Open →
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
    </>
  );
}

export default function HistoryRoute() {
  return (
    <AppShell crumbs={["Workspace", "History"]}>
      {(user) => <HistoryPage user={user} />}
    </AppShell>
  );
}
