/**
 * Single source of truth for the role -> nav-items map.
 * Backend role-gating still happens at the gateway (require_roles); this is
 * UX layer only — gateway returns 403 for protected calls regardless.
 */
import type { Role } from "@/lib/api";

export type NavSection = { section: string };
export type NavLink = {
  key: string;
  label: string;
  icon: string;
  href: string;
  count?: number;
  badge?: "warn" | "info";
};
export type NavEntry = NavSection | NavLink;

export const ROLE_LABELS: Record<Role, string> = {
  security_analyst: "Security Analyst",
  admin: "Administrator",
  data_scientist: "Data Scientist",
};

const WORKSPACE_COMMON: NavEntry[] = [
  { section: "Workspace" },
  { key: "dashboard", label: "Dashboard", icon: "dash", href: "/dashboard" },
  { key: "history", label: "History", icon: "history", href: "/history" },
];

export const NAV_BY_ROLE: Record<Role, NavEntry[]> = {
  security_analyst: [
    ...WORKSPACE_COMMON,
    { key: "upload", label: "New scan", icon: "upload", href: "/upload" },
  ],
  admin: [
    ...WORKSPACE_COMMON,
    { key: "upload", label: "New scan", icon: "upload", href: "/upload" },
    { section: "Administration" },
    { key: "users", label: "Users", icon: "users", href: "/users" },
    { key: "settings", label: "Thresholds & config", icon: "settings", href: "/settings" },
    { key: "drift", label: "Drift & fairness", icon: "drift", href: "/drift", badge: "warn" },
    { key: "model", label: "Model registry", icon: "model", href: "/model" },
  ],
  data_scientist: [
    ...WORKSPACE_COMMON,
    { section: "Models" },
    { key: "drift", label: "Drift & fairness", icon: "drift", href: "/drift", badge: "warn" },
    { key: "model", label: "Model registry", icon: "model", href: "/model" },
  ],
};

/**
 * Pages a given role is allowed to view. Used by RoleGate to redirect away
 * from forbidden routes. Order matches NAV_BY_ROLE plus the implicit /results/*.
 */
export const ALLOWED_ROUTES: Record<Role, string[]> = {
  security_analyst: ["/dashboard", "/history", "/results", "/upload"],
  admin: [
    "/dashboard", "/history", "/results", "/upload",
    "/users", "/settings", "/drift", "/model",
  ],
  data_scientist: ["/dashboard", "/history", "/results", "/drift", "/model"],
};

export function canAccess(role: Role, pathname: string): boolean {
  return ALLOWED_ROUTES[role].some((p) => pathname === p || pathname.startsWith(p + "/"));
}
