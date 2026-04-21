"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Badge, Button, Icon, Mark } from "@/components/ui";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@esprit.tn");
  const [password, setPassword] = useState("Admin123!");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/upload");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-side">
        <div className="row" style={{ gap: 10, color: "var(--fg)" }}>
          <Mark size={22} />
          <div className="brand-name" style={{ fontSize: 16 }}>SENTRA</div>
          <div className="brand-tag">v2.4</div>
        </div>
        <div style={{ maxWidth: 460 }}>
          <div className="tag" style={{ marginBottom: 12 }}>6G · ANOMALY DETECTION</div>
          <h1 style={{ fontSize: 28, letterSpacing: "-0.02em", fontWeight: 600, margin: 0, lineHeight: 1.2 }}>
            Sub-second attack classification for sliced&nbsp;6G networks.
          </h1>
          <p className="muted" style={{ fontSize: 14, marginTop: 14, maxWidth: 420 }}>
            Batch inference, drift monitoring, and per-slice fairness — in one analyst console.
          </p>
          <div className="hero-card" style={{ marginTop: 24 }}>
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <span className="muted" style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.08em" }}>Live · backend</span>
              <Badge tone="ok" dot>operational</Badge>
            </div>
            <div className="row"><span>moe-ids.api</span><span className="v" style={{ marginLeft: "auto" }}>:8000</span></div>
            <div className="row"><span>auth-svc</span><span className="v" style={{ marginLeft: "auto" }}>:8001</span></div>
            <div className="row"><span>inference-svc</span><span className="v" style={{ marginLeft: "auto" }}>:8003</span></div>
            <div className="row"><span>gateway</span><span className="v" style={{ marginLeft: "auto" }}>:8090</span></div>
          </div>
        </div>
        <div className="muted" style={{ fontSize: 11, fontFamily: "var(--mono)" }}>© 2026 Esprit · 4DATA · MoE IDS</div>
      </div>
      <div className="login-form-wrap">
        <form className="login-form" onSubmit={submit}>
          <h2 className="login-title">Sign in</h2>
          <p className="login-sub">Access the detection console.</p>

          <div className="form-field">
            <label className="form-label">Email</label>
            <input
              className="form-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>
          <div className="form-field">
            <label className="form-label">Password</label>
            <input
              className="form-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="alert alert-crit" style={{ marginBottom: 12 }}>
              <Icon name="warn" size={14} />
              <div>
                <div className="alert-title">Sign-in failed</div>
                <div className="alert-body">{error}</div>
              </div>
            </div>
          )}

          <Button type="submit" variant="primary" size="lg" className="btn-block" disabled={loading}>
            {loading ? "Authenticating…" : "Continue"} <Icon name="arrow" size={14} />
          </Button>

          <div className="divider" />
          <div className="subtle" style={{ fontSize: 11, fontFamily: "var(--mono)", textAlign: "center" }}>
            Default admin · admin@esprit.tn / Admin123!
          </div>
        </form>
      </div>
    </div>
  );
}