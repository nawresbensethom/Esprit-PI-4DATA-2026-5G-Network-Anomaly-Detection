# Testing & Setup Guide

Step‑by‑step instructions for the **one‑time setup** (GitHub + DockerHub + local `.env`) and the **end‑to‑end test plan** for every modification made during the unification + microservices refactor.

Companion to:
- [JURY_NEXT_WEEK_PLAN.md](JURY_NEXT_WEEK_PLAN.md) — what was changed and why
- [IMPLEMENTATION_AUDIT.md](IMPLEMENTATION_AUDIT.md) — file‑level change inventory
- [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md) — 60‑second jury walkthrough

---

## Part 1 — One-time setup

You only need to do these once. Total time: ~10 min.

### 1.1 DockerHub account + access token

1. Go to https://hub.docker.com → sign in (or create an account).
2. Click your avatar → **Account Settings** → **Security** → **New Access Token**.
3. Name: `github-actions-cd` · Permissions: **Read, Write, Delete**.
4. Click **Generate** → **copy the token now** (it won't be shown again).
5. (Optional) Pre‑create the 9 image repos under your account:
   `moe-inference` · `moe-training` · `moe-monitoring` · `dashboard-gateway` · `dashboard-auth` · `dashboard-inference` · `dashboard-upload` · `dashboard-report` · `dashboard-frontend`.
   If you skip this, the first CD push will auto-create them as **public**.

### 1.2 GitHub repository secrets

1. Go to https://github.com/nawresbensethom/Esprit-PI-4DATA-2026-6G-Network-Anomaly-Detection/settings/secrets/actions
2. Click **New repository secret** three times:

| Name | Value |
|---|---|
| `DOCKERHUB_USER` | your DockerHub username (e.g. `mouarag`) |
| `DOCKERHUB_TOKEN` | the token from step 1.1 |
| `SLACK_WEBHOOK_URL` | *optional* — your Slack Incoming Webhook (Slack → Apps → Incoming Webhooks → Add → pick channel → copy URL) |

### 1.3 Local `.env`

```bash
cd c:/Esprit-PI-4DATA-2026-6G-Network-Anomaly-Detection
cp .env.example .env
```

Edit `.env` and at minimum change:
- `INTERNAL_API_KEY` — anything other than `changeme` (otherwise auth between gateway and ML services is bypassed)
- `JWT_SECRET` — long random string

### 1.4 Format the codebase once

So the first CI run isn't red on `format-check`:

```bash
docker run --rm -v "$PWD/moe-ids:/work" -w /work python:3.11-slim \
  bash -c "pip install black ruff && black moe_ids/ scripts/ tests/ services/ && ruff check --fix moe_ids/ scripts/ tests/ services/"
```

(Or, if you have Python locally: `cd moe-ids && pip install -e ".[dev]" && make format`.)

Then commit the formatting changes:

```bash
git add -A
git commit -m "chore: black + ruff format"
```

### 1.5 Verify cleaned datasets are tracked

```bash
git ls-files MoE/*.csv
```

Expected output:
```
MoE/AIoT_6G_CLEANED.csv
MoE/Global_CLEANED.csv
```

If either is missing, the CI `model` job will hard-fail. Add them:

```bash
git add MoE/AIoT_6G_CLEANED.csv MoE/Global_CLEANED.csv
git commit -m "chore: track cleaned datasets for CI"
```

---

## Part 2 — Local boot (sanity check)

```bash
cd c:/Esprit-PI-4DATA-2026-6G-Network-Anomaly-Detection
docker compose up --build -d
docker compose ps
```

Wait until all services show `running` (and `healthy` where a healthcheck is defined). First build is slow (~10‑15 min) because of TensorFlow/XGBoost wheels; subsequent boots are < 30 s.

Should see ~18 services across these groups:
- **Edge** — `ids_gateway`, `ids_frontend`
- **Identity & business** — `ids_auth`, `ids_upload`, `ids_inference_proxy`, `ids_report`, `ids_celery`
- **ML microservices** — `moe_inference`, `moe_training`, `moe_monitoring`
- **Data plane** — `ids_postgres`, `ids_redis`, `ids_minio`, `moe_mlflow_db`, `moe_monitoring_db`
- **MLOps plane** — `moe_mlflow`, `moe_prometheus`, `moe_grafana`, `moe_node_exporter`, `moe_cadvisor`, `moe_pushgateway`

If any container is `Restarting` or `Exited`, dump its logs:

```bash
docker compose logs <container-name> --tail=200
```

---

## Part 3 — Test plan (all modifications, in dependency order)

Every test gives you the **command**, the **expected output**, and **how to know it passed**. Skip any test whose subsystem you've already verified.

### 3.1 Microservices split (Step 2)

Tests that the three new ML services are alive and split correctly.

```bash
# Inference service (port 8000)
curl -s http://localhost:8000/healthz | python -m json.tool
# Expected: {"status": "ok", "service": "inference"}

# Training service (port 8010)
curl -s http://localhost:8010/healthz | python -m json.tool
# Expected: {"status": "ok", "service": "training"}

# Monitoring service (port 8011)
curl -s http://localhost:8011/healthz | python -m json.tool
# Expected: {"status": "ok", "service": "monitoring"}

# Each service's /metrics should expose Prometheus-format text
curl -s http://localhost:8000/metrics | head -5
curl -s http://localhost:8010/metrics | head -5
curl -s http://localhost:8011/metrics | head -5
# Expected: # HELP moe_ids_requests_total ...
```

✅ **Pass when:** all three return `{"status":"ok","service":"<name>"}` and `/metrics` returns Prometheus text starting with `# HELP`.

### 3.2 Unified compose + monitoring extensions (Step 3)

```bash
# Prometheus is scraping all 6 jobs
curl -s http://localhost:9090/api/v1/targets | python -m json.tool | grep -E '"job"|"health"'
# Expected: jobs moe_inference, moe_training, moe_monitoring, node, cadvisor, pushgateway — all "health":"up"

# node-exporter is producing host metrics
curl -s http://localhost:9100/metrics | grep node_cpu_seconds_total | head -3
# Expected: node_cpu_seconds_total{cpu="0",mode="idle"} ...

# cadvisor is producing container metrics
curl -s http://localhost:8088/metrics | grep container_cpu_usage_seconds_total | head -3
# Expected: container_cpu_usage_seconds_total{...} ...

# Pushgateway is reachable (will be empty until first training run)
curl -s http://localhost:9091/metrics | head -3
# Expected: any output without 404
```

✅ **Pass when:** Prometheus shows 6 jobs all UP.

### 3.3 Gateway proxies (Step 4)

```bash
# Gateway health
curl -s http://localhost:8090/health | python -m json.tool
# Expected: {"status": "ok", "service": "api-gateway"}

# Login as admin (seeded user)
TOKEN=$(curl -s -X POST http://localhost:8090/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@esprit.tn","password":"Admin123!"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "$TOKEN" | head -c 40

# Check gateway forwards to training service
curl -s http://localhost:8090/api/train/status \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
# Expected: {"running": false, "last_result": null}

# Check gateway forwards to monitoring service
curl -s http://localhost:8090/api/drift/last \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
# Expected: {"status": "no_run_yet"}

# Role gating — drift /run requires admin (logged-in admin should pass)
curl -s -X POST http://localhost:8090/api/drift/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | python -m json.tool
# Expected: 503 or report — proves admin gate passed (would be 403 if non-admin)
```

✅ **Pass when:** all four return JSON (not 404 / 401 / 502).

### 3.4 Frontend rewire + accuracy KPI (Steps 5 + 7)

1. Open http://localhost:3000 in the browser → auto-redirects to `/login`.
2. Login with `admin@esprit.tn / Admin123!`.
3. Land on `/upload` → at the top, **4 KPI cards** should appear:
   - **Model accuracy** — value or `—` if no MLflow run yet
   - **F1**
   - **ROC AUC**
   - **MLflow run** (8-char run ID + experiment name)
4. Open browser DevTools → Network tab → reload page → look for `GET /api/predict/metrics` → returns JSON `{available, source, accuracy, f1, ...}`.
5. Drag `moe-ids/tests/fixtures/sample_5g_10rows.csv` into the dropzone → **Start prediction** → predictions table appears.

✅ **Pass when:** the 4 KPI cards render (even if values are `—`), and the `/api/predict/metrics` request succeeds.

### 3.5 Pushgateway model metrics (Step 6)

Trigger a training run and watch model metrics appear on the Pushgateway.

```bash
# Trigger training via the gateway
curl -s -X POST http://localhost:8090/api/train/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ae_epochs": 3, "gate_epochs": 3, "xgb_n_estimators": 30}' \
  | python -m json.tool
# Expected: {"status": "accepted", "message": "Training started ..."}

# Poll status (training takes ~3-5 min with these reduced epochs)
watch -n 10 'curl -s http://localhost:8090/api/train/status -H "Authorization: Bearer '"$TOKEN"'" | python -m json.tool'
# Wait until "running": false and "last_result.success": true

# After training, model metrics should be on the Pushgateway
curl -s http://localhost:9091/metrics | grep -E 'moe_ids_model_(accuracy|f1|auc)'
# Expected: 5 gauges with non-zero values
```

✅ **Pass when:** pushgateway shows `moe_ids_model_accuracy`, `_f1`, `_auc`, `_pr_auc`, `_run_ts` with values > 0.

### 3.6 Grafana dashboard extensions (Step 6)

1. Open http://localhost:3001 → login `admin / admin`.
2. Left sidebar → **Dashboards** → **MoE IDS — Inference Monitoring**.
3. Should see **8 panels in 4 rows**:
   - **Inference**: Request Rate · P95 Latency · Attack Rate · Rows Processed · Attack vs Benign
   - **Machine metrics (node-exporter)**: Host CPU% · Memory free % · Disk free
   - **Container metrics (cadvisor)**: Container CPU · Container memory RSS
   - **Model quality**: Accuracy · F1 · ROC AUC · Model Age

✅ **Pass when:** all 4 rows render. Inference panels populate after a few `/predict/batch` calls; model panels populate after a training run.

### 3.7 MLflow accuracy logging (Step 6 + 7)

1. Open http://localhost:5000 → click experiment `unified_moe`.
2. Find your run → click into it → **Metrics** tab.
3. Should see — among others — `moe_accuracy`, `moe_f1`, `moe_auc_roc`, `moe_pr_auc`.

After the run is logged, refresh the front upload page — the KPI cards should now show real numbers instead of `—`.

✅ **Pass when:** MLflow shows `moe_accuracy`, and the front KPI cards reflect the same value within 30 s.

### 3.8 Drift detection + Slack alert (Steps 6 + 10)

```bash
# Trigger a drift check after at least one batch prediction has been logged
curl -s -X POST http://localhost:8090/api/drift/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"window_days":7,"psi_threshold":0.2}' | python -m json.tool
# Expected: {"status":"ok"|"drift_detected"|"no_data", "psi_attack_rate":..., ...}

# Read it back
curl -s http://localhost:8090/api/drift/last \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Drift counter on monitoring /metrics
curl -s http://localhost:8011/metrics | grep moe_ids_drift_checks_total
# Expected: moe_ids_drift_checks_total{result="ok"} 1.0  (or "drift_detected")
```

If `SLACK_WEBHOOK_URL` is set in `.env`, a `drift_detected` result also posts an attachment to your Slack channel.

✅ **Pass when:** `/api/drift/run` returns a report and the drift counter increments.

### 3.9 CI pipeline (Step 8)

This requires pushing to GitHub.

```bash
# Make a trivial code change to trigger CI
echo "# CI test" >> moe-ids/README.md
git add moe-ids/README.md
git commit -m "test: trigger CI"
git push
```

Open https://github.com/nawresbensethom/Esprit-PI-4DATA-2026-6G-Network-Anomaly-Detection/actions → newest **CI** run.

✅ **Pass when:** all 5 jobs go green:
- `quality` (lint + format-check + bandit + pip-audit + pytest unit)
- `model` (boots MLflow + smoke training, ~5 min)
- `trivy-fs` (filesystem CVE scan)
- `frontend` (npm install + build)
- `notify-on-failure` (skipped on green — only runs if any job failed)

If `format-check` fails: you forgot to run section 1.4. It's marked `continue-on-error: true` so it warns but won't block.

### 3.10 CD pipeline (Step 9)

Manual trigger only (`workflow_dispatch`).

1. https://github.com/nawresbensethom/Esprit-PI-4DATA-2026-6G-Network-Anomaly-Detection/actions
2. Left sidebar → **CD** → **Run workflow** button → leave inputs default → green button.
3. Wait. The first run takes 30‑40 min (9 TF/XGBoost images to build cold).

✅ **Pass when:** all jobs go green:
- `build-and-push` (matrix × 9 — all images pushed)
- `train-and-log` (MLflow run logged)
- `deploy-and-smoke-test` (stack boots, gateway responds)
- `security-scan` (matrix × 9 Trivy image scans)
- `notify` (Slack message if webhook set, otherwise just succeeds)

**Verify outside the CD run:**
- DockerHub: https://hub.docker.com/u/&lt;your-user&gt; → 9 repos with fresh `latest` and `<sha>` tags + push timestamp from minutes ago.
- MLflow: http://localhost:5000 (after `docker compose up -d` again) → `unified_moe_cd` experiment exists with the new run.
- GitHub Security tab → **Code scanning alerts** → Trivy SARIF reports visible.

### 3.11 Trivy scans (Step 10)

Already covered by 3.9 (`trivy-fs` in CI) and 3.10 (`security-scan` matrix in CD).

Manual local check:

```bash
# Scan the source tree locally
docker run --rm -v "$PWD:/repo" aquasec/trivy:latest fs --severity HIGH,CRITICAL /repo
```

✅ **Pass when:** report prints CVE counts. (Existing CVEs are reported but don't block — the gate is currently `exit-code: 0` in the workflow.)

### 3.12 Auto‑promote on F1 threshold (Step 10)

This fires automatically inside the CD pipeline (3.10) — `train-and-log` runs `scripts/promote.py --latest --to production` after the training run.

To verify the promotion happened:
1. Open MLflow → **Models** tab (left sidebar).
2. Click `unified_moe` → should see version with stage = **Production**.

To test the gate manually (locally):

```bash
# Trigger training that won't hit threshold (very few epochs → low F1)
curl -s -X POST http://localhost:8090/api/train/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ae_epochs":1,"gate_epochs":1,"xgb_n_estimators":5}' | python -m json.tool

# Wait for completion, then try to promote
docker compose exec moe-training-svc python /app/scripts/promote.py \
  --latest --to production \
  --experiment unified_moe \
  --mlflow-tracking-uri http://mlflow:5000
# Expected: "PROMOTION BLOCKED — F1 X.XXXX < required 0.9"
```

✅ **Pass when:** low‑quality run is blocked, and a normal run (5+ epochs) gets promoted to Production.

### 3.13 Slack alerts (Step 10) — optional, only if `SLACK_WEBHOOK_URL` is set

Three trigger points:
1. **Drift detection** → see test 3.8.
2. **CI failure** → break a unit test deliberately and push; expect a red Slack message after the run fails.
3. **CD completion** → every CD run posts a status summary (success or failure).

✅ **Pass when:** at least one Slack message lands in your channel.

---

## Part 4 — Reset / cleanup

```bash
# Stop containers, keep MLflow history + uploaded files
docker compose down

# Wipe everything (volumes too) for a fresh demo
docker compose down -v

# Bring it all back up
docker compose up -d
```

---

## Part 5 — Troubleshooting cheatsheet

| Symptom | Likely cause | Fix |
|---|---|---|
| `docker compose up` errors with "container_name already in use" | Old `moe_*` or `ids_*` containers from before the unification | `docker compose -f moe-ids/docker-compose.yml.old down` and `docker compose -f dashboard/docker-compose.yml.old down` once, then proceed with root compose |
| Gateway `502 Inference service unreachable` | `moe-inference-svc` not started yet, or wrong DNS | `docker compose ps` — wait for moe-inference-svc to be healthy. Check it's on the `edge` network: `docker network inspect ids-platform_edge` |
| Front KPI cards stuck at `—` | No MLflow run yet OR MLflow unreachable from inference | Trigger a training run; check `docker compose logs moe-inference-svc` for httpx errors |
| Grafana machine panels empty | `node-exporter` / `cadvisor` not scraped | `curl http://localhost:9090/api/v1/targets` — both should be `health:"up"` |
| Pushgateway empty after training | Training was started without `PUSHGATEWAY_URL` env or with `--no-pushgateway` | Check `docker compose config moe-training-svc` env block |
| CI `format-check` red on first run | Code wasn't black-formatted | Run section 1.4 |
| CI `model` job: "CSV missing" | Cleaned CSVs not tracked in git | Run section 1.5 |
| CD `build-and-push`: "denied: requested access to the resource is denied" | `DOCKERHUB_TOKEN` missing or wrong scope (needs Write) | Regenerate with full perms in section 1.1, update GitHub secret |
| CD `auto-promote`: "PROMOTION BLOCKED" | F1 below 0.90 (real failure mode of this gate) | Increase epochs in CD inputs, OR temporarily lower `min_f1` in `moe_ids/config.py` |
| Slack messages never arrive | `SLACK_WEBHOOK_URL` not set | Add to GitHub secret + local `.env` (both — runtime + CI use different sources) |

---

## Part 6 — Quick verification (one paste)

If you want a single smoke test that exercises everything in one go after a fresh boot:

```bash
# 1. Health checks
for svc in 8000 8010 8011 8090 5000 9090; do
  echo -n "Port $svc: "
  curl -fsS "http://localhost:$svc/health" -o /dev/null && echo OK || \
  curl -fsS "http://localhost:$svc/healthz" -o /dev/null && echo OK || \
  curl -fsS "http://localhost:$svc/api/v1/status" -o /dev/null && echo OK || \
  echo FAIL
done

# 2. Login + token
TOKEN=$(curl -s -X POST http://localhost:8090/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@esprit.tn","password":"Admin123!"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 3. Predict
curl -s -X POST http://localhost:8090/api/predict/batch \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@moe-ids/tests/fixtures/sample_5g_10rows.csv" \
  | python -c "import sys,json; r=json.load(sys.stdin); print(f'predictions: {sum(r[\"predictions\"])} attacks / {r[\"n_rows\"]} rows')"

# 4. Train (returns immediately)
curl -s -X POST http://localhost:8090/api/train/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ae_epochs":3,"gate_epochs":3,"xgb_n_estimators":30}' | python -m json.tool

# 5. Drift
curl -s -X POST http://localhost:8090/api/drift/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | python -m json.tool

# 6. Model metrics (live from MLflow)
curl -s http://localhost:8090/api/predict/metrics \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

If all 6 commands return JSON (not 4xx/5xx), the unified platform is working end-to-end.
