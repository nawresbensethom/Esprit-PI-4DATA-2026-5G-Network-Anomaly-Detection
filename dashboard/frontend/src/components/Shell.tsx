"use client";

import { type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Badge, Icon, Mark, cls } from "@/components/ui";
import { clearSession, type User } from "@/lib/api";
import { NAV_BY_ROLE, ROLE_LABELS } from "@/lib/nav";

/**
 * Sidebar — role-filtered nav, brand mark, user card with sign-out.
 */
function Sidebar({ user }: { user: User }) {
  const pathname = usePathname();
  const router = useRouter();
  const items = NAV_BY_ROLE[user.role] ?? NAV_BY_ROLE.security_analyst;

  function signOut() {
    clearSession();
    router.push("/login");
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <Mark size={20} />
        <div className="brand-name">RESINET</div>
        <div className="brand-tag">v0.1</div>
      </div>

      {items.map((it, i) => {
        if ("section" in it) {
          return <div key={`s-${i}`} className="nav-section-label">{it.section}</div>;
        }
        const active = pathname === it.href || pathname.startsWith(it.href + "/");
        return (
          <Link key={it.key} href={it.href} className={cls("nav-item", active && "active")}>
            <Icon name={it.icon} size={15} />
            <span>{it.label}</span>
            {it.count != null && <span className="nav-count">{it.count}</span>}
            {it.badge && (
              <span style={{ marginLeft: "auto" }}>
                <Badge tone={it.badge === "warn" ? "warn" : "default"} dot>!</Badge>
              </span>
            )}
          </Link>
        );
      })}

      <div className="sidebar-footer">
        <div className="user-card" onClick={signOut} title="Sign out">
          <div className="avatar">
            {user.full_name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
          </div>
          <div className="user-info">
            <div className="user-name">{user.full_name}</div>
            <div className="user-role">{ROLE_LABELS[user.role]}</div>
          </div>
          <Icon name="chev" size={14} />
        </div>
      </div>
    </aside>
  );
}

/**
 * Topbar — breadcrumbs + status badge + per-page actions slot.
 */
function Topbar({
  crumbs,
  status,
  actions,
}: {
  crumbs: string[];
  status?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="topbar">
      <div className="crumbs">
        {crumbs.map((c, i) => (
          <span key={i}>
            {i > 0 && <span className="sep">/</span>}
            <span className={i === crumbs.length - 1 ? "cur" : ""}>{c}</span>
          </span>
        ))}
      </div>
      <div className="topbar-spacer" />
      {status ?? <Badge tone="ok" dot>backend live</Badge>}
      {actions}
    </div>
  );
}

/**
 * Authenticated app frame — sidebar + topbar + main content area.
 */
export function Shell({
  user,
  crumbs,
  topbarStatus,
  topbarActions,
  children,
}: {
  user: User;
  crumbs: string[];
  topbarStatus?: ReactNode;
  topbarActions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="app">
      <Sidebar user={user} />
      <main className="main">
        <Topbar crumbs={crumbs} status={topbarStatus} actions={topbarActions} />
        <div className="content">{children}</div>
      </main>
    </div>
  );
}
