// Shared primitives
const { useState, useEffect, useRef, useMemo, useCallback } = React;

function cls(...xs) { return xs.filter(Boolean).join(' '); }

function fmtN(n) {
  if (n == null) return '—';
  if (Math.abs(n) >= 1e6) return (n/1e6).toFixed(2)+'M';
  if (Math.abs(n) >= 1e3) return (n/1e3).toFixed(1)+'k';
  return Math.round(n).toLocaleString();
}
function fmtPct(n, d=1) { return (n*100).toFixed(d)+'%'; }
function fmtTime(ts) {
  const d = new Date(ts);
  const now = Date.now();
  const diff = (now - ts)/1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}
function fmtDate(ts) {
  return new Date(ts).toLocaleString('en-US', { month:'short', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false });
}
function fmtDur(s) {
  if (s < 60) return `${s}s`;
  return `${Math.floor(s/60)}m ${s%60}s`;
}

// Logo mark
function Mark({ size=20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none">
      <rect x="1" y="1" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="1.4" opacity=".35"/>
      <rect x="5" y="5" width="10" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.4" opacity=".7"/>
      <rect x="8.5" y="8.5" width="3" height="3" fill="currentColor"/>
    </svg>
  );
}

// Tiny icon set
const Icons = {
  dash: <path d="M3 3h7v7H3zM12 3h6v4h-6zM12 9h6v9h-6zM3 12h7v6H3z" fill="none" stroke="currentColor" strokeWidth="1.4"/>,
  upload: <path d="M10 13V3m0 0l-4 4m4-4l4 4M4 15h12v2H4z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>,
  history: <path d="M10 4a6 6 0 106 6M10 4V2m0 2H8m2 3v3l2 1" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>,
  results: <path d="M3 4h14M3 8h14M3 12h10M3 16h7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>,
  drift: <path d="M3 14l4-4 3 3 7-7M13 6h4v4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>,
  users: <path d="M7 9a3 3 0 100-6 3 3 0 000 6zM2 17c0-3 2-5 5-5s5 2 5 5M14 10a2.5 2.5 0 100-5M18 17c0-2.5-1.7-4-4-4" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>,
  settings: <path d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z M10 2v2M10 16v2M2 10h2M16 10h2M4.3 4.3l1.5 1.5M14.2 14.2l1.5 1.5M4.3 15.7l1.5-1.5M14.2 5.8l1.5-1.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none"/>,
  model: <path d="M10 2l7 4v8l-7 4-7-4V6zM3 6l7 4 7-4M10 10v8" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none"/>,
  search: <path d="M9 15a6 6 0 100-12 6 6 0 000 12zM14 14l3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none"/>,
  bell: <path d="M5 8a5 5 0 0110 0v3l1.5 2.5h-13L5 11zM8 16a2 2 0 004 0" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none"/>,
  chev: <path d="M5 7l5 5 5-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none"/>,
  check: <path d="M4 10l3.5 3.5L16 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" fill="none"/>,
  x: <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>,
  up: <path d="M6 13l4-4 4 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none"/>,
  down: <path d="M6 7l4 4 4-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none"/>,
  dot: <circle cx="10" cy="10" r="3" fill="currentColor"/>,
  warn: <path d="M10 2L18 17H2L10 2zM10 8v4M10 14v.5" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none"/>,
  info: <path d="M10 17a7 7 0 100-14 7 7 0 000 14zM10 9v5M10 6.5v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none"/>,
  file: <path d="M5 2h7l3 3v13H5zM12 2v3h3" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" fill="none"/>,
  play: <path d="M6 4l10 6-10 6V4z" fill="currentColor"/>,
  pause: <path d="M6 4h3v12H6zM11 4h3v12h-3z" fill="currentColor"/>,
  download: <path d="M10 3v10m0 0l-4-4m4 4l4-4M4 17h12" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>,
  filter: <path d="M3 5h14l-5 7v4l-4 2v-6z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>,
  sort: <path d="M7 4v12m0 0l-3-3m3 3l3-3M13 16V4m0 0l-3 3m3-3l3 3" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>,
  plus: <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>,
  more: <circle cx="5" cy="10" r="1.4" fill="currentColor"/>,
  arrow: <path d="M4 10h12m0 0l-4-4m4 4l-4 4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" fill="none"/>,
  logo: null,
};
function Icon({ name, size=16, className='' }) {
  return <svg width={size} height={size} viewBox="0 0 20 20" className={className}>{Icons[name]}</svg>;
}

// Badge
function Badge({ tone='default', children, dot=false }) {
  return <span className={cls('badge', `badge-${tone}`)}>
    {dot && <span className="badge-dot" />}
    {children}
  </span>;
}

// Button
function Button({ variant='default', size='md', children, onClick, icon, disabled, type='button', className='' }) {
  return <button type={type} onClick={onClick} disabled={disabled}
    className={cls('btn', `btn-${variant}`, `btn-${size}`, className)}>
    {icon && <Icon name={icon} size={14} />}
    {children}
  </button>;
}

// KPI card
function Kpi({ label, value, sub, delta, note, accent }) {
  const up = delta != null && delta > 0;
  return (
    <div className={cls('kpi', accent && 'kpi-accent')}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-sub">
        {delta != null && (
          <span className={cls('kpi-delta', up ? 'up' : 'down')}>
            <Icon name={up ? 'up' : 'down'} size={12} />
            {Math.abs(delta).toFixed(1)}%
          </span>
        )}
        <span className="kpi-note">{sub || note}</span>
      </div>
    </div>
  );
}

// Card/Panel
function Panel({ title, subtitle, actions, children, className='', padding=true }) {
  return (
    <div className={cls('panel', className)}>
      {(title || actions) && (
        <div className="panel-head">
          <div>
            {title && <div className="panel-title">{title}</div>}
            {subtitle && <div className="panel-sub">{subtitle}</div>}
          </div>
          {actions && <div className="panel-actions">{actions}</div>}
        </div>
      )}
      <div className={cls(padding && 'panel-body')}>{children}</div>
    </div>
  );
}

// Spark line
function Sparkline({ data, stroke='var(--accent)', fill=false, height=40 }) {
  if (!data || !data.length) return null;
  const w = 100, h = height;
  const max = Math.max(...data), min = Math.min(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 2) - 1;
    return [x, y];
  });
  const path = 'M ' + pts.map(([x,y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' L ');
  const fillPath = fill ? path + ` L ${w},${h} L 0,${h} Z` : null;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width:'100%', height }}>
      {fill && <path d={fillPath} fill={stroke} opacity=".08"/>}
      <path d={path} stroke={stroke} strokeWidth="1.2" fill="none" vectorEffect="non-scaling-stroke"/>
    </svg>
  );
}

// Minimal line chart
function LineChart({ series, height=180, yLabels=true, annotations=[] }) {
  // series: [{ name, color, data: [{x, y}], style: 'line'|'area' }]
  const w = 600;
  const padL = 28, padR = 6, padT = 8, padB = 20;
  const all = series.flatMap(s => s.data.map(p => p.y));
  const max = Math.max(...all, 0);
  const min = Math.min(...all, 0);
  const xs = series[0].data.map(p => p.x);
  const xMax = xs.length - 1;
  const X = i => padL + (i/xMax) * (w - padL - padR);
  const Y = v => padT + (1 - (v - min)/(max - min || 1)) * (height - padT - padB);
  return (
    <svg viewBox={`0 0 ${w} ${height}`} style={{ width:'100%', height, display:'block' }}>
      {yLabels && [0, .5, 1].map((t, i) => {
        const y = padT + t * (height - padT - padB);
        const v = max - t * (max - min);
        return <g key={i}>
          <line x1={padL} x2={w-padR} y1={y} y2={y} stroke="var(--line)" strokeDasharray="2 3" opacity=".6"/>
          <text x={padL-4} y={y+3} textAnchor="end" className="chart-label">{fmtN(v)}</text>
        </g>;
      })}
      {series.map((s, i) => {
        const path = 'M ' + s.data.map((p, j) => `${X(j)},${Y(p.y)}`).join(' L ');
        const area = path + ` L ${X(xMax)},${Y(0)} L ${X(0)},${Y(0)} Z`;
        return <g key={i}>
          {s.style === 'area' && <path d={area} fill={s.color} opacity=".1"/>}
          <path d={path} stroke={s.color} strokeWidth="1.4" fill="none"/>
        </g>;
      })}
      {series[0].data.map((p, j) => (
        j % Math.ceil(xMax/6) === 0 && <text key={j} x={X(j)} y={height-6} textAnchor="middle" className="chart-label">{p.label || p.x}</text>
      ))}
      {annotations.map((a,i) => (
        <g key={i}>
          <line x1={X(a.x)} x2={X(a.x)} y1={padT} y2={height-padB} stroke="var(--warn-fg)" strokeDasharray="3 2" opacity=".7"/>
          <text x={X(a.x)+3} y={padT+10} className="chart-label" fill="var(--warn-fg)">{a.label}</text>
        </g>
      ))}
    </svg>
  );
}

// Horizontal bar
function HBar({ data, max, color='var(--accent)', height=14, label, value }) {
  const pct = Math.min(100, (data/max)*100);
  return (
    <div className="hbar">
      {label && <div className="hbar-label">{label}</div>}
      <div className="hbar-track">
        <div className="hbar-fill" style={{ width: pct+'%', background: color }}/>
      </div>
      {value && <div className="hbar-val">{value}</div>}
    </div>
  );
}

// Donut
function Donut({ segments, size=140, thickness=16 }) {
  // segments: [{ label, value, color }]
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = (size - thickness)/2;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--line)" strokeWidth={thickness}/>
      {segments.map((s, i) => {
        const len = (s.value/total) * c;
        const dash = `${len} ${c-len}`;
        const el = <circle key={i} cx={size/2} cy={size/2} r={r} fill="none"
          stroke={s.color} strokeWidth={thickness}
          strokeDasharray={dash} strokeDashoffset={-offset}
          transform={`rotate(-90 ${size/2} ${size/2})`}/>;
        offset += len;
        return el;
      })}
    </svg>
  );
}

Object.assign(window, { cls, fmtN, fmtPct, fmtTime, fmtDate, fmtDur, Mark, Icon, Badge, Button, Kpi, Panel, Sparkline, LineChart, HBar, Donut });
