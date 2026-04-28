# Demo Checklist — Jury Validation

One‑page runbook for the next‑week validation. Companion to:
- [JURY_NEXT_WEEK_PLAN.md](JURY_NEXT_WEEK_PLAN.md) — gap analysis & rationale
- [MOE_IDS_GUIDE.md](MOE_IDS_GUIDE.md) — MoE IDS background
- [PROJECT_CHANGES_SUMMARY.md](PROJECT_CHANGES_SUMMARY.md) — dashboard integration

---

## 0. Prerequisites (do once, before demo day)

### 0.1 GitHub secrets (one‑time, ~3 min)
Go to https://github.com/nawresbensethom/Esprit-PI-4DATA-2026-6G-Network-Anomaly-Detection/settings/secrets/actions and add:

| Secret | Value | Used by |
|---|---|---|
| `DOCKERHUB_USER` | your DockerHub username | CD: build & push |
| `DOCKERHUB_TOKEN` | DockerHub access token (Settings → Security → New Access Token, scope **Read+Write+Delete**) | CD: build & push |
| `SLACK_WEBHOOK_URL` | optional — Slack Incoming Webhook URL | CI/CD failure alerts + drift alerts |

### 0.2 DockerHub repos
First push will auto‑create them if your DockerHub account allows it. Otherwise create these 9 repos manually under your DockerHub account:
`moe-inference` · `moe-training` · `moe-monitoring` · `dashboard-gateway` · `dashboard-auth` · `dashboard-inference` · `dashboard-upload` · `dashboard-report` · `dashboard-frontend`

### 0.3 Local `.env`
```bash
cp .env.example .env
# Then edit .env and set INTERNAL_API_KEY to something other than "changeme"
# (otherwise auth between gateway and ML services is bypassed).
```

### 0.4 Format / commit hygiene (recommended)
```bash
# Format the codebase once so the first CI run isn't red on format-check
make -C moe-ids format
git add -A && git commit -m "chore: black + ruff format"
```

---

## 1. Boot the stack (one command)

```bash
docker compose up --build -d
docker compose ps
```

First build takes ~10‑15 min (TensorFlow/XGBoost wheel install). Subsequent starts are < 30 s.

Wait until all services are `healthy` / `running`:
- **Edge:** `api-gateway`, `frontend-svc`
- **Identity & business:** `auth-svc`, `upload-svc`, `inference-svc`, `report-svc`, `celery-worker`
- **ML microservices:** `moe-inference-svc`, `moe-training-svc`, `moe-monitoring-svc`
- **Data plane:** `postgres`, `redis`, `minio`, `mlflow_db`, `monitoring_db`
- **MLOps plane:** `mlflow`, `prometheus`, `grafana`, `node-exporter`, `cadvisor`, `pushgateway`

---

## 2. Pre‑flight smoke test (~3 min)

```bash
# Edge entry
curl -fsS http://localhost:8090/health                   # gateway
curl -fsS http://localhost:3000 > /dev/null && echo OK   # frontend

# ML microservices via gateway (need to login first — see step 3)
curl -fsS http://localhost:5000/health                   # MLflow
curl -fsS http://localhost:9090/-/ready                  # Prometheus
curl -fsS http://localhost:3001/api/health               # Grafana
```

Open these tabs in the browser:
1. http://localhost:3000 → frontend (will redirect to /login)
2. http://localhost:5000 → MLflow
3. http://localhost:9090/targets → Prometheus (all targets should be UP)
4. http://localhost:3001 → Grafana (admin / admin)
5. http://localhost:9091 → Pushgateway (will be empty until first training run)

---

## 3. The jury demo (60 seconds)

### Pre‑seed (do this once, off‑demo, so the front has data to show)
1. Browser → `http://localhost:3000` → login `admin@esprit.tn / Admin123!`
2. Drag `moe-ids/tests/fixtures/sample_5g_10rows.csv` into the drop zone → **Start prediction**
3. Open Swagger at http://localhost:8090/docs → `POST /api/train/start` → run with defaults (3‑5 min — do this once before the jury arrives)

### The walkthrough
**1. "Microservices architecture"** — show `docker compose ps` (18 services on one network).

**2. "Auto-detect code change → CI"**
- Edit any file under `moe-ids/`, push to GitHub.
- Open https://github.com/nawresbensethom/Esprit-PI-4DATA-2026-6G-Network-Anomaly-Detection/actions
- Show the **CI** run firing automatically with 5 jobs: `quality`, `model`, `trivy-fs`, `frontend`, `notify-on-failure`.

**3. "Manual CD pipeline"**
- Actions → **CD** → "Run workflow" → leave defaults → green button.
- Watch the matrix: 9 images build in parallel → push to DockerHub.
- Then `train-and-log` runs and logs to MLflow.
- Then `auto-promote` step transitions the model to **Production** if F1 ≥ 0.90.
- Then `deploy-and-smoke-test` boots the full stack from the pulled images.
- Then `security-scan` matrix runs Trivy on all 9 images.
- Then `notify` posts to Slack.

**4. "Verify the artefacts"**
- DockerHub: open https://hub.docker.com/u/<your-user> → 9 repos with fresh `latest` and `<sha>` tags.
- MLflow tab → experiment `unified_moe_cd` → newest run with logged params, metrics (`moe_f1`, `moe_accuracy`, `moe_auc_roc`, `moe_pr_auc`), and artefacts.
- Front tab → `/upload` → top row of KPI cards shows live **Model accuracy / F1 / ROC AUC / MLflow run** (auto-refresh every 30 s).
- Grafana tab → MoE IDS dashboard → 8 panels in 4 rows:
  - **Inference**: request rate, p95 latency, attack rate, rows processed
  - **Machine**: host CPU%, host RAM free %, host disk free
  - **Containers**: per‑container CPU + RSS
  - **Model**: accuracy, F1, ROC AUC, model age (from Pushgateway)

**5. "Excellence"** (pick one to highlight):
- **Trivy** scans both source code (CI) and pushed images (CD) — SARIF upload to GitHub Security.
- **Auto-promote** — model is gated on F1 ≥ 0.90 before being transitioned to Production stage in MLflow.
- **Hot‑reload after promotion** — `promote.py` calls `/admin/reload` on the inference service so the new model goes live without restart.
- **Slack alerting** — drift detection in the monitoring service posts to Slack when PSI > 0.2.

**Punch line:** *"One push triggers CI; one click triggers CD; one image push goes to DockerHub; one MLflow run is logged with full metrics; the front shows accuracy live; Grafana shows machine + container + model health; Slack tells us if anything breaks."*

---

## 4. Reset between takes

```bash
docker compose down                # stop containers, keep volumes (MLflow history preserved)
docker compose down -v             # nuke volumes (fresh slate)
docker compose up -d               # back up in < 30 s
```

---

## 5. Common gotchas

| Symptom | Fix |
|---|---|
| First CI run red on `format-check` | Run `make -C moe-ids format` once, commit. |
| `model` job fails with "CSV missing" | Check `git ls-files MoE/*.csv` — both files must be tracked. If not, commit them or move them out of `.gitignore`. |
| CD `build-and-push` fails on login | `DOCKERHUB_TOKEN` missing or wrong scope (needs Read + Write). |
| Front shows `—` instead of accuracy | No MLflow run yet OR MLflow unreachable from `moe-inference-svc`. Check `docker compose logs mlflow moe-inference-svc`. Falls back to `baseline_stats.json` if present. |
| Grafana panels empty | No traffic / no training run yet. Run a few `/predict/batch` calls + one training run. Wait 15‑30 s for scrape. |
| `POST /api/train/start` returns 403 | Logged in as analyst/ml_engineer instead of admin. Reload requires admin role. |
| Pushgateway empty | Training was run with `--no-pushgateway` or `PUSHGATEWAY_URL` env not set. Check moe-training-svc env in `docker compose config`. |
| Grafana shows "no data" on machine panels | `cadvisor` / `node-exporter` not on the data network. Verify with `docker compose ps cadvisor node-exporter`. |

---

## 6. Endpoint reference (after Step 4 unification)

All client traffic enters at **`http://localhost:8090`**:

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/health` | GET | — | Gateway liveness |
| `/api/auth/login` | POST | — | JWT issue |
| `/api/predict/batch` | POST | JWT | CSV → predictions |
| `/api/predict/health` | GET | JWT | upstream reachability |
| `/api/predict/metrics` | GET | JWT | latest model metrics from MLflow |
| `/api/train/start` | POST | JWT + **admin** | trigger training run |
| `/api/train/status` | GET | JWT | poll running training |
| `/api/train/reload` | POST | JWT + **admin** | hot‑reload model |
| `/api/drift/run` | POST | JWT + **admin** | execute drift check now |
| `/api/drift/last` | GET | JWT | latest drift report |

Operator UIs are **NOT** behind the gateway (admin direct access):
- MLflow: http://localhost:5000
- Grafana: http://localhost:3001 (admin/admin)
- Prometheus: http://localhost:9090
- Pushgateway: http://localhost:9091
- MinIO console: http://localhost:9001 (minioadmin/minioadmin123)

---

## 7. Pre‑demo checklist (the morning of)

```
☐ git pull on demo machine
☐ cp .env.example .env  (and set INTERNAL_API_KEY)
☐ docker compose up -d
☐ docker compose ps                                       — 18 services healthy/running
☐ Open http://localhost:5000   (MLflow)                   — confirm previous runs visible
☐ Open http://localhost:3001   (Grafana, admin/admin)     — 4 rows visible
☐ Open http://localhost:3000   (frontend)                 — login admin@esprit.tn / Admin123!
☐ Upload sample_5g_10rows.csv → confirm KPI cards populate
☐ Trigger one POST /api/train/start (off‑demo, so MLflow has fresh data)
☐ Open https://hub.docker.com/u/<DOCKERHUB_USER>          — confirm last image push timestamp
☐ Open Actions tab on GitHub                              — confirm last CI run is green
☐ Make a 1‑line code change → push → watch GH Actions     — live evidence
☐ Click "Run workflow" on CD                              — live evidence
```
