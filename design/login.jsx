// Login screen
function LoginScreen({ onLogin, role, setRole, theme }) {
  const [email, setEmail] = useState('admin@sentra.io');
  const [pw, setPw] = useState('Admin123!');
  const [loading, setLoading] = useState(false);

  function submit(e) {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => onLogin(), 450);
  }

  return (
    <div className="login-shell">
      <div className="login-side">
        <div className="row" style={{ gap: 10, color: 'var(--fg)' }}>
          <Mark size={22}/>
          <div className="brand-name" style={{ fontSize: 16 }}>SENTRA</div>
          <div className="brand-tag">v2.4</div>
        </div>
        <div style={{ maxWidth: 460 }}>
          <div className="tag" style={{ marginBottom: 12 }}>6G · ANOMALY DETECTION</div>
          <h1 style={{ fontSize: 28, letterSpacing: '-0.02em', fontWeight: 600, margin: 0, lineHeight: 1.2 }}>
            Sub-second attack classification for sliced&nbsp;6G networks.
          </h1>
          <p className="muted" style={{ fontSize: 14, marginTop: 14, maxWidth: 420 }}>
            Batch inference, SHAP explanations, drift monitoring, and per-slice fairness — in one analyst console.
          </p>
          <div className="hero-card" style={{ marginTop: 24 }}>
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: 8 }}>
              <span className="muted" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Live · last 24h</span>
              <Badge tone="ok" dot>operational</Badge>
            </div>
            <div className="row"><span>predictions.total</span><span className="v" style={{ marginLeft: 'auto' }}>1,842,309</span></div>
            <div className="row"><span>predictions.attacks</span><span className="v" style={{ marginLeft: 'auto' }}>73,148</span></div>
            <div className="row"><span>avg_confidence</span><span className="v" style={{ marginLeft: 'auto' }}>0.912</span></div>
            <div className="row"><span>inference.p95_ms</span><span className="v" style={{ marginLeft: 'auto' }}>48</span></div>
            <div className="row"><span>drift_alerts</span><span className="v" style={{ marginLeft: 'auto', color: 'var(--warn-fg)' }}>2</span></div>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 11, fontFamily: 'var(--mono)' }}>© 2026 SENTRA Labs · build e14b2a</div>
      </div>
      <div className="login-form-wrap">
        <form className="login-form" onSubmit={submit}>
          <h2 className="login-title">Sign in</h2>
          <p className="login-sub">Access the detection console.</p>

          <div className="form-field">
            <label className="form-label">Email</label>
            <input className="form-input" value={email} onChange={e=>setEmail(e.target.value)} />
          </div>
          <div className="form-field">
            <label className="form-label">Password</label>
            <input className="form-input" type="password" value={pw} onChange={e=>setPw(e.target.value)} />
          </div>
          <div className="form-field">
            <label className="form-label">Role</label>
            <select className="form-select" value={role} onChange={e=>setRole(e.target.value)}>
              <option value="analyst">Security Analyst</option>
              <option value="admin">Administrator</option>
              <option value="ml_engineer">ML Engineer</option>
            </select>
            <div className="form-hint">Demo: role selector — normally derived from user record.</div>
          </div>

          <Button type="submit" variant="primary" size="lg" className="btn-block" disabled={loading}>
            {loading ? 'Authenticating…' : 'Continue'} <Icon name="arrow" size={14}/>
          </Button>

          <div className="divider"/>
          <div className="subtle" style={{ fontSize: 11, fontFamily: 'var(--mono)', textAlign: 'center' }}>
            SSO · SAML · MFA  ·  2026.04.20
          </div>
        </form>
      </div>
    </div>
  );
}

Object.assign(window, { LoginScreen });
