// Upload page + history + admin + drift
function UploadPage({ data, onComplete, onNavigate }) {
  const [stage, setStage] = useState('idle'); // idle, validating, invalid, ready, uploading, pending, running, completed
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [errors, setErrors] = useState([]);
  const [validateMode, setValidateMode] = useState('valid'); // 'valid' or 'invalid'
  const inputRef = useRef();

  function pick() { inputRef.current?.click(); }

  function handleFile(f) {
    const name = f?.name || 'cicflow_6g_urllc_2026-04-20.csv';
    const size = f?.size || 2845312;
    setFile({ name, size, rows: 14456, cols: 64 });
    setStage('validating');
    setTimeout(() => {
      if (validateMode === 'invalid') {
        setErrors([
          'Missing required column: SynAck_log',
          'Column sTtl contains 127 non-numeric values',
          '8.2% of rows are fully null (threshold: 10%)',
        ]);
        setStage('invalid');
      } else {
        setErrors([]);
        setStage('ready');
      }
    }, 900);
  }

  function startUpload() {
    setStage('uploading');
    setProgress(0);
    const iv = setInterval(() => {
      setProgress(p => {
        const np = p + 8 + Math.random()*10;
        if (np >= 100) { clearInterval(iv); setStage('pending'); setTimeout(() => setStage('running'), 700); return 100; }
        return np;
      });
    }, 140);
  }

  // auto-advance running → completed
  useEffect(() => {
    if (stage === 'running') {
      const t = setTimeout(() => setStage('completed'), 3800);
      return () => clearTimeout(t);
    }
  }, [stage]);

  function reset() {
    setStage('idle'); setFile(null); setErrors([]); setProgress(0);
  }

  const steps = [
    { key: 'pending', label: 'Queued' },
    { key: 'running', label: 'Fetching from MinIO' },
    { key: 'inference', label: 'Running inference' },
    { key: 'persisting', label: 'Persisting results' },
    { key: 'completed', label: 'Complete' },
  ];
  const stageOrder = ['idle','validating','ready','uploading','pending','running','completed'];
  const stageIdx = stageOrder.indexOf(stage);

  function stepState(i) {
    if (stage === 'completed') return 'done';
    if (stage === 'running' && i < 3) return i < 2 ? 'done' : 'active';
    if (stage === 'pending' && i === 0) return 'active';
    if (stage === 'pending' && i < 0) return 'done';
    return 'idle';
  }

  return <>
    <div className="page-head">
      <div>
        <h1 className="page-title">New scan</h1>
        <div className="page-desc">Upload a CSV of 5G/6G network flows. Max 50 MB · up to 100,000 rows.</div>
      </div>
      <div className="page-actions">
        <div className="tweak-chips" style={{ marginRight: 4 }}>
          <span className="subtle" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em', alignSelf: 'center', marginRight: 6 }}>demo validation</span>
          <button className={cls('tweak-chip', validateMode==='valid' && 'on')} onClick={()=>setValidateMode('valid')}>valid</button>
          <button className={cls('tweak-chip', validateMode==='invalid' && 'on')} onClick={()=>setValidateMode('invalid')}>invalid</button>
        </div>
      </div>
    </div>

    <div className="grid dash-grid">
      <div className="span-8">
        <Panel title="Upload" padding={false}>
          <div style={{ padding: 16 }}>
            {(stage === 'idle' || stage === 'validating' || stage === 'invalid' || stage === 'ready') && (
              <div className={cls('dropzone', dragging && 'active')}
                onClick={pick}
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}>
                <input ref={inputRef} type="file" accept=".csv" style={{ display: 'none' }}
                  onChange={e => e.target.files[0] && handleFile(e.target.files[0])}/>
                <div className="dropzone-icon"><Icon name="upload" size={20}/></div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>Drop CSV file here</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>or click to browse · accepts <span className="mono">.csv</span> up to 50MB</div>
                <div className="row" style={{ justifyContent: 'center', gap: 6, marginTop: 14 }}>
                  <span className="tag">sTtl</span><span className="tag">dTtl</span><span className="tag">Rate_log</span><span className="tag">SrcBytes_log</span><span className="tag muted">+60 more</span>
                </div>
              </div>
            )}

            {file && stage !== 'idle' && (
              <div className="panel" style={{ marginTop: 14, border: '1px solid var(--line)' }}>
                <div className="row" style={{ padding: 12, gap: 12 }}>
                  <div style={{ width: 36, height: 36, borderRadius: 6, background: 'var(--bg-subtle)', display: 'grid', placeItems: 'center', color: 'var(--fg-muted)', flexShrink: 0 }}>
                    <Icon name="file" size={18}/>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="mono" style={{ fontSize: 12, fontWeight: 500 }}>{file.name}</div>
                    <div className="muted" style={{ fontSize: 11 }}>
                      {(file.size/1024/1024).toFixed(2)} MB · {file.rows.toLocaleString()} rows × {file.cols} cols
                      {stage === 'validating' && <> · <span style={{ color: 'var(--accent)' }}>validating schema…</span></>}
                      {stage === 'ready' && <> · <span style={{ color: 'var(--ok)' }}>schema valid</span></>}
                      {stage === 'invalid' && <> · <span style={{ color: 'var(--critical)' }}>{errors.length} error{errors.length!==1?'s':''}</span></>}
                    </div>
                  </div>
                  <button className="icon-btn" onClick={reset}><Icon name="x"/></button>
                </div>
              </div>
            )}

            {stage === 'invalid' && (
              <div className="alert alert-crit" style={{ marginTop: 10 }}>
                <Icon name="warn" size={16}/>
                <div>
                  <div className="alert-title">Validation failed</div>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 18, fontSize: 12 }}>
                    {errors.map((e,i) => <li key={i} style={{ color: 'var(--fg-muted)' }}>{e}</li>)}
                  </ul>
                </div>
              </div>
            )}

            {(stage === 'ready' || stage === 'uploading' || stage === 'pending' || stage === 'running' || stage === 'completed') && (
              <div style={{ marginTop: 12 }}>
                <div className="row" style={{ marginBottom: 10, justifyContent: 'space-between' }}>
                  <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>Job pipeline</div>
                  <span className="mono muted" style={{ fontSize: 11 }}>
                    {stage === 'completed' ? 'job_a3f1 · 2m 14s' : stage === 'running' ? 'job_a3f1 · running' : 'job_a3f1 · pending'}
                  </span>
                </div>
                <div className="steps">
                  {steps.map((s, i) => {
                    let state = 'idle';
                    if (stage === 'completed') state = 'done';
                    else if (stage === 'running' && i <= 2) state = i < 2 ? 'done' : 'active';
                    else if (stage === 'pending' && i === 0) state = 'active';
                    else if (stage === 'uploading' && i === 0) state = 'active';
                    return <div key={s.key} className={cls('step', state)}>
                      <div className="step-dot">
                        {state === 'done' && <Icon name="check" size={10}/>}
                      </div>
                      <span>{s.label}</span>
                    </div>;
                  })}
                </div>
                {stage === 'uploading' && (
                  <div style={{ marginTop: 10 }}>
                    <div className="row" style={{ justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                      <span className="muted">Uploading to MinIO…</span>
                      <span className="mono">{progress.toFixed(0)}%</span>
                    </div>
                    <div className="progress-bar"><div className="progress-bar-fill" style={{ width: progress+'%' }}/></div>
                  </div>
                )}
              </div>
            )}

            <div className="row" style={{ marginTop: 14, justifyContent: 'flex-end', gap: 8 }}>
              {stage === 'ready' && <>
                <Button variant="ghost" onClick={reset}>Cancel</Button>
                <Button variant="primary" icon="play" onClick={startUpload}>Start prediction</Button>
              </>}
              {stage === 'invalid' && <Button variant="default" onClick={reset}>Choose another file</Button>}
              {stage === 'completed' && <>
                <Button variant="ghost" onClick={reset}>New scan</Button>
                <Button variant="primary" onClick={() => onNavigate('results')}>View results →</Button>
              </>}
            </div>
          </div>
        </Panel>
      </div>

      <div className="span-4">
        <Panel title="Schema requirements" subtitle="CSV columns & constraints">
          <div style={{ fontSize: 12, lineHeight: 1.8 }}>
            <div className="row"><Icon name="check" size={14} style={{ color: 'var(--ok)' }}/><span className="muted">Extension</span><span className="mono" style={{ marginLeft: 'auto' }}>.csv</span></div>
            <div className="row"><Icon name="check" size={14} style={{ color: 'var(--ok)' }}/><span className="muted">Max size</span><span className="mono" style={{ marginLeft: 'auto' }}>50 MB</span></div>
            <div className="row"><Icon name="check" size={14} style={{ color: 'var(--ok)' }}/><span className="muted">Max rows</span><span className="mono" style={{ marginLeft: 'auto' }}>100,000</span></div>
            <div className="row"><Icon name="check" size={14} style={{ color: 'var(--ok)' }}/><span className="muted">Null tolerance</span><span className="mono" style={{ marginLeft: 'auto' }}>≤ 10%</span></div>
            <div className="row"><Icon name="check" size={14} style={{ color: 'var(--ok)' }}/><span className="muted">Required cols</span><span className="mono" style={{ marginLeft: 'auto' }}>64 (5G) / 75 (6G)</span></div>
          </div>
          <div className="divider"/>
          <div className="panel-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>First 8 features</div>
          <div className="row" style={{ flexWrap: 'wrap', gap: 4 }}>
            {data.FEATURES.slice(0,16).map(f => <span key={f} className="tag">{f}</span>)}
          </div>
          <div className="divider"/>
          <div className="hlink" style={{ fontSize: 11 }}>Download template CSV →</div>
        </Panel>

        <div style={{ height: 12 }}/>

        <Panel title="Detection model" subtitle="active endpoint">
          <div className="mono" style={{ fontSize: 12, lineHeight: 1.9 }}>
            <div className="row"><span className="muted">model</span><span style={{ marginLeft: 'auto' }}>autoencoder-6g-v1.4</span></div>
            <div className="row"><span className="muted">algorithm</span><span style={{ marginLeft: 'auto' }}>Variational AE</span></div>
            <div className="row"><span className="muted">features</span><span style={{ marginLeft: 'auto' }}>75</span></div>
            <div className="row"><span className="muted">trained</span><span style={{ marginLeft: 'auto' }}>2026-03-12</span></div>
            <div className="row"><span className="muted">endpoint</span><Badge tone="ok" dot>healthy</Badge></div>
          </div>
        </Panel>
      </div>
    </div>
  </>;
}

// ─────────── History ───────────
function HistoryPage({ data, onNavigate }) {
  const [sortKey, setSortKey] = useState('created');
  const [sortDir, setSortDir] = useState('desc');
  const [filter, setFilter] = useState('all');

  const filtered = data.jobs.filter(j => filter === 'all' || j.status === filter);
  const sorted = [...filtered].sort((a,b) => {
    const av = a[sortKey], bv = b[sortKey];
    const d = typeof av === 'string' ? av.localeCompare(bv) : (av - bv);
    return sortDir === 'asc' ? d : -d;
  });

  function setSort(k) {
    if (sortKey === k) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortKey(k); setSortDir('desc'); }
  }

  function Th({ k, children, align }) {
    const sorted = sortKey === k;
    return <th className={cls('sortable', sorted && 'sorted', align === 'right' && 'num')} onClick={()=>setSort(k)}>
      <span className="row" style={{ gap: 4, justifyContent: align === 'right' ? 'flex-end' : 'flex-start' }}>
        {children}
        {sorted && <Icon name={sortDir==='desc'?'down':'up'} size={10}/>}
      </span>
    </th>;
  }

  return <>
    <div className="page-head">
      <div>
        <h1 className="page-title">Prediction history</h1>
        <div className="page-desc">{filtered.length} jobs · sort and filter to review past scans</div>
      </div>
      <div className="page-actions">
        <Button variant="default" size="md" icon="download">Export list</Button>
        <Button variant="primary" size="md" icon="upload" onClick={() => onNavigate('upload')}>New scan</Button>
      </div>
    </div>

    <Panel padding={false}>
      <div className="stat-strip">
        <div className="stat"><span className="stat-label">Total jobs</span><span className="stat-value">{data.jobs.length}</span></div>
        <div className="stat"><span className="stat-label">Completed</span><span className="stat-value" style={{ color: 'var(--ok)' }}>{data.jobs.filter(j=>j.status==='completed').length}</span></div>
        <div className="stat"><span className="stat-label">Running</span><span className="stat-value" style={{ color: 'var(--accent)' }}>{data.jobs.filter(j=>j.status==='running').length}</span></div>
        <div className="stat"><span className="stat-label">Failed</span><span className="stat-value" style={{ color: 'var(--critical)' }}>{data.jobs.filter(j=>j.status==='failed').length}</span></div>
        <div className="stat"><span className="stat-label">Rows processed</span><span className="stat-value">{fmtN(data.jobs.reduce((s,j)=>s+j.rows,0))}</span></div>
        <div className="stat"><span className="stat-label">Avg attack rate</span><span className="stat-value">{fmtPct(data.jobs.reduce((s,j)=>s+j.attackRate,0)/data.jobs.length)}</span></div>
        <div style={{ marginLeft: 'auto' }} className="row">
          <span className="subtle" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>filter</span>
          <div className="tweak-chips">
            {['all','completed','running','failed'].map(f => (
              <button key={f} className={cls('tweak-chip', filter===f && 'on')} onClick={()=>setFilter(f)}>{f}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr>
            <Th k="status">Status</Th>
            <Th k="id">Job</Th>
            <Th k="filename">File</Th>
            <Th k="slice">Slice</Th>
            <Th k="rows" align="right">Rows</Th>
            <Th k="attacks" align="right">Attacks</Th>
            <Th k="attackRate" align="right">Attack rate</Th>
            <Th k="duration" align="right">Duration</Th>
            <Th k="created">Created</Th>
            <th>Flags</th>
            <th></th>
          </tr></thead>
          <tbody>
            {sorted.map(j => (
              <tr key={j.id} className="clickable" onClick={() => onNavigate('results')}>
                <td>
                  <Badge tone={j.status==='completed'?'ok':j.status==='running'?'accent':'critical'} dot>
                    {j.status}
                  </Badge>
                </td>
                <td className="mono">{j.id}</td>
                <td className="truncate" style={{ maxWidth: 240 }}>{j.filename}</td>
                <td><span className="mono muted">{j.slice}</span></td>
                <td className="num">{fmtN(j.rows)}</td>
                <td className="num">{fmtN(j.attacks)}</td>
                <td className="num">
                  <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                    <div style={{ width: 40, height: 3, background: 'var(--bg-subtle)', borderRadius: 2 }}>
                      <div style={{ width: `${j.attackRate*100}%`, height: '100%', background: j.attackRate > 0.3 ? 'var(--critical)' : 'var(--accent)', borderRadius: 2 }}/>
                    </div>
                    <span>{fmtPct(j.attackRate)}</span>
                  </div>
                </td>
                <td className="num muted">{fmtDur(j.duration)}</td>
                <td className="muted">{fmtDate(j.created)}</td>
                <td>
                  <div className="row" style={{ gap: 4 }}>
                    {j.drift && <Badge tone="warn">drift</Badge>}
                    {j.fairness && <Badge tone="warn">fairness</Badge>}
                  </div>
                </td>
                <td><Icon name="arrow" size={14} className="muted"/></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  </>;
}

Object.assign(window, { UploadPage, HistoryPage });
