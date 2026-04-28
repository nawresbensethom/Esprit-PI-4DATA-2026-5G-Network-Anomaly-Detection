# Jury Validation — Next Week Action Plan

Gap analysis of the current repo against the jury's MLOps validation requirements, with a concrete to‑do list, file paths, and ready‑to‑drop‑in skeletons.

Companion to [MOE_IDS_GUIDE.md](MOE_IDS_GUIDE.md) and [PROJECT_CHANGES_SUMMARY.md](PROJECT_CHANGES_SUMMARY.md).

---

## 0. TL;DR — what's already there vs. what's missing

| Jury requirement | Status | Where it lives / what's missing |
|---|---|---|
| MLflow container running in advance | ✅ Done | [moe-ids/docker-compose.yml](moe-ids/docker-compose.yml) services `mlflow` + `mlflow_db` |
| "CM" (monitoring) containers running in advance | ⚠️ Need extension | Have **Prometheus + Grafana** (jury already accepted them — keep). Missing host/container metrics + model‑accuracy gauge — see §4 |
| Auto‑detect code/Makefile change → CI (lint, black, security, unit tests) | ❌ Missing | No `.github/workflows/` — must add (§1) |
| Auto‑run model steps (prep, train, create model) on push | ❌ Missing | `scripts/train.py` exists but isn't wired to CI (§1) |
| Manual CD pipeline (build → push DockerHub → log MLflow → run containers) | ❌ Missing | No CD workflow, no DockerHub push, no `workflow_dispatch` (§2) |
| Verification: DockerHub image, MLflow run, front shows accuracy, monitoring metrics | ⚠️ Partial | Front does **not** display accuracy yet; Grafana lacks machine + model‑accuracy panels (§3, §4) |
| Microservices architecture (jury feedback: moe‑ids = monolithic) | ❌ To fix | Split moe‑ids into 3 FastAPI services **and** unify both stacks behind the existing `api-gateway:8090` — one network, one edge (§5) |
| Excellence (extra non‑required item) | ❌ To pick | Pick one from §5 |

Repo: `nawresbensethom/Esprit-PI-4DATA-2026-6G-Network-Anomaly-Detection` (GitHub) — good, jury accepts GitHub Actions as the CI/CD engine.

---

## 1. CI pipeline — auto‑trigger on push (code/Makefile change)

**Target file:** [.github/workflows/ci.yml](.github/workflows/ci.yml) *(does not exist — create)*

Trigger on `push` and `pull_request` so any change to code or `Makefile` fires the pipeline. Two parallel jobs:

### Job A — code quality / security
- `ruff check` (already configured in [moe-ids/pyproject.toml](moe-ids/pyproject.toml))
- `ruff format --check` (use as **black** replacement — ruff's formatter is black‑compatible) **or** add real `black` to dev deps
- `bandit -r moe_ids/ services/` for code security
- `pip-audit` (or `safety check`) for dependency CVEs
- `pytest tests/unit -v --cov=moe_ids` (8 unit test files already present — see [moe-ids/tests/unit/](moe-ids/tests/unit/))

### Job B — model pipeline (data → train → artefacts → MLflow)
- Boot an **MLflow service container** in the GH runner (postgres + mlflow image)
- Run `python scripts/train.py --no-mlflow=false --mlflow-tracking-uri=http://localhost:5000`
- Upload `artefacts/` as a workflow artefact so the CD job can reuse it
- Optionally run `pytest tests/integration` against the trained model

**Skeleton to drop in:**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    paths: ["moe-ids/**", "src/**", "Makefile", "moe-ids/Makefile", ".github/workflows/**"]
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: moe-ids } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: "pip" }
      - run: pip install -e ".[dev,api,mlflow]" bandit pip-audit
      - run: ruff check moe_ids/ scripts/ tests/
      - run: ruff format --check moe_ids/ scripts/ tests/
      - run: bandit -r moe_ids/ services/ -ll
      - run: pip-audit --strict || true   # don't fail build on transitive CVEs
      - run: pytest tests/unit -v --cov=moe_ids --cov-report=xml
      - uses: codecov/codecov-action@v4
        with: { files: moe-ids/coverage.xml }

  model:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: moe-ids } }
    services:
      mlflow_db:
        image: postgres:15-alpine
        env: { POSTGRES_USER: mlflow, POSTGRES_PASSWORD: mlflow, POSTGRES_DB: mlflow }
        ports: ["5433:5432"]
        options: >-
          --health-cmd "pg_isready -U mlflow" --health-interval 5s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev,mlflow]"
      - name: Start MLflow
        run: |
          pip install mlflow psycopg2-binary
          mlflow server --backend-store-uri postgresql://mlflow:mlflow@localhost:5433/mlflow \
                        --host 0.0.0.0 --port 5000 &
          sleep 8
      - name: Train model & log to MLflow
        run: make train
        env:
          MLFLOW_TRACKING_URI: http://localhost:5000
          DATA_5G_PATH: ../MoE/Global_CLEANED.csv
          DATA_6G_PATH: ../MoE/AIoT_6G_CLEANED.csv
      - uses: actions/upload-artifact@v4
        with: { name: artefacts, path: moe-ids/artefacts/production/ }
```

**To‑dos before this works:**
- [ ] Add `black` and `bandit` to `moe-ids/pyproject.toml` `[dev]` extras (or rely on `ruff format`)
- [ ] The two CSVs in `MoE/` are large — confirm they are checked in (LFS?) so the runner has them. If not, `actions/cache` them or move to GH Releases.
- [ ] Add `make train-ci` target that uses smaller sample datasets if the full ones are too large for free runner minutes.

---

## 2. CD pipeline — manual trigger (`workflow_dispatch`)

**Target file:** [.github/workflows/cd.yml](.github/workflows/cd.yml) *(does not exist — create)*

Triggered manually from the GitHub Actions UI ("Run workflow" button). Steps the jury wants, in order:

1. **Build Docker images** (back + front)
2. **Push to DockerHub**
3. **Train + log to MLflow** (so the registry has a fresh run before deploy)
4. **Launch back/front containers** (on the runner — for demo — or via SSH to a target host)

**Skeleton:**

```yaml
# .github/workflows/cd.yml
name: CD

on:
  workflow_dispatch:
    inputs:
      tag:
        description: "Image tag (default: git SHA)"
        required: false

jobs:
  deploy:
    runs-on: ubuntu-latest
    env:
      IMAGE_TAG: ${{ github.event.inputs.tag || github.sha }}
      DOCKERHUB_USER: ${{ secrets.DOCKERHUB_USER }}
    steps:
      - uses: actions/checkout@v4

      - name: Login DockerHub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USER }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      # 1+2  Build & push images
      - uses: docker/setup-buildx-action@v3

      - name: Build/push moe-ids API (back)
        uses: docker/build-push-action@v5
        with:
          context: moe-ids
          file: moe-ids/services/api/Dockerfile
          push: true
          tags: |
            ${{ env.DOCKERHUB_USER }}/moe-ids-api:${{ env.IMAGE_TAG }}
            ${{ env.DOCKERHUB_USER }}/moe-ids-api:latest

      - name: Build/push dashboard frontend
        uses: docker/build-push-action@v5
        with:
          context: dashboard/frontend
          push: true
          tags: |
            ${{ env.DOCKERHUB_USER }}/dashboard-frontend:${{ env.IMAGE_TAG }}
            ${{ env.DOCKERHUB_USER }}/dashboard-frontend:latest

      # (repeat for gateway / auth / inference)

      # 3  Train + log to MLflow on a remote MLflow server
      - name: Trigger training run
        run: |
          pip install -e moe-ids[mlflow]
          python moe-ids/scripts/train.py \
            --mlflow-tracking-uri ${{ secrets.MLFLOW_REMOTE_URI }} \
            --data-5g MoE/Global_CLEANED.csv \
            --data-6g MoE/AIoT_6G_CLEANED.csv

      # 4  Launch containers
      # Option A (in-runner demo): docker compose up -d using the just-pushed images
      # Option B (real deploy):    SSH to a VPS and pull+up there
      - name: Boot stack
        run: |
          docker compose -f moe-ids/docker-compose.yml up -d
          docker compose -f dashboard/docker-compose.yml up -d
```

**Secrets to add in GitHub repo settings → Secrets → Actions:**
- `DOCKERHUB_USER`
- `DOCKERHUB_TOKEN` (DockerHub access token, **not** password)
- `MLFLOW_REMOTE_URI` (only if MLflow runs on a separate VPS, otherwise drop)

**To‑dos:**
- [ ] Create DockerHub repos: `moe-ids-api`, `dashboard-frontend`, `dashboard-gateway`, `dashboard-auth`, `dashboard-inference`
- [ ] Confirm each service has a `Dockerfile` — [dashboard/inference/](dashboard/inference/), [dashboard/gateway/](dashboard/gateway/), [dashboard/auth/](dashboard/auth/), [dashboard/frontend/](dashboard/frontend/) — and that they build on a clean runner without local cache.
- [ ] Add a `docker-compose.prod.yml` that pulls `image:` from DockerHub instead of `build:` for the deploy step.

---

## 3. Frontend — show accuracy (jury verification step)

The jury says: *"Open front interface and test the model to display accuracy."*

Currently the upload page renders verdicts and gate weights (see [dashboard/frontend/src/app/upload/page.tsx](dashboard/frontend/src/app/upload/page.tsx)) but **does not display the model's accuracy** anywhere. Two fixes possible — pick the cheapest:

### Option A (recommended, ~30 min) — pull last MLflow run
Add a small endpoint `inference-svc → moe-ids /admin/metrics` that returns the latest run's `f1`, `accuracy`, `auc` from MLflow's REST API (`GET /api/2.0/mlflow/runs/search`), and surface it as a KPI card on the upload page.

### Option B — add an "Evaluate" button on the front
Upload a labelled CSV → backend computes accuracy on the fly → returns it. Heavier change to the inference proxy.

**To‑dos:**
- [ ] Pick A or B (recommend A)
- [ ] If A: add `routes_metrics.py` to [moe-ids/services/api/](moe-ids/services/api/) and a `<Kpi label="Model accuracy" />` to the front

---

## 4. Monitoring — extend the existing Prometheus + Grafana stack

The jury already validated Prometheus + Grafana in the previous review, so **keep it**. The jury's three required metric families just need to map onto Grafana panels — currently only one of the three is covered.

| Required metric family | Current state | Fix |
|---|---|---|
| **Machine metrics** (CPU, RAM, disk, network) | ❌ Missing | Add `node-exporter` (host) + `cadvisor` (per‑container) to `moe-ids/docker-compose.yml`, scrape from Prometheus |
| **Tool metrics** (request rate, latency, errors) | ✅ Present | Already exposed by `services/api/metrics.py` and visible in [moe_ids.json](moe-ids/monitoring/grafana/dashboards/moe_ids.json) |
| **Model accuracy / F1 / AUC** | ❌ Missing | Add a Prometheus **Pushgateway**; have `scripts/train.py` push final metrics at the end of each run |

### 4.1 Add `node-exporter` + `cadvisor` + `pushgateway`

Append to [moe-ids/docker-compose.yml](moe-ids/docker-compose.yml):

```yaml
  node-exporter:
    image: prom/node-exporter:v1.7.0
    container_name: moe_node_exporter
    pid: host
    volumes:
      - /:/host:ro,rslave
    command: ["--path.rootfs=/host"]
    ports: ["9100:9100"]
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.49.1
    container_name: moe_cadvisor
    privileged: true
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    ports: ["8088:8080"]
    restart: unless-stopped

  pushgateway:
    image: prom/pushgateway:v1.7.0
    container_name: moe_pushgateway
    ports: ["9091:9091"]
    restart: unless-stopped
```

Then update [moe-ids/monitoring/prometheus.yml](moe-ids/monitoring/prometheus.yml) to scrape them:

```yaml
scrape_configs:
  - job_name: moe_ids_api
    static_configs: [{ targets: ["api:8000"] }]
  - job_name: node
    static_configs: [{ targets: ["node-exporter:9100"] }]
  - job_name: cadvisor
    static_configs: [{ targets: ["cadvisor:8080"] }]
  - job_name: pushgateway
    honor_labels: true
    static_configs: [{ targets: ["pushgateway:9091"] }]
```

### 4.2 Push model metrics from `train.py`

At the end of [moe-ids/scripts/train.py](moe-ids/scripts/train.py), after MLflow logging, add ~10 lines:

```python
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

reg = CollectorRegistry()
Gauge("moe_ids_model_accuracy", "Last training accuracy", registry=reg).set(metrics["accuracy"])
Gauge("moe_ids_model_f1",       "Last training F1",       registry=reg).set(metrics["f1"])
Gauge("moe_ids_model_auc",      "Last training AUC",      registry=reg).set(metrics["auc"])
Gauge("moe_ids_model_run_ts",   "Unix ts of last run",    registry=reg).set(time.time())
push_to_gateway(os.getenv("PUSHGATEWAY_URL", "http://pushgateway:9091"), job="moe_ids_train", registry=reg)
```

(`prometheus-client` is already in the `[api]` extra — also add it to `[mlflow]` or a new `[train]` extra.)

### 4.3 Extend the Grafana dashboard

Edit [moe-ids/monitoring/grafana/dashboards/moe_ids.json](moe-ids/monitoring/grafana/dashboards/moe_ids.json) to add three new rows:

| Row | Panels (PromQL) |
|---|---|
| **Machine** | `100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)` (CPU%), `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100` (free RAM%), `node_filesystem_avail_bytes{mountpoint="/host"}` (disk) |
| **Containers** | `rate(container_cpu_usage_seconds_total{name=~"moe_.*"}[1m])`, `container_memory_usage_bytes{name=~"moe_.*"}` |
| **Model accuracy** | `moe_ids_model_accuracy`, `moe_ids_model_f1`, `moe_ids_model_auc`, single‑stat with `time() - moe_ids_model_run_ts` for "model age" |

After you save the JSON and `docker compose restart grafana`, the dashboard auto‑provisions — no manual import.

**To‑dos:**
- [ ] Append the three services to `moe-ids/docker-compose.yml`
- [ ] Update `prometheus.yml` with the three new jobs
- [ ] Add `prometheus_client` import + push block to `scripts/train.py`
- [ ] Add three rows to `moe_ids.json` (or create a second dashboard `machine_and_model.json` and let Grafana auto‑load it)

---

## 5. Microservices refactor + unified gateway — answering the jury's "moe‑ids is monolithic" note

Goal: split moe‑ids into three ML microservices AND make every client request go through the **single `api-gateway:8090` edge**. No more two isolated stacks talking via `host.docker.internal` — one logical system, one entry point, JWT everywhere.

### 5.1 What the jury actually saw

[moe-ids/services/api/](moe-ids/services/api/) is **one FastAPI process** (`main.py`) that mounts four route modules in the same container:

| Route module | Concern |
|---|---|
| [routes_health.py](moe-ids/services/api/routes_health.py) | liveness |
| [routes_batch.py](moe-ids/services/api/routes_batch.py) | inference (CSV upload) |
| [routes_realtime.py](moe-ids/services/api/routes_realtime.py) | inference (single JSON row) |
| [routes_train.py](moe-ids/services/api/routes_train.py) | training trigger + reload + status |

Plus the two stacks are **physically separate**: `dashboard/` and `moe-ids/` each run their own `docker compose`, bridged only by `host.docker.internal` (see [dashboard/inference/app/routes/predict.py](dashboard/inference/app/routes/predict.py)). From the jury's point of view that looks like two siloed monoliths stitched together, not a microservices system.

### 5.2 Target architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      Browser (Next.js UI on :3000)                    │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │  every request goes here
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     api-gateway :8090  (FastAPI)                      │
│   CORS · JWT validation · inject X-User-Id / X-User-Role              │
│                                                                        │
│   /api/auth/*       → auth-svc          :8001                          │
│   /api/upload/*     → upload-svc        :8002                          │
│   /api/predict/*    → moe-inference-svc :8000                          │
│   /api/train/*      → moe-training-svc  :8010                          │
│   /api/drift/*      → moe-monitoring-svc:8011                          │
│   /api/report/*     → report-svc        :8004                          │
│   /api/mlflow/*     → mlflow            :5000  (read-only proxy)       │
│   /api/grafana/*    → grafana           :3000  (read-only proxy)       │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬─────────────────┘
   │      │      │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼
 auth  upload inference training drift report mlflow grafana
       │                                    │
       ▼                                    ▼
    minio + redis                    prometheus  ← scrapes everything
                                            ▲
                                            │
                                    node-exporter · cadvisor · pushgateway
                                    (shared monitoring plane from §4)
```

**One Docker network, one compose file, one edge.** The browser only ever talks to `:8090`; nothing else is exposed outside the network except `:3000` (front) and the operator dashboards (`:5000` MLflow, `:3001` Grafana) which remain accessible for direct admin use.

### 5.3 Split moe‑ids into three services

Same `moe_ids/` Python package, three thin FastAPI wrappers, each with its own `Dockerfile`:

| New service | Port | Routes (unprefixed) | Why split |
|---|---|---|---|
| **`moe-inference-svc`** | 8000 | `/healthz`, `/metrics`, `/predict/batch`, `/predict/realtime`, `/admin/reload` | Hot path — light, horizontally scalable |
| **`moe-training-svc`** | 8010 | `/admin/train`, `/admin/train/status`, `/healthz`, `/metrics` | Heavy (TF + XGBoost) — own image, own scaling |
| **`moe-monitoring-svc`** | 8011 | `/drift`, `/drift/last`, `/healthz`, `/metrics` | Wraps `mlops/detect_drift.py`, runs on its own schedule |

All three:
- Mount the same `artefacts/` volume (training writes, inference reads after `/admin/reload`)
- Share the `monitoring_db` Postgres
- Share MLflow as the model registry — that's the seam between them, not in‑process calls

```
moe-ids/
├── services/
│   ├── inference/         ← was services/api/, minus routes_train.py
│   │   ├── Dockerfile
│   │   └── main.py
│   ├── training/          ← NEW
│   │   ├── Dockerfile
│   │   └── main.py
│   └── monitoring/        ← NEW
│       ├── Dockerfile
│       └── main.py
```

Mostly mechanical: split [services/api/main.py](moe-ids/services/api/main.py) three ways, copy the existing Dockerfile, add three `services:` blocks to the unified compose file.

### 5.4 Merge the two compose files into one

Replace the two separate `docker-compose.yml` files with a **single root [docker-compose.yml](docker-compose.yml)** so every service joins the same network and the gateway can resolve `moe-inference-svc` / `moe-training-svc` / `moe-monitoring-svc` by DNS (no more `host.docker.internal`).

```yaml
# /docker-compose.yml  (repo root — NEW)
name: ids-platform

networks:
  edge:           # everything the gateway can reach
  data:           # postgres/redis/minio — not exposed to gateway directly

services:
  # ── Edge ─────────────────────────────────────────────────────────────
  api-gateway:
    build: ./dashboard/gateway
    ports: ["8090:8090"]
    environment:
      AUTH_SERVICE_URL:       http://auth-svc:8001
      UPLOAD_SERVICE_URL:     http://upload-svc:8002
      INFERENCE_SERVICE_URL:  http://moe-inference-svc:8000
      TRAINING_SERVICE_URL:   http://moe-training-svc:8010
      MONITORING_SERVICE_URL: http://moe-monitoring-svc:8011
      REPORT_SERVICE_URL:     http://report-svc:8004
      MLFLOW_URL:             http://mlflow:5000
      GRAFANA_URL:            http://grafana:3000
      JWT_SECRET: ${JWT_SECRET:-supersecretkey}
      FRONTEND_ORIGIN: http://localhost:3000
    networks: [edge]

  frontend-svc:
    build: ./dashboard/frontend
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8090
    networks: [edge]

  # ── Identity & user-facing services ─────────────────────────────────
  auth-svc:      { build: ./dashboard/auth,   networks: [edge, data], depends_on: [postgres] }
  upload-svc:    { build: ./dashboard/upload, networks: [edge, data], depends_on: [postgres, redis, minio] }
  report-svc:    { build: ./dashboard/report, networks: [edge, data], depends_on: [postgres, minio] }
  celery-worker: { build: { context: ./dashboard/upload, dockerfile: Dockerfile.worker }, networks: [data] }

  # ── ML microservices (split moe-ids) ────────────────────────────────
  moe-inference-svc:
    build: { context: ./moe-ids, dockerfile: services/inference/Dockerfile }
    environment:
      ARTEFACTS_DIR: /app/artefacts/production
      MONITORING_DB_URL: postgresql://moe:moe@monitoring_db:5432/moe_monitoring
      API_KEY: ${INTERNAL_API_KEY:-changeme}   # now internal only — gateway adds it
    volumes: [ ./moe-ids/artefacts:/app/artefacts:ro, ./MoE:/app/data:ro ]
    networks: [edge, data]
    depends_on: [monitoring_db]

  moe-training-svc:
    build: { context: ./moe-ids, dockerfile: services/training/Dockerfile }
    environment:
      MLFLOW_TRACKING_URI: http://mlflow:5000
      PUSHGATEWAY_URL:    http://pushgateway:9091
    volumes: [ ./moe-ids/artefacts:/app/artefacts, ./MoE:/app/data:ro ]
    networks: [edge, data]
    depends_on: [mlflow, pushgateway]

  moe-monitoring-svc:
    build: { context: ./moe-ids, dockerfile: services/monitoring/Dockerfile }
    environment:
      MONITORING_DB_URL: postgresql://moe:moe@monitoring_db:5432/moe_monitoring
    networks: [edge, data]
    depends_on: [monitoring_db]

  # ── Data plane ──────────────────────────────────────────────────────
  postgres:      { image: postgres:16-alpine, networks: [data], … }
  redis:         { image: redis:7-alpine,     networks: [data] }
  minio:         { image: minio/minio:latest, networks: [data], … }
  monitoring_db: { image: postgres:15-alpine, networks: [data], … }
  mlflow_db:     { image: postgres:15-alpine, networks: [data], … }

  # ── MLOps / observability plane ─────────────────────────────────────
  mlflow:        { image: ghcr.io/mlflow/mlflow:v2.21.3, networks: [edge, data], depends_on: [mlflow_db] }
  prometheus:    { image: prom/prometheus:v2.50.1,       networks: [edge, data] }
  grafana:       { image: grafana/grafana:10.3.3,        networks: [edge], depends_on: [prometheus] }
  node-exporter: { image: prom/node-exporter:v1.7.0,     networks: [data] }
  cadvisor:      { image: gcr.io/cadvisor/cadvisor,      networks: [data] }
  pushgateway:   { image: prom/pushgateway:v1.7.0,       networks: [data] }
```

Total: ~18 services, all on one network, one `docker compose up -d` away from running.

### 5.5 Gateway routing changes

The existing gateway only knows three upstreams (`auth`, `upload`, `inference`). Add two new proxy modules:

**`dashboard/gateway/app/routes/training_proxy.py`** — mirror of [inference_proxy.py](dashboard/gateway/app/routes/inference_proxy.py):
- `POST /api/train/start` → `moe-training-svc:8010/admin/train` (JWT‑required, role=admin)
- `GET  /api/train/status` → `moe-training-svc:8010/admin/train/status`
- `POST /api/train/reload` → `moe-inference-svc:8000/admin/reload` (yes, reload is on inference — it's the service holding the model in memory)

**`dashboard/gateway/app/routes/monitoring_proxy.py`**:
- `GET  /api/drift/last` → `moe-monitoring-svc:8011/drift/last`
- `POST /api/drift/run`  → `moe-monitoring-svc:8011/drift`

Register both in `dashboard/gateway/app/main.py`. Reuse the existing JWT dep from [dashboard/gateway/app/deps/auth.py](dashboard/gateway/app/deps/auth.py) so only logged‑in admins can hit `/api/train/*` — a security win the monolith didn't have.

### 5.6 Retire or keep `dashboard/inference-svc`?

Today it's a **pure pass‑through** to moe‑ids (see [dashboard/inference/app/routes/predict.py](dashboard/inference/app/routes/predict.py)) — ~40 lines. Two options:

- **Retire it** (simpler): gateway talks directly to `moe-inference-svc`. Lose one hop, lose one service to keep alive.
- **Keep it as a business layer** (recommended): gateway → `dashboard/inference-svc` → `moe-inference-svc`. This is where prediction history gets written to the dashboard Postgres, per‑user rate limits live, and audit logging happens. Keeps ML concerns (`moe-inference-svc`) separate from product concerns (history / quotas / analytics).

If kept, point `INFERENCE_SERVICE_URL` in the gateway at `http://inference-svc:8003` and set `MLOPS_BASE_URL=http://moe-inference-svc:8000` inside that service — no more `host.docker.internal`.

### 5.7 Auth flow after the unification

Same as today ([PROJECT_CHANGES_SUMMARY.md §5](PROJECT_CHANGES_SUMMARY.md)) but now covers **every** service:

```
 browser → POST :8090/api/auth/login                          → auth-svc
 browser → POST :8090/api/predict/batch  (Bearer JWT)         → gateway validates → moe-inference-svc (X-User-Id injected)
 browser → POST :8090/api/train/start    (Bearer JWT, admin)  → gateway validates role → moe-training-svc
 browser → GET  :8090/api/drift/last     (Bearer JWT)         → gateway → moe-monitoring-svc
 operator → GET :8090/api/mlflow/...     (Bearer JWT, admin)  → gateway → mlflow   (read-only proxy)
```

Moe‑ids services drop the `X-Api-Key` middleware entirely — the network boundary is the gateway, nothing else is reachable from outside. (Keep the key as a belt‑and‑braces internal auth between gateway and services.)

### 5.8 Frontend change

One‑line change in [dashboard/frontend/src/lib/api.ts](dashboard/frontend/src/lib/api.ts): the existing `NEXT_PUBLIC_API_URL=http://localhost:8090` already points at the gateway. Add typed clients for the new endpoints:

```ts
export const trainStart  = () => post("/api/train/start",  {});
export const trainStatus = () => get ("/api/train/status");
export const driftLast   = () => get ("/api/drift/last");
```

Wire them to the admin console pages listed in Phase D of [PROJECT_CHANGES_SUMMARY.md §11](PROJECT_CHANGES_SUMMARY.md).

### 5.9 Effort revised

| Sub‑task | Time |
|---|---|
| Split `services/api/main.py` → 3 FastAPI apps + 3 Dockerfiles | 2.5h |
| Write root `docker-compose.yml` merging both stacks, one network | 1.5h |
| Add `training_proxy.py` + `monitoring_proxy.py` to gateway | 1.5h |
| Rewire `dashboard/inference-svc` to `http://moe-inference-svc:8000` (drop `host.docker.internal`) | 15 min |
| Frontend: 3 new API client functions | 30 min |
| End‑to‑end smoke test + fix port collisions | 1h |
| **Total** | **~7h** |

Heavier than the previous estimate but delivers *both* deliverables at once: microservices split **and** unified gateway routing.

---

## 6. Excellence — pick **one** (do it well, don't spread thin)

| Idea | Effort | Wow factor | Notes |
|---|---|---|---|
| **Replace Makefile with `dvc` + `dvc repro`** for data/model orchestration | Medium | High — direct match to "data automation + replace Makefile" | Versions data, caches stages, integrates with MLflow |
| **Auto‑promote MLflow model to `Production` when F1 ≥ threshold** + auto `POST /admin/reload` | Low | Medium | `scripts/promote.py` already exists — just wire it into CI |
| **Slack/Discord alerting on CI/CD failure + drift** | Low | Medium | One webhook secret + one PSI threshold check |
| **Trivy + Hadolint security scan on Docker images** in CI | Low | High (matches "tools security check") | One extra GH Actions job |
| **Pre‑commit hooks** (ruff, black, bandit, secret detection) | Very low | Low–Medium | `.pre-commit-config.yaml` + `pre-commit install` |
| **Replace Makefile with [Taskfile](https://taskfile.dev/)** | Low | Medium | Cleaner YAML syntax than Make, cross‑platform |
| **Canary deploy via Traefik** (route 10% of traffic to new model) | High | Very high | Probably too much for one week |


**Recommendation:** combine two cheap wins — **Trivy security scan in CI** + **auto‑promote on F1 threshold + Slack alert**. Total ~3 hours, hits three jury bullets.

---

## 7. Pre‑demo checklist (the morning of)

```
☐ git pull on demo machine
☐ docker compose up -d                                # ONE command — all 18 services from the root compose (§5.4)
☐ docker compose ps                                   # confirm all services healthy
☐ Open http://localhost:5000   (MLflow)         — confirm previous runs visible
☐ Open http://localhost:3001   (Grafana)        — confirm 3 rows: machine / containers / model accuracy
☐ curl http://localhost:8090/api/predict/health       — gateway → moe-inference-svc reachable
☐ curl http://localhost:8090/api/train/status         — gateway → moe-training-svc reachable
☐ curl http://localhost:8090/api/drift/last           — gateway → moe-monitoring-svc reachable
☐ Open http://localhost:3000   (front)          — login admin@esprit.tn / Admin123!
☐ Open https://hub.docker.com/u/<DOCKERHUB_USER> — confirm last image push timestamp
☐ Make a 1-line code change → push → watch GH Actions run live
☐ Click "Run workflow" on CD → watch image push → watch container reload
☐ Upload sample CSV in front → confirm predictions + accuracy KPI
☐ Refresh Kibana → confirm new log lines + metricbeat data
```

---

## 8. Priority order (1 week, in working hours)

| # | Task | Time est. | Blocking? |
|---|---|---|---|
| 1 | Create `.github/workflows/ci.yml` (§1) | 2h | Blocks demo step "auto detection" |
| 2 | Add `black` / `bandit` / `pip-audit` to dev deps (§1) | 30 min | Blocks ci.yml |
| 3 | Create DockerHub repos + add secrets (§2) | 30 min | Blocks cd.yml |
| 4 | Create `.github/workflows/cd.yml` (§2) | 3h | Blocks demo step "push to DockerHub" |
| 5 | Add accuracy KPI to front (§3) | 1h | Blocks demo step "front shows accuracy" |
| 6 | Add `node-exporter` + `cadvisor` + `pushgateway` to compose, update prometheus.yml (§4.1) | 1h | Blocks "machine metrics" panel |
| 7 | Push model metrics from `train.py` (§4.2) | 30 min | Blocks "model accuracy" panel |
| 8 | Extend Grafana dashboard with 3 new rows (§4.3) | 1.5h | Blocks demo step "monitoring metrics" |
| 9 | Split moe‑ids into `inference` / `training` / `monitoring` services (§5.3) | 2.5h | Answers jury's "monolithic" feedback |
| 10 | Merge both stacks into a single root `docker-compose.yml` with one network (§5.4) | 1.5h | Needed so the gateway can resolve moe‑ids services by DNS |
| 11 | Add `training_proxy.py` + `monitoring_proxy.py` to the gateway (§5.5) | 1.5h | Unifies everything behind `:8090` |
| 12 | Rewire `dashboard/inference-svc` + frontend API client (§5.6, §5.8) | 45 min | Kills `host.docker.internal`, adds train/drift buttons |
| 13 | Excellence item — Trivy + auto‑promote + Slack (§6) | 3h | Optional but expected |
| 14 | Dry‑run full demo end‑to‑end on a clean machine | 2h | Catches last‑minute breakage |

**Total: ~22h** — still fits one week. The microservices refactor (items 9‑12) is the biggest net‑new scope but yields a single unified system the jury can inspect in one `docker compose ps`.

---

## 9. Files to create (recap)

```
/                                       ← repo root
├── docker-compose.yml                  ← §5.4 NEW unified stack (replaces the two separate ones)
├── docker-compose.prod.yml             ← §2 pulls images from DockerHub instead of build
└── .github/workflows/
    ├── ci.yml                          ← §1
    └── cd.yml                          ← §2

moe-ids/
├── services/
│   ├── inference/                      ← §5.3 (was services/api/, routes_train.py removed)
│   │   ├── Dockerfile
│   │   └── main.py
│   ├── training/                       ← §5.3 NEW
│   │   ├── Dockerfile
│   │   └── main.py
│   └── monitoring/                     ← §5.3 NEW
│       ├── Dockerfile
│       └── main.py
└── services/inference/routes_metrics.py ← §3 (accuracy KPI endpoint)

dashboard/gateway/app/routes/
├── training_proxy.py                   ← §5.5 NEW
└── monitoring_proxy.py                 ← §5.5 NEW

.pre-commit-config.yaml                 ← §6 (excellence, optional)
```

## 10. Files to edit

- [moe-ids/pyproject.toml](moe-ids/pyproject.toml) — add `black`, `bandit`, `pip-audit` to `[dev]`
- [moe-ids/Makefile](moe-ids/Makefile) — add `format`, `security`, `train-ci` targets
- [moe-ids/monitoring/prometheus.yml](moe-ids/monitoring/prometheus.yml) — add scrape jobs for `node-exporter`, `cadvisor`, `pushgateway`, **plus** the three split services `moe-inference-svc:8000`, `moe-training-svc:8010`, `moe-monitoring-svc:8011` (§4.1 + §5.3)
- [moe-ids/monitoring/grafana/dashboards/moe_ids.json](moe-ids/monitoring/grafana/dashboards/moe_ids.json) — add 3 panel rows (§4.3)
- [moe-ids/scripts/train.py](moe-ids/scripts/train.py) — push final metrics to Pushgateway (§4.2)
- [moe-ids/services/api/main.py](moe-ids/services/api/main.py) — **delete** after splitting into the 3 new services (§5.3)
- [moe-ids/docker-compose.yml](moe-ids/docker-compose.yml) — **delete** once the root `docker-compose.yml` (§5.4) subsumes it
- [dashboard/docker-compose.yml](dashboard/docker-compose.yml) — **delete** once the root `docker-compose.yml` subsumes it (§5.4)
- [dashboard/gateway/app/main.py](dashboard/gateway/app/main.py) — register `training_proxy` + `monitoring_proxy` routers (§5.5)
- [dashboard/inference/app/routes/predict.py](dashboard/inference/app/routes/predict.py) — change `MLOPS_BASE_URL` default from `host.docker.internal:8000` to `http://moe-inference-svc:8000` (§5.6)
- [dashboard/frontend/src/lib/api.ts](dashboard/frontend/src/lib/api.ts) — add `trainStart`, `trainStatus`, `driftLast` clients (§5.8)
- [dashboard/frontend/src/app/upload/page.tsx](dashboard/frontend/src/app/upload/page.tsx) — add Accuracy KPI card (§3)
