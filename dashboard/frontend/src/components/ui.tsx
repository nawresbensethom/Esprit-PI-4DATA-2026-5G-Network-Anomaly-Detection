"use client";

import type { ReactNode, MouseEventHandler } from "react";

export function cls(...xs: (string | false | null | undefined)[]): string {
  return xs.filter(Boolean).join(" ");
}

export function fmtN(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return Math.round(n).toLocaleString();
}

export function fmtPct(n: number, d = 1): string {
  return (n * 100).toFixed(d) + "%";
}

export function Mark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none">
      <rect x="1" y="1" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="1.4" opacity=".35" />
      <rect x="5" y="5" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.4" opacity=".7" />
      <rect x="8.5" y="8.5" width="3" height="3" fill="currentColor" />
    </svg>
  );
}

const ICONS: Record<string, ReactNode> = {
  arrow: <path d="M4 10h12m0 0l-4-4m4 4l-4 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none" />,
  check: <path d="M4 10l3.5 3.5L16 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />,
  x: <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />,
  upload: <path d="M10 13V3m0 0l-4 4m4-4l4 4M4 15h12v2H4z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
  warn: <path d="M10 2L18 17H2L10 2zM10 8v4M10 14v.5" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none" />,
  file: <path d="M5 2h7l3 3v13H5zM12 2v3h3" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none" />,
  download: <path d="M10 3v10m0 0l-4-4m4 4l4-4M4 17h12" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
  play: <path d="M6 4l10 6-10 6V4z" fill="currentColor" />,
  dash: <path d="M3 4h6v6H3zM11 4h6v3h-6zM11 9h6v7h-6zM3 12h6v4H3z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />,
  history: <path d="M3 5a7 7 0 1 1-1.5 4.4M3 5v3h3M10 6v4l3 2" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
  results: <path d="M3 16V8m4 8V4m4 12v-6m4 6V11" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />,
  users: <path d="M7 9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zm6 0a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM2 17v-1a4 4 0 0 1 4-4h2a4 4 0 0 1 4 4v1M12 17v-1a4 4 0 0 0-2-3.5M14 12h0a4 4 0 0 1 4 4v1" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
  settings: <path d="M10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM16 10a6 6 0 0 0-.1-1l1.5-1.2-1.5-2.6-1.8.6a6 6 0 0 0-1.7-1L12 3H8l-.4 1.8a6 6 0 0 0-1.7 1l-1.8-.6L2.6 7.8 4.1 9a6 6 0 0 0 0 2L2.6 12.2l1.5 2.6 1.8-.6a6 6 0 0 0 1.7 1L8 17h4l.4-1.8a6 6 0 0 0 1.7-1l1.8.6 1.5-2.6L15.9 11" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />,
  drift: <path d="M2 14c2-3 4-3 6 0s4 3 6 0 4-3 4 0M2 8c2-3 4-3 6 0s4 3 6 0 4-3 4 0" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
  model: <path d="M10 3l7 4-7 4-7-4 7-4zM3 11l7 4 7-4M3 15l7 4 7-4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
  chev: <path d="M6 8l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
  bell: <path d="M5 14V9a5 5 0 0 1 10 0v5l1 2H4l1-2zM8 17a2 2 0 0 0 4 0" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />,
  search: <path d="M9 16a7 7 0 1 1 0-14 7 7 0 0 1 0 14zm5-2l4 4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />,
};

export function Icon({ name, size = 16, className = "" }: { name: string; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" className={className}>
      {ICONS[name] ?? null}
    </svg>
  );
}

type Tone = "default" | "ok" | "warn" | "critical" | "accent" | "benign";
export function Badge({ tone = "default", children, dot = false }: { tone?: Tone; children: ReactNode; dot?: boolean }) {
  return (
    <span className={cls("badge", `badge-${tone}`)}>
      {dot && <span className="badge-dot" />}
      {children}
    </span>
  );
}

type Variant = "default" | "primary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";
export function Button({
  variant = "default",
  size = "md",
  children,
  onClick,
  icon,
  disabled,
  type = "button",
  className = "",
}: {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  icon?: string;
  disabled?: boolean;
  type?: "button" | "submit" | "reset";
  className?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cls("btn", `btn-${variant}`, `btn-${size}`, className)}
    >
      {icon && <Icon name={icon} size={14} />}
      {children}
    </button>
  );
}

export function Panel({
  title,
  subtitle,
  actions,
  children,
  className = "",
  padding = true,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  padding?: boolean;
}) {
  return (
    <div className={cls("panel", className)}>
      {(title || actions) && (
        <div className="panel-head">
          <div>
            {title && <div className="panel-title">{title}</div>}
            {subtitle && <div className="panel-sub">{subtitle}</div>}
          </div>
          {actions && <div className="panel-actions">{actions}</div>}
        </div>
      )}
      <div className={cls(padding && "panel-body")}>{children}</div>
    </div>
  );
}

export function Kpi({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div className={cls("kpi", accent && "kpi-accent")}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub"><span className="kpi-note">{sub}</span></div>}
    </div>
  );
}