// Results detail page + Admin + Drift pages
function ResultsPage({ data, onNavigate }) {
  const [selected, setSelected] = useState(null);
  const [classFilter, setClassFilter] = useState('all');
  const [minConf, setMinConf] = useState(0.5);
  const job = data.jobs[0];

  const filtered = data.predictions.filter(p => {
    if (classFilter !== 'all' && p.cls !== classFilter) return false;
    if (p.conf < minConf) return false;
    return true;
  });

  const attackCount = data.predictions.filter(p => p.cls !== 'benign').length;
  const total = data.predictions.length;

  return <>
    <div className="page-head">
      <div>
        <div className="row" style={{ gap: 8, marginBottom: 4 }}>
          <span className="hlink mono" style={{ fontSize: 11 }} onClick={() => onNavigate('history')}>← history</span>
          <Badge tone="ok" dot>completed</Badge>
          <span className="mono muted" style={{ fontSize: 11 }}>{job.id}</span>
        </div>
        <h1 className="page-title">{job.filename}</h1>
        <div className="page-desc">
          {fmtN(job.rows)} rows · finished {fmtTime(job.created)} · duration {fmtDur(job.duration)} · model <span className="mono">{job.model}</span>
        </div>
      </div>
      <div className="page-actions">
        <Button variant="default" size="md" icon="download">Export CSV</Button>
        <Button variant="default" size="md" icon="download">Export PDF</Button>
      </div>
    </div>

    <div className="grid dash-grid" style={{ marginBottom: 12 }}>
      <div className="span-3"><Kpi label="Rows" value={fmtN(job.rows)} sub="processed"/></div>
      <div className="span-3"><Kpi label="Attacks detected" value={fmtN(job.attacks)} sub={`${fmtPct(job.attackRate)} of traffic`}/></div>
      <div className="span-3"><Kpi label="Avg confidence" value="0.914" sub="across all predictions"/></div>
      <div className="span-3"><Kpi label="Inference time" value="48ms" sub="p95 per 500-row batch"/></div>
    </div>

    <div className="grid dash-grid">
      <div className="span-8">
        <Panel padding={false}>
          <div className="stat-strip">
            <div className="row" style={{ gap: 10 }}>
              <span className="subtle" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>class</span>
              <div className="tweak-chips">
                {['all','benign','ddos_volumetric','ddos_syn','port_scan','c2_beacon'].map(c => (
                  <button key={c} className={cls('tweak-chip', classFilter===c && 'on')} onClick={()=>setClassFilter(c)}>{c.replace(/_/g,' ')}</button>
                ))}
              </div>
            </div>
            <div className="row" style={{ marginLeft: 'auto', gap: 10 }}>
              <span className="subtle" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>min conf</span>
              <input type="range" min="0.5" max="1" step="0.01" value={minConf}
                onChange={e=>setMinConf(parseFloat(e.target.value))}
                className="slider" style={{ width: 100 }}/>
              <span className="mono" style={{ fontSize: 11, width: 34 }}>{minConf.toFixed(2)}</span>
              <span className="subtle" style={{ fontSize: 11 }}>·</span>
              <span className="mono muted" style={{ fontSize: 11 }}>{filtered.length} of {total}</span>
            </div>
          </div>

          <div className="tbl-wrap" style={{ maxHeight: 520, overflow: 'auto' }}>
            <table className="tbl">
              <thead><tr>
                <th>#</th><th>Source → Dest</th><th>Proto</th><th>Slice</th>
                <th className="num">Bytes</th><th className="num">Pkts</th>
                <th>Prediction</th><th className="num">Confidence</th><th></th>
              </tr></thead>
              <tbody>
                {filtered.slice(0, 80).map(p => (
                  <tr key={p.id} className={cls('clickable', selected?.id === p.id && 'selected')} onClick={() => setSelected(p)}>
                    <td className="mono muted">{String(p.row).padStart(4,'0')}</td>
                    <td><span className="mono">{p.src}</span><span className="subtle" style={{ margin:'0 6px' }}>→</span><span className="mono">{p.dst}</span></td>
                    <td><span className="tag">{p.proto}</span></td>
                    <td><span className="mono muted">{p.slice}</span></td>
                    <td className="num">{fmtN(p.bytes)}</td>
                    <td className="num">{p.pkts}</td>
                    <td>
                      <Badge tone={p.clsColor === 'critical' ? 'critical' : p.clsColor === 'warn' ? 'warn' : 'benign'} dot>
                        {p.clsLabel}
                      </Badge>
                    </td>
                    <td className="num">
                      <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                        <div style={{ width: 36, height: 4, background: 'var(--bg-subtle)', borderRadius: 2, overflow: 'hidden' }}>
                          <div style={{ width: `${p.conf*100}%`, height: '100%', background: p.conf > 0.8 ? 'var(--critical)' : 'var(--accent)' }}/>
                        </div>
                        <span>{p.conf.toFixed(4)}</span>
                      </div>
                    </td>
                    <td className="muted"><Icon name="arrow" size={14}/></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <div className="span-4">
        {!selected ? (
          <Panel title="Select a row" subtitle="to view SHAP explanation">
            <div className="empty">
              <Icon name="results" size={24} className="muted" style={{ marginBottom: 8 }}/>
              <div>Click any prediction in the table to inspect feature attribution.</div>
            </div>
          </Panel>
        ) : (
          <SHAPCard p={selected} shap={data.shap}/>
        )}
      </div>
    </div>
  </>;
}

function SHAPCard({ p, shap }) {
  const maxAbs = Math.max(...shap.map(s => s.abs));
  return (
    <Panel title="SHAP · feature attribution" subtitle={`row ${p.row} · ${p.clsLabel}`}
      actions={<Badge tone="accent">{p.conf.toFixed(4)}</Badge>}>
      <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginBottom: 10 }}>
        Why this row was classified as <b>{p.clsLabel}</b>. Red bars increase attack score; green decrease it.
      </div>
      <div className="row" style={{ justifyContent: 'space-between', fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--fg-subtle)', marginBottom: 4 }}>
        <span>benign</span><span>base = 0.203</span><span>malicious</span>
      </div>
      {shap.map((s,i) => {
        const pctAbs = (s.abs/maxAbs)*48;
        return <div key={i} className="shap-row">
          <div className="shap-label">{s.feature}</div>
          <div className="shap-bar">
            {s.value > 0 && <div className="shap-bar-pos" style={{ width: pctAbs+'%' }}/>}
            {s.value < 0 && <div className="shap-bar-neg" style={{ width: pctAbs+'%' }}/>}
          </div>
          <div className="shap-val">{s.value > 0 ? '+' : ''}{s.value.toFixed(3)}</div>
        </div>;
      })}
      <div className="divider"/>
      <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Flow metadata</div>
      <div className="mono" style={{ fontSize: 11, lineHeight: 1.8 }}>
        <div className="row"><span className="muted">src</span><span style={{ marginLeft: 'auto' }}>{p.src}</span></div>
        <div className="row"><span className="muted">dst</span><span style={{ marginLeft: 'auto' }}>{p.dst}</span></div>
        <div className="row"><span className="muted">proto</span><span style={{ marginLeft: 'auto' }}>{p.proto}</span></div>
        <div className="row"><span className="muted">slice</span><span style={{ marginLeft: 'auto' }}>{p.slice}</span></div>
        <div className="row"><span className="muted">bytes</span><span style={{ marginLeft: 'auto' }}>{p.bytes.toLocaleString()}</span></div>
        <div className="row"><span className="muted">packets</span><span style={{ marginLeft: 'auto' }}>{p.pkts}</span></div>
      </div>
      <div className="row" style={{ marginTop: 12, gap: 6, flexWrap: 'wrap' }}>
        <Button variant="danger" size="sm">Isolate host</Button>
        <Button variant="default" size="sm">Watchlist</Button>
        <Button variant="ghost" size="sm">False positive</Button>
      </div>
    </Panel>
  );
}

// ─────────── Admin: users ───────────
function UsersPage({ data }) {
  const [users, setUsers] = useState(data.users);
  const [modalOpen, setModalOpen] = useState(false);

  function toggleActive(id) {
    setUsers(us => us.map(u => u.id === id ? { ...u, active: !u.active } : u));
  }
  function setRole(id, role) {
    setUsers(us => us.map(u => u.id === id ? { ...u, role } : u));
  }

  return <>
    <div className="page-head">
      <div>
        <h1 className="page-title">Users & roles</h1>
        <div className="page-desc">{users.length} members · admins can add, deactivate, and reassign roles</div>
      </div>
      <div className="page-actions">
        <Button variant="primary" size="md" icon="plus" onClick={()=>setModalOpen(true)}>Invite user</Button>
      </div>
    </div>

    <Panel padding={false}>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr>
            <th>Name</th><th>Email</th><th>Role</th><th>Status</th>
            <th>Last active</th><th></th>
          </tr></thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id}>
                <td>
                  <div className="row">
                    <div className="avatar">{u.name.split(' ').map(n=>n[0]).slice(0,2).join('')}</div>
                    <span style={{ fontWeight: 500 }}>{u.name}</span>
                  </div>
                </td>
                <td className="mono muted" style={{ fontSize: 11 }}>{u.email}</td>
                <td>
                  <select className="form-select" style={{ height: 24, fontSize: 11, padding: '0 6px', width: 120 }}
                    value={u.role} onChange={e => setRole(u.id, e.target.value)}>
                    <option value="analyst">Analyst</option>
                    <option value="admin">Administrator</option>
                    <option value="ml_engineer">ML Engineer</option>
                  </select>
                </td>
                <td>
                  <div className="row" style={{ gap: 8 }}>
                    <div className={cls('toggle', u.active && 'on')} onClick={()=>toggleActive(u.id)}>
                      <div className="toggle-thumb"/>
                    </div>
                    <span className="muted" style={{ fontSize: 11 }}>{u.active?'active':'disabled'}</span>
                  </div>
                </td>
                <td className="muted">{fmtTime(u.last)}</td>
                <td><button className="icon-btn"><Icon name="more"/></button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>

    {modalOpen && (
      <div className="modal-backdrop" onClick={()=>setModalOpen(false)}>
        <div className="modal" onClick={e=>e.stopPropagation()}>
          <div className="modal-head">
            <div className="modal-title">Invite user</div>
            <button className="icon-btn" onClick={()=>setModalOpen(false)}><Icon name="x"/></button>
          </div>
          <div className="modal-body">
            <div className="form-field">
              <label className="form-label">Full name</label>
              <input className="form-input" placeholder="Jamie Chen"/>
            </div>
            <div className="form-field">
              <label className="form-label">Email</label>
              <input className="form-input" placeholder="jamie@sentra.io"/>
            </div>
            <div className="form-field">
              <label className="form-label">Role</label>
              <select className="form-select">
                <option value="analyst">Security Analyst</option>
                <option value="ml_engineer">ML Engineer</option>
                <option value="admin">Administrator</option>
              </select>
              <div className="form-hint">Role controls sidebar menu and allowed operations.</div>
            </div>
          </div>
          <div className="modal-foot">
            <Button variant="ghost" onClick={()=>setModalOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={()=>setModalOpen(false)}>Send invite</Button>
          </div>
        </div>
      </div>
    )}
  </>;
}

// ─────────── Admin: settings ───────────
function SettingsPage({ threshold, setThreshold, sliceThresholds, setSliceThresholds }) {
  const [maxRows, setMaxRows] = useState(100000);
  const [saved, setSaved] = useState(false);

  function save() { setSaved(true); setTimeout(()=>setSaved(false), 2000); }

  return <>
    <div className="page-head">
      <div>
        <h1 className="page-title">Thresholds & configuration</h1>
        <div className="page-desc">Changes are logged to audit_log and take effect on next inference batch.</div>
      </div>
      <div className="page-actions">
        {saved && <Badge tone="ok" dot>changes saved</Badge>}
        <Button variant="primary" size="md" onClick={save}>Save changes</Button>
      </div>
    </div>

    <div className="grid dash-grid">
      <div className="span-8">
        <Panel title="Detection thresholds" subtitle="confidence cutoff for marking a flow as malicious">
          <div style={{ marginBottom: 16 }}>
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
              <div>
                <div style={{ fontSize: 12, fontWeight: 500 }}>Global default</div>
                <div className="muted" style={{ fontSize: 11 }}>applied to all slices unless overridden</div>
              </div>
              <div className="mono" style={{ fontSize: 18 }}>{threshold.toFixed(2)}</div>
            </div>
            <input type="range" min="0.3" max="0.95" step="0.01" value={threshold}
              onChange={e=>setThreshold(parseFloat(e.target.value))} className="slider"/>
            <div className="row" style={{ justifyContent: 'space-between', marginTop: 4, fontSize: 10, color: 'var(--fg-subtle)', fontFamily: 'var(--mono)' }}>
              <span>0.30 · sensitive</span><span>0.50</span><span>0.70</span><span>0.95 · strict</span>
            </div>
          </div>

          <div className="divider"/>

          <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10 }}>Per-slice overrides</div>
          {['URLLC','eMBB','mMTC'].map(s => (
            <div key={s} style={{ marginBottom: 14 }}>
              <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                <div className="row">
                  <span className="mono" style={{ fontWeight: 500 }}>{s}</span>
                  <span className="muted" style={{ fontSize: 11 }}>
                    {s==='URLLC' && 'ultra-reliable low-latency'}
                    {s==='eMBB' && 'enhanced mobile broadband'}
                    {s==='mMTC' && 'massive machine-type comms'}
                  </span>
                </div>
                <div className="mono" style={{ fontSize: 13 }}>{sliceThresholds[s].toFixed(2)}</div>
              </div>
              <input type="range" min="0.3" max="0.95" step="0.01"
                value={sliceThresholds[s]}
                onChange={e => setSliceThresholds({ ...sliceThresholds, [s]: parseFloat(e.target.value) })}
                className="slider"/>
            </div>
          ))}
        </Panel>
      </div>

      <div className="span-4">
        <Panel title="Upload limits">
          <div className="form-field">
            <label className="form-label">Max rows per CSV</label>
            <input className="form-input" type="number" value={maxRows} onChange={e=>setMaxRows(+e.target.value)}/>
            <div className="form-hint">Hard cap per upload; spreads to validator and batch splitter.</div>
          </div>
          <div className="form-field">
            <label className="form-label">Max file size (MB)</label>
            <input className="form-input" type="number" defaultValue="50"/>
          </div>
          <div className="form-field">
            <label className="form-label">Null tolerance</label>
            <input className="form-input" type="number" defaultValue="10"/>
            <div className="form-hint">% of rows permitted to be fully null.</div>
          </div>
        </Panel>

        <div style={{ height: 12 }}/>

        <Panel title="Notifications">
          <div className="row" style={{ justifyContent: 'space-between', padding: '6px 0' }}>
            <div><div style={{ fontSize: 12, fontWeight: 500 }}>Drift alerts</div><div className="muted" style={{ fontSize: 11 }}>email on > 3 drifted features</div></div>
            <div className="toggle on"><div className="toggle-thumb"/></div>
          </div>
          <div className="row" style={{ justifyContent: 'space-between', padding: '6px 0' }}>
            <div><div style={{ fontSize: 12, fontWeight: 500 }}>Fairness alerts</div><div className="muted" style={{ fontSize: 11 }}>email on per-slice recall &lt; 0.8</div></div>
            <div className="toggle on"><div className="toggle-thumb"/></div>
          </div>
          <div className="row" style={{ justifyContent: 'space-between', padding: '6px 0' }}>
            <div><div style={{ fontSize: 12, fontWeight: 500 }}>Job completion</div><div className="muted" style={{ fontSize: 11 }}>notify job author</div></div>
            <div className="toggle"><div className="toggle-thumb"/></div>
          </div>
        </Panel>
      </div>
    </div>
  </>;
}

// ─────────── Drift & Fairness page ───────────
function DriftPage({ data }) {
  return <>
    <div className="page-head">
      <div>
        <h1 className="page-title">Drift & fairness</h1>
        <div className="page-desc">Distribution shift monitoring and per-slice performance audits</div>
      </div>
      <div className="page-actions">
        <Badge tone="warn" dot>2 active alerts</Badge>
        <Button variant="default" size="md" icon="download">Export audit log</Button>
      </div>
    </div>

    <div className="alert alert-warn" style={{ marginBottom: 12 }}>
      <Icon name="warn" size={16}/>
      <div>
        <div className="alert-title">Concept drift detected · job_3319</div>
        <div className="alert-body">Kolmogorov–Smirnov test flagged 3 of 24 monitored features (p &lt; 0.05). Autoencoder-6g-v1.4 may be stale.</div>
      </div>
      <div className="alert-actions">
        <Button variant="ghost" size="sm">Trigger retrain</Button>
        <Button variant="ghost" size="sm">Acknowledge</Button>
      </div>
    </div>

    <div className="grid dash-grid">
      <div className="span-7">
        <Panel title="Feature drift (KS two-sample)" subtitle="incoming batch vs. reference training distribution">
          <table className="tbl">
            <thead><tr>
              <th>Feature</th>
              <th className="num">KS statistic</th>
              <th className="num">p-value</th>
              <th>Distribution</th>
              <th>Status</th>
            </tr></thead>
            <tbody>
              {data.drift.features.map(f => (
                <tr key={f.name}>
                  <td><span className="mono">{f.name}</span></td>
                  <td className="num">{f.ks.toFixed(3)}</td>
                  <td className="num"><span style={{ color: f.drifted?'var(--critical)':'var(--fg-muted)' }}>{f.p.toFixed(3)}</span></td>
                  <td>
                    <div style={{ width: 120, height: 18, position: 'relative' }}>
                      <Sparkline data={Array.from({length: 20}, (_,i) => Math.sin(i/2 + (f.drifted?1:0)) + Math.random()*0.3)} stroke={f.drifted?'var(--critical)':'var(--fg-subtle)'} fill={true} height={18}/>
                    </div>
                  </td>
                  <td>
                    <Badge tone={f.drifted?'critical':'ok'} dot>
                      {f.drifted?'drifted':'stable'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>

      <div className="span-5">
        <Panel title="Per-slice fairness" subtitle="recall & precision by 6G network slice">
          {data.fairness.map(f => {
            const ok = f.recall >= 0.8;
            return (
              <div key={f.slice} style={{ marginBottom: 14 }}>
                <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
                  <div className="row">
                    <span className="mono" style={{ fontWeight: 500 }}>{f.slice}</span>
                    <Badge tone={ok?'ok':'critical'} dot>{ok?'within SLA':'below SLA'}</Badge>
                  </div>
                  <span className="muted mono" style={{ fontSize: 10 }}>support {f.support.toLocaleString()}</span>
                </div>
                <HBar label="recall" data={f.recall} max={1} color={ok?'var(--ok)':'var(--critical)'} value={f.recall.toFixed(3)}/>
                <HBar label="precision" data={f.precision} max={1} color="var(--accent)" value={f.precision.toFixed(3)}/>
              </div>
            );
          })}
          <div className="divider"/>
          <div className="alert alert-warn">
            <Icon name="warn" size={14}/>
            <div>
              <div className="alert-title">mMTC recall below SLA</div>
              <div className="alert-body">0.72 vs. target 0.80. 9,842 samples. Consider rebalancing training set or slice-specific model head.</div>
            </div>
          </div>
        </Panel>

        <div style={{ height: 12 }}/>

        <Panel title="Audit trail" subtitle="last 5 privileged actions">
          <div style={{ fontSize: 11, lineHeight: 1.8, fontFamily: 'var(--mono)' }}>
            <div className="row" style={{ justifyContent: 'space-between' }}><span className="muted">14:32:18</span><span>admin@sentra.io · threshold.update</span></div>
            <div className="row" style={{ justifyContent: 'space-between' }}><span className="muted">13:08:42</span><span>leila.ba · job.create</span></div>
            <div className="row" style={{ justifyContent: 'space-between' }}><span className="muted">12:51:04</span><span>admin@sentra.io · user.activate</span></div>
            <div className="row" style={{ justifyContent: 'space-between' }}><span className="muted">12:01:19</span><span>y.tanaka · model.inspect</span></div>
            <div className="row" style={{ justifyContent: 'space-between' }}><span className="muted">10:44:07</span><span>system · drift.alert</span></div>
          </div>
        </Panel>
      </div>
    </div>
  </>;
}

function ModelPage() {
  return <>
    <div className="page-head">
      <div>
        <h1 className="page-title">Model registry</h1>
        <div className="page-desc">Deployed models and versions</div>
      </div>
    </div>
    <Panel padding={false}>
      <table className="tbl">
        <thead><tr>
          <th>Model</th><th>Version</th><th>Algorithm</th><th className="num">Features</th><th>Deployed</th><th>Status</th>
        </tr></thead>
        <tbody>
          <tr>
            <td><span className="mono">autoencoder-6g</span></td>
            <td>v1.4</td><td>Variational AE</td>
            <td className="num">75</td>
            <td className="muted">2026-03-12</td>
            <td><Badge tone="ok" dot>active</Badge></td>
          </tr>
          <tr>
            <td><span className="mono">xgboost-5g</span></td>
            <td>v2.1</td><td>XGBoost</td>
            <td className="num">64</td>
            <td className="muted">2026-02-28</td>
            <td><Badge tone="ok" dot>active</Badge></td>
          </tr>
          <tr>
            <td><span className="mono">autoencoder-6g</span></td>
            <td>v1.3</td><td>Variational AE</td>
            <td className="num">75</td>
            <td className="muted">2026-01-15</td>
            <td><Badge tone="default" dot>archived</Badge></td>
          </tr>
        </tbody>
      </table>
    </Panel>
  </>;
}

Object.assign(window, { ResultsPage, UsersPage, SettingsPage, DriftPage, ModelPage });
