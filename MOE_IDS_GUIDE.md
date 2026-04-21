# MoE IDS — MLOps Pipeline Guide

A walkthrough of the `moe-ids/` stack for teammates testing it locally.

This is the **productionized** version of the Mixture-of-Experts intrusion detector from `MoE/Moe.ipynb`: same model, wrapped in a FastAPI service with MLflow tracking, Prometheus metrics, Grafana dashboards, and drift detection — all orchestrated with Docker Compose.

---

## 1. What's in the box

Six services run together in `moe-ids/docker-compose.yml`:

| Service | Port | Role |
|---|---|---|
| **api** | 8000 | FastAPI inference + training trigger (Swagger at `/docs`) |
| **mlflow** | 5000 | Experiment tracking UI — every training run is logged here |
| **mlflow_db** | 5433 | PostgreSQL backing store for MLflow |
| **monitoring_db** | 5434 | PostgreSQL — one row per prediction request (for drift analysis) |
| **prometheus** | 9090 | Scrapes `/metrics` from the API every 15s |
| **grafana** | 3001 | Dashboard UI (admin / admin) |

---

## 2. How the pieces fit together

```
         ┌─────────────────────────────────────────────────────────┐
         │                      User / Swagger                      │
         └──────────┬──────────────────────────────┬────────────────┘
                    │                              │
          POST /predict/batch              POST /admin/train
                    │                              │
                    ▼                              ▼
         ┌─────────────────────┐       ┌──────────────────────┐
         │     FastAPI (api)   │       │  scripts/train.py    │
         │ ┌─────────────────┐ │       │  (background task)   │
         │ │  MoEPredictor   │ │       │                      │
         │ │  (5 experts +   │ │       │  • trains experts    │
         │ │   gate network) │ │       │  • fits gate         │
         │ └─────────────────┘ │       │  • saves artefacts   │
         │                     │       │  • logs to MLflow ───┼──┐
         │ exports /metrics    │       └──────────────────────┘  │
         │ writes predictions  │                                  │
         │  to monitoring_db   │                                  │
         └──────┬──────┬───────┘                                  │
                │      │                                           │
                │      └──► monitoring_db (Postgres)               │
                │                 │                                │
                │                 └──► mlops/detect_drift.py       │
                │                      (PSI on feature dists)      │
                ▼                                                  ▼
         prometheus ──scrape──► /metrics              mlflow ◄─── logs
             │                                              │
             ▼                                              ▼
         grafana ──────── dashboard ────────► http://localhost:3001
```

### The model (unchanged from `MoE/Moe.ipynb`)
- **5 experts:** 3 XGBoost slice-experts (eMBB / mMTC / URLLC) + 2 autoencoders (5G proto, 6G proto).
- **Gate network:** small Keras MLP that outputs softmax weights over the 5 experts per row.
- **Output:** final attack probability = weighted sum of expert scores, thresholded via F1-optimal calibration.

### Artefacts directory (`moe-ids/artefacts/production/`)
Everything the API needs to score a row: scalers, expert models, gate weights, calibration params, threshold. Mounted into the API container as `/app/artefacts`.

---

## 3. Prerequisites

- **Docker Desktop** (Windows / macOS / Linux) — the only hard requirement.
- ~8 GB RAM free for the containers.
- The two cleaned CSVs must sit at `MoE/Global_CLEANED.csv` and `MoE/AIoT_6G_CLEANED.csv` (they already do in this repo). The API container mounts `../MoE/` read-only at `/app/data/`.
- The Linux wheel cache at `moe-ids/wheels/` (~744 MB) is already checked in so the Docker build doesn't hit PyPI for tensorflow/xgboost.

**No local Python install needed** — everything runs inside containers.

---

## 4. Run it

```bash
cd moe-ids
docker compose up --build -d
docker compose ps
```

First build takes ~5-10 min (mostly copying wheels). Subsequent starts take <30s.

Wait until all six services are `healthy` / `running`:

```bash
docker compose ps
```

---

## 5. Smoke-test each piece

### 5.1 API health
```bash
curl http://localhost:8000/healthz
# {"status":"ok", "model_loaded": true, ...}
```

### 5.2 Swagger UI
Open `http://localhost:8000/docs` in the browser.

You'll see three sections: **health**, **inference**, **admin**.

### 5.3 Run a prediction
In Swagger → `POST /predict/batch` → **Try it out** → upload one of:
- `moe-ids/tests/fixtures/sample_5g_10rows.csv`
- `moe-ids/tests/fixtures/sample_6g_10rows.csv`

Add header `X-Api-Key: changeme` and click **Execute**. You get back predictions, probabilities, and per-row gate weights.

### 5.4 Trigger a training run from the API
In Swagger → `POST /admin/train` → **Try it out** → **don't change the body** (defaults are correct) → **Execute**.

Response: `202 Accepted` with a message. Training runs in the background (~3-5 min).

Poll status:
```bash
curl -H "X-Api-Key: changeme" http://localhost:8000/admin/train/status
```

### 5.5 MLflow — see the run
Open `http://localhost:5000` → click experiment **unified_moe** → the run appears with logged params, metrics (F1, AUC, AUPRC per expert and overall), and artefacts.

### 5.6 Prometheus — confirm scraping
Open `http://localhost:9090/targets` — `moe_ids_api` should be **UP**.

Query example: `rate(moe_ids_requests_total[1m])`

### 5.7 Grafana — see the dashboard
Open `http://localhost:3001` (login `admin` / `admin`) → **Dashboards** → **MoE IDS**.

The Prometheus datasource and dashboard are **auto-provisioned** — nothing to configure. If panels are empty, it just means no traffic has hit the API yet. Run a few `/predict/batch` calls and they'll populate within ~15s.

### 5.8 Drift detection
After a handful of predictions have been logged to `monitoring_db`:
```bash
docker compose exec api python -m mlops.detect_drift
```
Computes Population Stability Index (PSI) per feature between a reference window and the most recent window. Flags features with PSI > 0.2.

---

## 6. What each endpoint is for

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/healthz` | GET | no | Liveness — used by Docker healthcheck |
| `/metrics` | GET | no | Prometheus scrape endpoint |
| `/predict/batch` | POST | `X-Api-Key` | Score a CSV file (5G Argus or 6G CICFlowMeter schema) |
| `/predict/realtime` | POST | `X-Api-Key` | Score a single JSON row |
| `/admin/train` | POST | `X-Api-Key` | Kick off `scripts/train.py` in the background, logs to MLflow |
| `/admin/train/status` | GET | no | Poll the running training job |
| `/admin/reload` | POST | `X-Api-Key` | Hot-reload artefacts from disk without a restart |

Default API key is `changeme` (set via `API_KEY` env var in compose).

---

## 7. Common problems

| Symptom | Fix |
|---|---|
| `docker compose build api` hangs on pip install | The Linux wheel cache in `moe-ids/wheels/` is missing or incomplete — pull the repo again. |
| MLflow container restarts in a loop | Usually an Alembic schema mismatch from a stale volume. Fix: `docker compose down && docker volume rm moe-ids_mlflow_db_data && docker compose up -d`. |
| Swagger shows `"string"` as the default for paths | Old build cached. Run `docker compose build api && docker compose up -d --force-recreate api`, then hard-refresh browser (Ctrl+Shift+R). |
| `POST /admin/train` returns 400 "Invalid data_5g" | You edited the body and kept Swagger's `"string"` placeholder. Leave the body at its defaults. |
| Grafana dashboard empty | No traffic yet — hit `/predict/batch` a few times. Or Prometheus can't reach the API: check `http://localhost:9090/targets`. |
| Port already in use | Something else is on 8000/5000/3001 — edit the `ports:` in `docker-compose.yml`. |

---

## 8. Shutting down

```bash
cd moe-ids
docker compose down            # stop containers, keep volumes (MLflow history)
docker compose down -v         # also wipe volumes (fresh slate)
```

---

## 9. What to look at in the code

- Model + predictor: [moe-ids/moe_ids/moe.py](moe-ids/moe_ids/moe.py)
- Experts (XGBoost + autoencoder): [moe-ids/moe_ids/experts.py](moe-ids/moe_ids/experts.py)
- Gate network: [moe-ids/moe_ids/gate.py](moe-ids/moe_ids/gate.py)
- Training pipeline: [moe-ids/scripts/train.py](moe-ids/scripts/train.py)
- API routes: [moe-ids/services/api/routes_batch.py](moe-ids/services/api/routes_batch.py), [routes_train.py](moe-ids/services/api/routes_train.py)
- Prometheus metrics definitions: [moe-ids/services/api/metrics.py](moe-ids/services/api/metrics.py)
- Drift detection: [moe-ids/mlops/monitoring/](moe-ids/mlops/monitoring/) and `mlops/detect_drift.py`
- Dashboard JSON: [moe-ids/monitoring/grafana/dashboards/moe_ids.json](moe-ids/monitoring/grafana/dashboards/moe_ids.json)

---

## 10. The 60-second demo script

For a quick walkthrough during the defense:

1. `docker compose up -d` → show `docker compose ps` all green.
2. Open Swagger → upload `sample_5g_10rows.csv` → show JSON response with predictions + gate weights.
3. Hit `POST /admin/train` with defaults → 202.
4. Switch to MLflow tab → show the run being logged live with metrics.
5. Switch to Grafana tab → show request rate + latency + attack-rate panels populating.
6. Back to Swagger → `POST /admin/reload` → point out `moe_ids_model_reloads_total` just ticked in Grafana.

That's the full loop: **request → prediction → metric → dashboard → retrain → reload → metric**.