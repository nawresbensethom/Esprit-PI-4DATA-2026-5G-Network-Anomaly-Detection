// Sidebar / shell / topbar
const NAV_BY_ROLE = {
  analyst: [
    { section: 'Workspace' },
    { key: 'dashboard', label: 'Dashboard', icon: 'dash' },
    { key: 'upload', label: 'New scan', icon: 'upload' },
    { key: 'history', label: 'History', icon: 'history', count: 12 },
    { key: 'results', label: 'Results', icon: 'results' },
  ],
  admin: [
    { section: 'Workspace' },
    { key: 'dashboard', label: 'Dashboard', icon: 'dash' },
    { key: 'upload', label: 'New scan', icon: 'upload' },
    { key: 'history', label: 'History', icon: 'history', count: 12 },
    { key: 'results', label: 'Results', icon: 'results' },
    { section: 'Administration' },
    { key: 'users', label: 'Users', icon: 'users', count: 7 },
    { key: 'settings', label: 'Thresholds & config', icon: 'settings' },
    { key: 'drift', label: 'Drift & fairness', icon: 'drift', count: 2, badge: 'warn' },
  ],
  ml_engineer: [
    { section: 'Workspace' },
    { key: 'dashboard', label: 'Dashboard', icon: 'dash' },
    { key: 'history', label: 'History', icon: 'history', count: 12 },
    { key: 'results', label: 'Results', icon: 'results' },
    { section: 'Models' },
    { key: 'drift', label: 'Drift & fairness', icon: 'drift', count: 2, badge: 'warn' },
    { key: 'model', label: 'Model registry', icon: 'model' },
  ],
};

const ROLE_LABELS = { analyst: 'Security Analyst', admin: 'Administrator', ml_engineer: 'ML Engineer' };

function Sidebar({ route, setRoute, role, user, onSignOut }) {
  const items = NAV_BY_ROLE[role] || NAV_BY_ROLE.analyst;
  return (
    <aside className="sidebar">
      <div className="brand">
        <Mark size={20}/>
        <div className="brand-name">SENTRA</div>
        <div className="brand-tag">v2.4</div>
      </div>
      {items.map((it, i) => it.section
        ? <div key={i} className="nav-section-label">{it.section}</div>
        : (
          <div key={it.key}
            className={cls('nav-item', route === it.key && 'active')}
            onClick={() => setRoute(it.key)}>
            <Icon name={it.icon} size={15}/>
            <span>{it.label}</span>
            {it.count != null && <span className="nav-count">{it.count}</span>}
          </div>
        )
      )}
      <div className="sidebar-footer">
        <div className="user-card" onClick={onSignOut} title="Sign out">
          <div className="avatar">{user.name.split(' ').map(n=>n[0]).slice(0,2).join('')}</div>
          <div className="user-info">
            <div className="user-name">{user.name}</div>
            <div className="user-role">{ROLE_LABELS[role]}</div>
          </div>
          <Icon name="chev" size={14}/>
        </div>
      </div>
    </aside>
  );
}

function Topbar({ crumbs, actions, onCmd }) {
  return (
    <div className="topbar">
      <div className="crumbs">
        {crumbs.map((c, i) => <React.Fragment key={i}>
          {i > 0 && <span className="sep">/</span>}
          <span className={i === crumbs.length-1 ? 'cur' : ''}>{c}</span>
        </React.Fragment>)}
      </div>
      <div className="topbar-spacer"/>
      <div className="search-box">
        <Icon name="search" size={14}/>
        <input placeholder="Search jobs, IPs, CVEs…"/>
        <span className="kbd">⌘K</span>
      </div>
      <button className="icon-btn" title="Notifications">
        <Icon name="bell" size={15}/>
        <span className="dot-ind"/>
      </button>
      {actions}
    </div>
  );
}

Object.assign(window, { Sidebar, Topbar, NAV_BY_ROLE, ROLE_LABELS });
