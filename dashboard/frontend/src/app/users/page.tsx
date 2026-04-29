"use client";

import { Badge, Icon, Kpi, Panel } from "@/components/ui";
import { AppShell } from "@/components/AppShell";
import { ROLE_LABELS } from "@/lib/nav";
import type { Role, User } from "@/lib/api";

// Placeholder seed — the auth-svc doesn't yet expose GET /admin/users.
// Replace this with `await listUsers()` once the endpoint lands.
const SEED_USERS: { email: string; full_name: string; role: Role; is_active: boolean }[] = [
  { email: "admin@esprit.tn",      full_name: "Platform Administrator", role: "admin",            is_active: true },
];

function UsersPage(_: { user: User }) {
  const counts = SEED_USERS.reduce(
    (acc, u) => ({
      total: acc.total + 1,
      active: acc.active + (u.is_active ? 1 : 0),
      admins: acc.admins + (u.role === "admin" ? 1 : 0),
    }),
    { total: 0, active: 0, admins: 0 },
  );

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Users</h1>
          <div className="page-desc">
            User management for the IDS platform. Account creation and role changes are gated to admins.
          </div>
        </div>
      </div>

      <div className="grid dash-grid">
        <div className="span-3"><Kpi label="Total users" value={counts.total} accent /></div>
        <div className="span-3"><Kpi label="Active" value={counts.active} sub={`${counts.total - counts.active} disabled`} /></div>
        <div className="span-3"><Kpi label="Admins" value={counts.admins} /></div>
        <div className="span-3"><Kpi label="Sign-ups today" value="—" sub="endpoint pending" /></div>
      </div>

      <div style={{ marginTop: 12 }}>
        <div className="alert" style={{ background: "var(--bg-subtle)" }}>
          <Icon name="warn" size={14} />
          <div>
            <div className="alert-title">Read-only preview</div>
            <div className="alert-body" style={{ fontSize: 12 }}>
              The auth-svc does not yet expose <span className="mono">GET /admin/users</span> /
              <span className="mono"> POST /admin/users</span>. Wire those endpoints in
              <span className="mono"> dashboard/auth/app/routes/</span> and replace the seed list below
              with <span className="mono">await listUsers()</span>.
            </div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <Panel title="Accounts" subtitle={`${SEED_USERS.length} seeded`}>
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {SEED_USERS.map((u) => (
                  <tr key={u.email}>
                    <td className="mono" style={{ fontSize: 12 }}>{u.email}</td>
                    <td>{u.full_name}</td>
                    <td>
                      <Badge tone={u.role === "admin" ? "critical" : u.role === "data_scientist" ? "accent" : "default"}>
                        {ROLE_LABELS[u.role]}
                      </Badge>
                    </td>
                    <td>
                      {u.is_active
                        ? <Badge tone="ok" dot>active</Badge>
                        : <Badge tone="default" dot>disabled</Badge>}
                    </td>
                    <td className="muted" style={{ fontSize: 12 }}>—</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <div style={{ marginTop: 12 }}>
        <Panel title="Roles in the platform">
          <div className="grid dash-grid">
            <div className="span-4">
              <Badge tone="default">{ROLE_LABELS.security_analyst}</Badge>
              <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                Front-line: dashboard, history, run new scans. No model or admin access.
              </div>
            </div>
            <div className="span-4">
              <Badge tone="accent">{ROLE_LABELS.data_scientist}</Badge>
              <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                Read history, drift &amp; fairness, trigger training runs. No user management.
              </div>
            </div>
            <div className="span-4">
              <Badge tone="critical">{ROLE_LABELS.admin}</Badge>
              <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                Full access. Manages users, thresholds, hot-reloads the model.
              </div>
            </div>
          </div>
        </Panel>
      </div>
    </>
  );
}

export default function UsersRoute() {
  return (
    <AppShell crumbs={["Administration", "Users"]} roles={["admin"]}>
      {(user) => <UsersPage user={user} />}
    </AppShell>
  );
}
