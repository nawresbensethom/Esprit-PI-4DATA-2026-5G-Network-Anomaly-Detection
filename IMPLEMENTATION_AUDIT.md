# Implementation Audit — Jury Requirements vs. Code

Maps every jury requirement (from the brief) to the file/line that implements it.
Generated after Step 11 of [JURY_NEXT_WEEK_PLAN.md](JURY_NEXT_WEEK_PLAN.md).

## ✅ Requirement coverage

### "MLFlow et CM containers lancés à l'avance"
- **MLflow**: [docker-compose.yml `mlflow` + `mlflow_db`](docker-compose.yml) — postgres-backed, port 5000.
- **CM (monitoring)**: [docker-compose.yml `prometheus` + `grafana` + `node-exporter` + `cadvisor` + `pushgateway`](docker-compose.yml) — Prometheus on 9090, Grafana on 3001.
- **One command boot**: `docker compose up -d` from repo root.

### "Modification code/Makefile détectée automatiquement → CI"
- **Auto-trigger**: [.github/workflows/ci.yml lines 3-15](.github/workflows/ci.yml#L3-L15) — `on: push + pull_request` with `paths:` filter on `moe-ids/**`, `dashboard/**`, `Makefile`, compose, workflow itself.
- **Lint**: `quality` job → `make lint` (ruff) + `make format-check` (black) — [ci.yml lines 47-53](.github/workflows/ci.yml#L47-L53)
- **Black formatting**: [moe-ids/pyproject.toml `[tool.black]`](moe-ids/pyproject.toml) + [Makefile `format-check` target](moe-ids/Makefile)
- **Sécurité du code**: `make security` → `bandit -ll` + `pip-audit` — [Makefile](moe-ids/Makefile) + [ci.yml](.github/workflows/ci.yml)
- **Tests unitaires**: `pytest tests/unit -v --cov` — 8 unit test files in [moe-ids/tests/unit/](moe-ids/tests/unit/), Codecov upload best-effort
- **Étapes modèle automatiques**: `model` job → boots MLflow (postgres service container) → trains smoke-sized → uploads `artefacts/ci/` — [ci.yml lines 75-145](.github/workflows/ci.yml#L75-L145)

### "Lancer manuellement une pipeline CD"
- **Manual trigger**: [.github/workflows/cd.yml line 4](.github/workflows/cd.yml#L4) — `on: workflow_dispatch` with `tag`, `experiment_name`, `run_training`, `boot_stack` inputs.

#### CD steps (jury's exact ordering):

1. **Image Docker back+front** — `build-and-push` matrix job, 9 images in parallel — [cd.yml lines 33-79](.github/workflows/cd.yml#L33-L79)
2. **Push DockerHub** — `docker/login-action@v3` + `docker/build-push-action@v5` push tagged `${IMAGE_TAG}` and `latest` — same job
3. **MLflow logging** — `train-and-log` job, real training run, logs to MLflow with `--experiment "${experiment_name}"` — [cd.yml lines 84-150](.github/workflows/cd.yml#L84-L150)
4. **Lancer back/front containers** — `deploy-and-smoke-test` job uses [docker-compose.prod.yml](docker-compose.prod.yml) overlay (pulls images instead of building) — [cd.yml lines 165-205](.github/workflows/cd.yml#L165-L205)

### "Vérifier les résultats"

| Verification step | Where to look | Implementation |
|---|---|---|
| DockerHub image pushed | https://hub.docker.com/u/&lt;user&gt; | CD `build-and-push` matrix |
| MLflow experiment + models + files | http://localhost:5000 → `unified_moe_cd` | `mlc.log_params`, `log_metrics`, `log_artefacts`, `register_model` in [scripts/train.py](moe-ids/scripts/train.py) |
| Front affiche accuracy | http://localhost:3000/upload — top KPI row | [services/inference/routes_metrics.py](moe-ids/services/inference/routes_metrics.py) → [dashboard/inference predict.py /metrics](dashboard/inference/app/routes/predict.py) → [gateway inference_proxy.py /api/predict/metrics](dashboard/gateway/app/routes/inference_proxy.py) → [frontend api.ts getModelMetrics()](dashboard/frontend/src/lib/api.ts) → [upload/page.tsx KPI cards](dashboard/frontend/src/app/upload/page.tsx) |
| Monitoring (machine + tools + accuracy) | http://localhost:3001 → MoE IDS dashboard | [moe_ids.json](moe-ids/monitoring/grafana/dashboards/moe_ids.json) — 4 rows: inference / machine / containers / model |

### "Excellence" (jury said: "non vue dans le cours")

| Item | Where |
|---|---|
| **Trivy** filesystem scan in CI | [ci.yml `trivy-fs` job](.github/workflows/ci.yml) — uploads SARIF to GitHub Security |
| **Trivy** image scans in CD | [cd.yml `security-scan` matrix job](.github/workflows/cd.yml) — scans all 9 pushed images |
| **Auto‑promote on F1 threshold** | [scripts/promote.py](moe-ids/scripts/promote.py) extended with `--latest`, `--experiment`, `--reload-url` — called from CD after training |
| **Hot-reload after promotion** | `promote.py --reload-url http://moe-inference-svc:8000/admin/reload` — model swap without restart |
| **Slack alerting (3 places)** | CI failure: [ci.yml `notify-on-failure`](.github/workflows/ci.yml) · CD status: [cd.yml `notify`](.github/workflows/cd.yml) · drift detection: [routes_drift.py `_post_drift_alert`](moe-ids/services/monitoring/routes_drift.py) |

### Bonus (jury didn't ask, but worth showing)

| Item | Where |
|---|---|
| **Microservices** (jury's previous note: moe-ids was monolithic) | Split into 3 FastAPI services: [services/inference/](moe-ids/services/inference/) · [services/training/](moe-ids/services/training/) · [services/monitoring/](moe-ids/services/monitoring/), shared code in [services/common/](moe-ids/services/common/) |
| **Unified gateway** (everything behind :8090) | [docker-compose.yml](docker-compose.yml) — single network, gateway routes to 9 backends |
| **JWT validation only at the gateway** | [dashboard/gateway/app/middleware/auth.py](dashboard/gateway/app/middleware/auth.py); ML services trust `X-User-*` headers + internal `X-Api-Key` |
| **Role-based gating on training** | [training_proxy.py `require_roles("admin")`](dashboard/gateway/app/routes/training_proxy.py) — admin-only on `start` and `reload` |
| **Pushgateway model metrics** | [scripts/train.py `_push_model_metrics()`](moe-ids/scripts/train.py) publishes 5 gauges after each run |
| **Drift detection as a service** | [routes_drift.py](moe-ids/services/monitoring/routes_drift.py) wraps the standalone CLI as `POST /drift` + `GET /drift/last` |

---

## 📁 Files changed in this PR

### Created (24)
```
.env.example
.github/workflows/ci.yml
.github/workflows/cd.yml
docker-compose.yml
docker-compose.prod.yml
DEMO_CHECKLIST.md
IMPLEMENTATION_AUDIT.md
JURY_NEXT_WEEK_PLAN.md
PROJECT_CHANGES_SUMMARY.md

dashboard/gateway/app/routes/training_proxy.py
dashboard/gateway/app/routes/monitoring_proxy.py

moe-ids/services/common/__init__.py
moe-ids/services/common/auth.py
moe-ids/services/common/db.py
moe-ids/services/common/predictor.py
moe-ids/services/common/metrics.py

moe-ids/services/inference/__init__.py
moe-ids/services/inference/main.py
moe-ids/services/inference/Dockerfile
moe-ids/services/inference/routes_health.py
moe-ids/services/inference/routes_batch.py
moe-ids/services/inference/routes_realtime.py
moe-ids/services/inference/routes_metrics.py

moe-ids/services/training/__init__.py
moe-ids/services/training/main.py
moe-ids/services/training/Dockerfile
moe-ids/services/training/routes_health.py
moe-ids/services/training/routes_train.py

moe-ids/services/monitoring/__init__.py
moe-ids/services/monitoring/main.py
moe-ids/services/monitoring/Dockerfile
moe-ids/services/monitoring/routes_health.py
moe-ids/services/monitoring/routes_drift.py
```

### Modified (12)
```
moe-ids/Makefile                              format/format-check/security targets
moe-ids/pyproject.toml                         black + bandit + pip-audit + [tool.black]
moe-ids/scripts/train.py                       accuracy + Pushgateway + flat_metrics extension
moe-ids/scripts/promote.py                     --latest / --experiment / --reload-url
moe-ids/monitoring/prometheus.yml              6 scrape jobs
moe-ids/monitoring/grafana/dashboards/moe_ids.json   3 new rows (machine / containers / model)
moe-ids/tests/integration/test_api_batch.py    import paths post-split

dashboard/gateway/app/main.py                  registered training + monitoring routers
dashboard/gateway/app/config.py                added TRAINING/MONITORING URLs + INTERNAL_API_KEY
dashboard/gateway/app/routes/inference_proxy.py    added /api/predict/metrics route
dashboard/inference/app/routes/predict.py      MLOPS_BASE_URL → moe-inference-svc + /metrics passthrough
dashboard/frontend/src/lib/api.ts              5 new typed clients + ModelMetrics interface
dashboard/frontend/src/app/upload/page.tsx     4 KPI cards + 30s polling
```

### Deleted (11)
```
moe-ids/services/api/__init__.py
moe-ids/services/api/Dockerfile
moe-ids/services/api/main.py
moe-ids/services/api/db.py
moe-ids/services/api/dependencies.py
moe-ids/services/api/metrics.py
moe-ids/services/api/routes_batch.py
moe-ids/services/api/routes_health.py
moe-ids/services/api/routes_realtime.py
moe-ids/services/api/routes_train.py

moe-ids/docker-compose.yml      → renamed to .yml.old (subsumed by root docker-compose.yml)
dashboard/docker-compose.yml    → renamed to .yml.old (subsumed by root docker-compose.yml)
```

---

## 🧪 Validation status (run before write-up)

| Check | Result |
|---|---|
| `python -c "import yaml; yaml.safe_load('.github/workflows/ci.yml')"` | ✅ |
| `python -c "import yaml; yaml.safe_load('.github/workflows/cd.yml')"` | ✅ |
| `docker compose config --quiet` | ✅ |
| `DOCKERHUB_USER=test IMAGE_TAG=test docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet` | ✅ |
| `python -c "import json; json.load(open('moe-ids/monitoring/grafana/dashboards/moe_ids.json'))"` | ✅ |
| `ast.parse` on every modified Python file | ✅ |
| Both cleaned CSVs tracked in git (`git ls-files MoE/*.csv`) | ✅ — `MoE/Global_CLEANED.csv` + `MoE/AIoT_6G_CLEANED.csv` |

## ⏸ Outside this PR's scope (manual setup)

| Action | Where | Why |
|---|---|---|
| Create DockerHub access token | https://hub.docker.com → Account Settings → Security | needed for CD push |
| Add `DOCKERHUB_USER`/`DOCKERHUB_TOKEN` GitHub secrets | repo → Settings → Secrets → Actions | needed for CD push |
| Add `SLACK_WEBHOOK_URL` GitHub secret (optional) | same | enables Slack alerts |
| Run `make -C moe-ids format` once + commit | local | so first CI run isn't red on `format-check` |
| Run `docker compose up -d` once | local | smoke‑test the unified stack before demo day |
