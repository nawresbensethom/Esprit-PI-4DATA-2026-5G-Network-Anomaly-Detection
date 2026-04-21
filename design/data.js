// Mock data for SENTRA dashboard
window.SENTRA_DATA = (() => {
  // Seeded RNG for stable data
  let seed = 42;
  const rand = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };

  const ATTACK_TYPES = [
    { key: 'benign', label: 'Benign', color: 'benign' },
    { key: 'ddos_volumetric', label: 'DDoS · Volumetric', color: 'critical' },
    { key: 'ddos_syn', label: 'DDoS · SYN flood', color: 'critical' },
    { key: 'port_scan', label: 'Reconnaissance · Port scan', color: 'warn' },
    { key: 'c2_beacon', label: 'C2 Beacon', color: 'critical' },
    { key: 'data_exfil', label: 'Data exfiltration', color: 'critical' },
    { key: 'mqtt_anomaly', label: 'MQTT anomaly', color: 'warn' },
    { key: 'slice_breach', label: 'Slice isolation breach', color: 'warn' },
  ];

  const SLICES = ['URLLC', 'eMBB', 'mMTC'];

  const FEATURES = [
    'sTtl', 'dTtl', 'sHops', 'dHops', 'SrcWin_log', 'SrcPkts_log',
    'SrcBytes_log', 'TotPkts_log', 'TotBytes_log', 'Rate_log',
    'Offset_log', 'sMeanPktSz_log', 'SynAck_log', 'SrcLoad_log',
    'Load_log', 'TcpRtt_log', 'DstTCPBase', 'SrcTCPBase',
    'dDSb_ef', 'SrcLoss_ratio', 'State_ECO', 'State_REQ',
    'State_RST', 'Proto_udp'
  ];

  function genIP() {
    return `10.${(rand()*255)|0}.${(rand()*255)|0}.${(rand()*255)|0}`;
  }

  // Generate recent predictions
  const predictions = [];
  for (let i = 0; i < 140; i++) {
    const r = rand();
    const cls = r < 0.62 ? ATTACK_TYPES[0] : ATTACK_TYPES[1 + ((rand()*7)|0)];
    const conf = cls.key === 'benign'
      ? 0.55 + rand() * 0.44
      : 0.70 + rand() * 0.29;
    predictions.push({
      id: `p_${1000+i}`,
      row: i,
      src: genIP(),
      dst: genIP(),
      proto: ['TCP','UDP','ICMP','TCP','TCP'][(rand()*5)|0],
      slice: SLICES[(rand()*3)|0],
      bytes: ((rand()*8000)|0) + 64,
      pkts: ((rand()*120)|0) + 1,
      cls: cls.key,
      clsLabel: cls.label,
      clsColor: cls.color,
      conf: +conf.toFixed(4),
      ts: Date.now() - i * 1000 * (30 + rand()*90),
    });
  }

  // Distribution
  const classDist = {};
  for (const t of ATTACK_TYPES) classDist[t.key] = 0;
  for (const p of predictions) classDist[p.cls]++;

  // Confidence histogram
  const confBuckets = [
    { range: '0.5–0.6', count: 0 },
    { range: '0.6–0.7', count: 0 },
    { range: '0.7–0.8', count: 0 },
    { range: '0.8–0.9', count: 0 },
    { range: '0.9–1.0', count: 0 },
  ];
  for (const p of predictions) {
    const idx = Math.min(4, Math.max(0, Math.floor((p.conf - 0.5) * 10)));
    confBuckets[idx].count++;
  }

  // Trend (last 24 hours, per hour)
  const trend = [];
  for (let h = 23; h >= 0; h--) {
    const base = 40 + Math.sin(h/3) * 15 + rand() * 20;
    const attacks = Math.max(0, base * (0.25 + rand()*0.2));
    trend.push({
      hour: h,
      label: `${String((new Date().getHours() - h + 24) % 24).padStart(2,'0')}:00`,
      total: Math.round(base + attacks),
      attacks: Math.round(attacks),
      benign: Math.round(base),
    });
  }

  // Jobs history
  const FILES = [
    'cicflow_6g_urllc_2026-04-19.csv',
    'ton_iot_embb_batch_042.csv',
    'capture_mmtc_nodes_edge07.csv',
    'slice_a_flows_1200Z.csv',
    'ran_telemetry_2026-04-18.csv',
    'edge_agg_firewall_019.csv',
    'corp_vpn_egress_0417.csv',
    'iot_gateway_42_hourly.csv',
    'slice_b_flows_0600Z.csv',
    'cicflow_6g_urllc_2026-04-17.csv',
    'probe_hexa_ring3.csv',
    'bsr_handover_042.csv',
  ];
  const STATUSES = ['completed','completed','completed','completed','failed','completed','completed','completed','running','completed','completed','completed'];
  const jobs = FILES.map((f, i) => {
    const rows = 1200 + ((rand()*40000)|0);
    const attackRate = 0.08 + rand() * 0.45;
    const status = STATUSES[i];
    return {
      id: `job_${(8423 + i).toString(16)}`,
      filename: f,
      rows,
      attackRate: +attackRate.toFixed(3),
      attacks: Math.round(rows * attackRate),
      status,
      created: Date.now() - i * 1000 * 60 * (45 + rand()*300),
      duration: 8 + ((rand()*240)|0),
      drift: i === 2 || i === 5,
      fairness: i === 7,
      model: i % 3 === 0 ? 'xgboost-5g-v2.1' : 'autoencoder-6g-v1.4',
      slice: SLICES[(rand()*3)|0],
    };
  });

  // SHAP values for a sample
  const shap = [
    { feature: 'SrcBytes_log', value: 0.34, abs: 0.34 },
    { feature: 'Rate_log', value: 0.21, abs: 0.21 },
    { feature: 'SynAck_log', value: 0.18, abs: 0.18 },
    { feature: 'TcpRtt_log', value: -0.12, abs: 0.12 },
    { feature: 'sTtl', value: 0.09, abs: 0.09 },
    { feature: 'State_RST', value: 0.07, abs: 0.07 },
    { feature: 'sHops', value: -0.06, abs: 0.06 },
    { feature: 'Proto_udp', value: 0.04, abs: 0.04 },
    { feature: 'SrcLoss_ratio', value: -0.03, abs: 0.03 },
    { feature: 'DstTCPBase', value: 0.02, abs: 0.02 },
  ];

  // Users for admin page
  const users = [
    { id: 'u1', name: 'Admin User', email: 'admin@sentra.io', role: 'admin', active: true, last: Date.now() - 1000*60*3 },
    { id: 'u2', name: 'Leïla Ben Amor', email: 'leila.ba@sentra.io', role: 'analyst', active: true, last: Date.now() - 1000*60*18 },
    { id: 'u3', name: 'Marcus Odili', email: 'm.odili@sentra.io', role: 'analyst', active: true, last: Date.now() - 1000*60*120 },
    { id: 'u4', name: 'Yuki Tanaka', email: 'y.tanaka@sentra.io', role: 'ml_engineer', active: true, last: Date.now() - 1000*60*60*6 },
    { id: 'u5', name: 'Rania Kacem', email: 'r.kacem@sentra.io', role: 'analyst', active: false, last: Date.now() - 1000*60*60*24*14 },
    { id: 'u6', name: 'Dmitri Volkov', email: 'd.volkov@sentra.io', role: 'ml_engineer', active: true, last: Date.now() - 1000*60*60*48 },
    { id: 'u7', name: 'Sara Nouri', email: 's.nouri@sentra.io', role: 'analyst', active: true, last: Date.now() - 1000*60*34 },
  ];

  // Drift report
  const drift = {
    triggered: true,
    features: [
      { name: 'Rate_log', ks: 0.31, p: 0.003, drifted: true },
      { name: 'SrcBytes_log', ks: 0.24, p: 0.012, drifted: true },
      { name: 'SynAck_log', ks: 0.19, p: 0.041, drifted: true },
      { name: 'TcpRtt_log', ks: 0.11, p: 0.089, drifted: false },
      { name: 'sTtl', ks: 0.08, p: 0.21, drifted: false },
    ],
  };

  // Fairness
  const fairness = [
    { slice: 'URLLC', recall: 0.94, precision: 0.91, support: 12430 },
    { slice: 'eMBB', recall: 0.88, precision: 0.86, support: 18200 },
    { slice: 'mMTC', recall: 0.72, precision: 0.81, support: 9842 },
  ];

  return {
    ATTACK_TYPES, SLICES, FEATURES,
    predictions, classDist, confBuckets, trend,
    jobs, shap, users, drift, fairness,
  };
})();
