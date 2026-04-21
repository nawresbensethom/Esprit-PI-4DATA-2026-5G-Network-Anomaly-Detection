// Dashboard page
function DashboardPage({ data, threshold, onNavigate }) {
  const [selected, setSelected] = useState(null);

  // recompute KPIs based on threshold
  const predictions = useMemo(() => data.predictions.map(p => ({
    ...p,
    thresholdedClass: p.cls === 'benign' ? 'benign' : (p.conf >= threshold ? p.cls : 'benign'),
  })), [data.predictions, threshold]);

  const attackCount = predictions.filter(p => p.thresholdedClass !== 'benign').length;
  const total = predictions.length;
  const attackRate = attackCount / total;
  const avgConf = predictions.reduce((s,p)=>s+p.conf,0)/total;

  // Trend data — use data.trend
  const lineSeries = [
    { name: 'Total flows', color: 'var(--fg-subtle)', style: 'line',
      data: data.trend.map((t,i) => ({ x: i, label: t.label, y: t.total })) },
    { name: 'Attacks', color: 'var(--critical)', style: 'area',
      data: data.trend.map((t,i) => ({ x: i, label: t.label, y: t.attacks })) },
  ];

  // Attack distribution (donut)
  const typeColors = {
    benign: 'var(--ok)',
    ddos_volumetric: 'oklch(0.58 0.18 25)',
    ddos_syn: 'oklch(0.65 0.18 15)',
    port_scan: 'oklch(0.70 0.14 70)',
    c2_beacon: 'oklch(0.50 0.18 320)',
    data_exfil: 'oklch(0.55 0.18 0)',
    mqtt_anomaly: 'oklch(0.68 0.12 100)',
    slice_breach: 'oklch(0.62 0.14 50)',
  };
  const classCounts = {};
  predictions.forEach(p => { classCounts[p.thresholdedClass] = (classCounts[p.thresholdedClass]||0) + 1; });
  const segments = data.ATTACK_TYPES.filter(t => (classCounts[t.key]||0) > 0).map(t => ({
    label: t.label, value: classCounts[t.key]||0, color: typeColors[t.key],
  }));

  // Confidence histogram
  const confBuckets = [0,0,0,0,0];
  predictions.forEach(p => { const i = Math.min(4, Math.max(0, Math.floor((p.conf-0.5)*10))); confBuckets[i]++; });
  const maxConf = Math.max(...confBuckets);

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Detection overview</h1>
          <div className="page-desc">Live view · last 24 hours · model <span className="mono">autoencoder-6g-v1.4</span></div>
        </div>
        <div className="page-actions">
          <Badge tone="ok" dot>all systems operational</Badge>
          <Button variant="default" size="md" icon="download">Export</Button>
          <Button variant="primary" size="md" icon="upload" onClick={() => onNavigate('upload')}>New scan</Button>
        </div>
      </div>

      {/* Drift alert */}
      <div className="alert alert-warn" style={{ marginBottom: 12 }}>
        <Icon name="warn" size={16}/>
        <div>
          <div className="alert-title">Concept drift detected on 3 features in job <span className="mono">job_3319</span></div>
          <div className="alert-body">Rate_log (KS=0.31, p=0.003), SrcBytes_log (KS=0.24, p=0.012), SynAck_log (KS=0.19, p=0.041). Consider retraining.</div>
        </div>
        <div className="alert-actions">
          <Button variant="ghost" size="sm" onClick={() => onNavigate('drift')}>Review</Button>
          <Button variant="ghost" size="sm">Dismiss</Button>
        </div>
      </div>

      <div className="grid dash-grid" style={{ marginBottom: 12 }}>
        <div className="span-3"><Kpi label="Predictions (24h)" value={fmtN(total*13200)} delta={8.2} sub="vs. prev 24h"/></div>
        <div className="span-3"><Kpi label="Attack rate" value={fmtPct(attackRate)} delta={-2.3} sub={`threshold ${threshold.toFixed(2)}`}/></div>
        <div className="span-3"><Kpi label="Avg confidence" value={avgConf.toFixed(3)} sub="across all classes"/></div>
        <div className="span-3"><Kpi label="Active jobs" value="3" accent sub="2 running · 1 queued"/></div>
      </div>

      <div className="grid dash-grid">
        <div className="span-8">
          <Panel title="Detection volume" subtitle="flows per hour, attacks highlighted"
            actions={<>
              <div className="legend">
                <span><span className="legend-dot" style={{ background: 'var(--fg-subtle)' }}/>total</span>
                <span><span className="legend-dot" style={{ background: 'var(--critical)' }}/>attacks</span>
              </div>
              <Button variant="ghost" size="sm">24h</Button>
              <Button variant="ghost" size="sm">7d</Button>
            </>}>
            <LineChart series={lineSeries} height={220} annotations={[{ x: 4, label: 'drift' }]}/>
          </Panel>
        </div>

        <div className="span-4">
          <Panel title="Attack distribution" subtitle={`${attackCount.toLocaleString()} malicious · ${(total-attackCount).toLocaleString()} benign`}>
            <div className="row" style={{ alignItems: 'center', gap: 18 }}>
              <div style={{ position: 'relative' }}>
                <Donut segments={segments} size={140} thickness={14}/>
                <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center' }}>
                  <div>
                    <div className="mono" style={{ fontSize: 18, fontWeight: 500 }}>{fmtPct(attackRate, 0)}</div>
                    <div className="subtle" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>attack rate</div>
                  </div>
                </div>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                {segments.slice(0, 6).map((s,i) => (
                  <div key={i} className="row" style={{ padding: '3px 0', fontSize: 11 }}>
                    <span className="legend-dot" style={{ background: s.color }}/>
                    <span className="truncate" style={{ flex: 1 }}>{s.label}</span>
                    <span className="mono muted">{s.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </Panel>
        </div>

        <div className="span-5">
          <Panel title="Confidence distribution" subtitle="bucketed [0.5, 1.0]">
            <div style={{ padding: '2px 0 6px' }}>
              {['0.5–0.6','0.6–0.7','0.7–0.8','0.8–0.9','0.9–1.0'].map((r,i) => (
                <HBar key={i} label={r} data={confBuckets[i]} max={maxConf}
                  color={i>=3 ? 'var(--accent)' : 'var(--fg-subtle)'}
                  value={confBuckets[i]}/>
              ))}
            </div>
            <div className="divider"/>
            <div className="row" style={{ justifyContent: 'space-between', fontSize: 11 }}>
              <span className="muted">mean</span><span className="mono">{avgConf.toFixed(4)}</span>
              <span className="muted">p50</span><span className="mono">0.876</span>
              <span className="muted">p95</span><span className="mono">0.982</span>
            </div>
          </Panel>
        </div>

        <div className="span-7">
          <Panel title="Per-slice telemetry" subtitle="live recall & precision by network slice"
            actions={<Badge tone="warn" dot>mMTC · recall below SLA</Badge>}>
            <table className="tbl">
              <thead><tr>
                <th>Slice</th><th>SLA</th><th className="num">Support</th><th className="num">Recall</th><th className="num">Precision</th><th>Status</th>
              </tr></thead>
              <tbody>
                {data.fairness.map(f => {
                  const ok = f.recall >= 0.8;
                  return <tr key={f.slice}>
                    <td><span className="mono">{f.slice}</span></td>
                    <td className="muted">{f.slice==='URLLC'?'1ms · 99.999%':f.slice==='eMBB'?'10Gbps':'10⁶ dev/km²'}</td>
                    <td className="num muted">{f.support.toLocaleString()}</td>
                    <td className="num"><span className={cls(ok?'':'muted')} style={{ color: ok?'var(--ok)':'var(--critical)'}}>{f.recall.toFixed(3)}</span></td>
                    <td className="num">{f.precision.toFixed(3)}</td>
                    <td><Badge tone={ok?'ok':'critical'} dot>{ok?'within SLA':'below SLA'}</Badge></td>
                  </tr>;
                })}
              </tbody>
            </table>
          </Panel>
        </div>

        <div className="span-12">
          <Panel title="Recent predictions" subtitle={`${total} rows · auto-refresh 10s`}
            actions={<>
              <Button variant="ghost" size="sm" icon="filter">Filter</Button>
              <Button variant="ghost" size="sm" icon="download">Export</Button>
              <Button variant="ghost" size="sm" onClick={() => onNavigate('results')}>View all →</Button>
            </>}>
            <div className="tbl-wrap">
              <table className="tbl">
                <thead><tr>
                  <th>#</th><th>Source → Dest</th><th>Proto</th><th>Slice</th>
                  <th className="num">Bytes</th><th className="num">Pkts</th>
                  <th>Prediction</th><th className="num">Confidence</th>
                  <th>Time</th><th></th>
                </tr></thead>
                <tbody>
                  {predictions.slice(0, 14).map(p => (
                    <tr key={p.id} className="clickable" onClick={() => setSelected(p)}>
                      <td className="mono muted">{String(p.row).padStart(4,'0')}</td>
                      <td>
                        <span className="mono">{p.src}</span>
                        <span className="subtle" style={{ margin: '0 6px' }}>→</span>
                        <span className="mono">{p.dst}</span>
                      </td>
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
                      <td className="muted">{fmtTime(p.ts)}</td>
                      <td><span className="hlink" style={{ fontSize: 11 }}>Explain →</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </div>

      {selected && <PredictionDetail prediction={selected} data={data} onClose={() => setSelected(null)}/>}
    </>
  );
}

function PredictionDetail({ prediction: p, data, onClose }) {
  const shap = data.shap;
  const maxAbs = Math.max(...shap.map(s => s.abs));
  const basePred = shap.reduce((s,x) => s+x.value, 0);
  return (
    <>
      <div className="slideover-backdrop" onClick={onClose}/>
      <div className="slideover">
        <div className="slideover-head">
          <div>
            <div className="row" style={{ gap: 8 }}>
              <Badge tone={p.clsColor === 'critical' ? 'critical' : p.clsColor === 'warn' ? 'warn' : 'benign'} dot>{p.clsLabel}</Badge>
              <span className="mono muted" style={{ fontSize: 11 }}>row {p.row} · {p.id}</span>
            </div>
            <div style={{ fontWeight: 600, marginTop: 4, fontSize: 14 }}>
              <span className="mono">{p.src}</span> <span className="subtle">→</span> <span className="mono">{p.dst}</span>
            </div>
          </div>
          <button className="icon-btn" onClick={onClose}><Icon name="x"/></button>
        </div>
        <div className="slideover-body">
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
            <div><div className="muted" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Confidence</div><div className="mono" style={{ fontSize: 18, marginTop: 2 }}>{p.conf.toFixed(4)}</div></div>
            <div><div className="muted" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Slice</div><div className="mono" style={{ fontSize: 14, marginTop: 4 }}>{p.slice}</div></div>
            <div><div className="muted" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Protocol</div><div className="mono" style={{ fontSize: 14, marginTop: 4 }}>{p.proto}</div></div>
          </div>

          <div className="panel-sub" style={{ marginTop: 4, marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.06em' }}>SHAP · feature attribution</div>
          <div style={{ fontSize: 11, color: 'var(--fg-muted)', marginBottom: 8 }}>
            Red = pushes toward <b>{p.clsLabel}</b>, green = pushes toward benign. Base value E[f(X)] = 0.203.
          </div>
          {shap.map((s, i) => {
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
          <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Raw scores</div>
          <div className="mono" style={{ fontSize: 12, background: 'var(--bg-subtle)', padding: 12, borderRadius: 6, border: '1px solid var(--line)', lineHeight: 1.7 }}>
            <div><span className="muted">benign            </span>{(1-p.conf).toFixed(4)}</div>
            <div><span className="muted">malicious         </span>{p.conf.toFixed(4)}</div>
            <div><span className="muted">inference_time_ms </span>{(20 + (p.row%50)).toFixed(0)}</div>
            <div><span className="muted">model_version     </span>"autoencoder-6g-v1.4"</div>
          </div>

          <div className="divider"/>
          <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Recommended action</div>
          <div className="alert alert-crit" style={{ marginBottom: 8 }}>
            <Icon name="warn" size={14}/>
            <div><div className="alert-title">Isolate source address</div>
              <div className="alert-body">This flow exhibits high rate_log and anomalous SynAck_log, consistent with SYN-flood DDoS.</div>
            </div>
          </div>
          <div className="row" style={{ gap: 6 }}>
            <Button variant="danger" size="sm">Isolate host</Button>
            <Button variant="default" size="sm">Add to watchlist</Button>
            <Button variant="ghost" size="sm">Mark false positive</Button>
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { DashboardPage, PredictionDetail });
