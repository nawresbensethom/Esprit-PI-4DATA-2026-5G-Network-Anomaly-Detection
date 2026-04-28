# Project Changes Summary — Dashboard Integration

A presentation-oriented summary of what changed since the MoE MLOps pipeline (`moe-ids/`) was wired up to the user-facing dashboard (`dashboard/`).

This document is the companion to [MOE_IDS_GUIDE.md](MOE_IDS_GUIDE.md): the guide explains the standalone MLOps backbone; this file explains how that backbone is now consumed by a multi-service analyst console with authentication, file ingestion, and a React UI.

---

## 1. Before vs. after

**Before** — two disconnected deliverables:
- `MoE/Moe.ipynb` → Mixture-of-Experts notebook, runnable only from Jupyter.
- `moe-ids/` → FastAPI + MLflow + Prometheus + Grafana productionization of that model.

Testing the model required hitting Swagger at `localhost:8000/docs` with a raw API key — no users, no history, no UI.

**After** — two stacks, cleanly integrated:
- `moe-ids/` (port **8000**) — the MLOps backbone, unchanged. Still the source of truth for the model, metrics, experiment tracking, drift detection.
- `dashboard/` (ports **3000 / 8090 / …**) — a new microservice stack and Next.js frontend that authenticates users, lets them upload CSVs, forwards requests to `moe-ids` through a JWT-protected gateway, and renders the predictions in a designed UI.

One click in the browser now triggers: **login → upload CSV → gateway → inference-svc → moe-ids → predictions table**.

---

## 2. New architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Browser (Next.js UI on :3000)                     │
│                   /login  →  /upload  →  results table                │
└─────────────────────────────┬────────────────────────────────────────┘
                              │  fetch(NEXT_PUBLIC_API_URL)
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    api-gateway :8090  (FastAPI)                       │
│   • CORS + JWT validation                                             │
│   • /api/auth/*   →  auth-svc :8001                                   │
│   • /api/predict/*→  inference-svc :8003   (adds X-User-Id / Role)    │
└──────┬──────────────────────────────────────────────┬────────────────┘
       │                                              │
       ▼                                              ▼
┌──────────────────┐                      ┌──────────────────────────┐
│  auth-svc :8001  │                      │   inference-svc :8003    │
│ JWT issuance     │                      │   Thin proxy to moe-ids  │
│ bcrypt+Postgres  │                      │   + Prometheus passthru  │
└────────┬─────────┘                      └────────────┬─────────────┘
         │                                             │  X-Api-Key
         ▼                                             ▼
   postgres :5432                         ┌──────────────────────────┐
                                          │   moe-ids/api :8000      │
                                          │ (unchanged MoE pipeline) │
                                          │ mlflow · prometheus ·    │
                                          │ grafana · drift          │
                                          └──────────────────────────┘

  (upload-svc + celery-worker + redis + minio + report-svc scaffolded
   for async job pipeline — Phase B)
```

Two Docker Compose stacks run in parallel. They talk over `host.docker.internal` rather than sharing a network — each stack stays independently deployable.

---

## 3. What's now in the `dashboard/` stack

| Service | Port | Role | Status |
|---|---|---|---|
| **frontend-svc** | 3000 | Next.js 14 / React 18 analyst UI | ✅ live |
| **api-gateway** | 8090 | JWT-protected FastAPI edge router | ✅ live |
| **auth-svc** | 8001 | Email/password + JWT, Postgres-backed | ✅ live |
| **inference-svc** | 8003 | Proxy to `moe-ids` API | ✅ live |
| **upload-svc** | 8002 | Presigned S3 uploads to MinIO | 🟡 scaffolded |
| **report-svc** | 8004 | PDF/CSV export generator | 🟡 scaffolded |
| **celery-worker** | — | Async job runner (uploads → inference) | 🟡 scaffolded |
| **postgres** | 5432 | Users, sessions, prediction history | ✅ live |
| **redis** | 6379 | Celery broker + rate-limit cache | ✅ live |
| **minio** | 9000 / 9001 | S3-compatible object store for uploads/exports | ✅ live |

**Live** = fully wired in the current demo path. **Scaffolded** = container builds and boots, endpoints exist, not yet on the happy path.

---

## 4. The integration seam — how the two stacks talk

The only bridge between `dashboard/` and `moe-ids/` is [dashboard/inference/app/routes/predict.py](dashboard/inference/app/routes/predict.py), a ~40-line thin proxy:

```python
MLOPS_BASE_URL = os.environ.get("MLOPS_BASE_URL", "http://host.docker.internal:8000")
MLOPS_API_KEY  = os.environ.get("MLOPS_API_KEY",  "changeme")

@router.post("/batch")
async def predict_batch(file: UploadFile):
    files   = {"file": (file.filename, await file.read(), "text/csv")}
    headers = {"X-Api-Key": MLOPS_API_KEY}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{MLOPS_BASE_URL}/predict/batch",
                                 files=files, headers=headers)
    return resp.json()
```

**Why this matters for the defense:** the MoE model is untouched. The dashboard is a consumer, not a fork. If we retrain tomorrow via `POST /admin/train` on moe-ids, the dashboard picks up the new model after a `POST /admin/reload` — no rebuild, no redeploy.

---

## 5. Auth flow — what actually happens when a user clicks "Sign in"

```
 1. browser       → POST localhost:8090/api/auth/login  { email, password }
 2. api-gateway   → forwards to auth-svc:8001/auth/login
 3. auth-svc      → bcrypt-verifies password against Postgres users table
                  → issues access_token (JWT, 60 min) + refresh_token (7 days)
 4. api-gateway   → returns { access_token, refresh_token, user } to browser
 5. browser       → stores tokens + user in localStorage, redirects to /upload

 6. /upload page  → POST localhost:8090/api/predict/batch  (Bearer access_token)
 7. api-gateway   → decodes JWT, validates signature & expiry
                  → adds X-User-Id + X-User-Role headers
                  → forwards multipart body to inference-svc:8003
 8. inference-svc → adds X-Api-Key: changeme, forwards to moe-ids:8000
 9. moe-ids       → scores batch, returns predictions + gate weights
10. browser       → renders KPIs + predictions table
```

Every request past step 5 requires a valid JWT. The gateway is the one place that validates it — downstream services trust the `X-User-*` headers.

---

## 6. The UI — designed → shipped

The `design/` mockup (static HTML) is now a real Next.js app under [dashboard/frontend/](dashboard/frontend/):

| Page | Route | Highlights |
|---|---|---|
| **Login** | `/login` | Split hero / form layout, live backend status card, pre-filled admin creds for demo |
| **New scan** | `/upload` | Drag-drop CSV, live scoring state machine (idle → ready → running → done), per-row table with verdict badges + per-expert gate weights, 4 KPI cards |
| **Home** | `/` | Redirects to `/login` |

Built on:
- **Design tokens** (`globals.css`): `oklch()` colors, dark theme via `<html data-theme="dark">`, Inter + JetBrains Mono.
- **Component kit** ([ui.tsx](dashboard/frontend/src/components/ui.tsx)): `Badge`, `Button`, `Panel`, `Kpi`, `Icon`, `Mark` — no external UI library, all ~140 LOC.
- **Typed API client** ([api.ts](dashboard/frontend/src/lib/api.ts)): `login()`, `predictBatch()`, `BatchPrediction` interface, localStorage session.

Pages still to port from the mockup: Dashboard KPIs, History, Drift, Fairness, Model registry, Users, Settings.

---

## 7. Endpoint reference (new)

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/auth/login` | POST | — | Email + password → JWT pair |
| `/api/auth/refresh` | POST | refresh JWT | Rotate access token |
| `/api/auth/me` | GET | Bearer | Current user profile |
| `/api/predict/batch` | POST | Bearer | Upload CSV, get predictions |
| `/api/predict/health` | GET | Bearer | Check inference-svc → moe-ids reachability |
| `/healthz` (per service) | GET | — | Docker liveness probes |

Gateway is at **`http://localhost:8090`** in dev. Frontend at **`http://localhost:3000`**.

---

## 8. Key design decisions

| Decision | Rationale |
|---|---|
| **Two compose stacks, not one** | `moe-ids` must stay shippable standalone for the ML team. The dashboard is an optional consumer. |
| **Gateway-only JWT validation** | Downstream services don't re-validate — they trust `X-User-*` headers the gateway injects. Reduces duplication and latency. |
| **Thin inference proxy (no caching, no DB writes yet)** | Phase A goal was end-to-end demo; heavy lifting (history, drift tagging, fairness per slice) will land in Phase B via `upload-svc` + Celery. |
| **`host.docker.internal` instead of shared network** | Lets either stack restart independently without breaking DNS. |
| **`NEXT_PUBLIC_API_URL` injected at build** | Lets us retarget the gateway (e.g., behind a reverse proxy) without rebuilding the app image manually. |
| **Default admin user seeded on first boot** | `admin@esprit.tn / Admin123!` — one-click demo; production would disable this and use an env-gated migration. |

---

## 9. What broke along the way (and what we learned)

| Problem | Root cause | Fix |
|---|---|---|
| Gateway couldn't start | Port 8000 conflict with `moe-ids` API | Remapped gateway to host **8090** |
| `bind: Only one usage of each socket address` | Port 8080 already used on the host | Host-side port `8090` kept, container-side was the issue (next row) |
| `Empty reply from server` on `curl` | `8090:8080` mapping but uvicorn was listening on **8090** inside the container | Changed compose mapping to `"8090:8090"` to match the Dockerfile's `EXPOSE 8090` |
| `Invoke-WebRequest : paramètre -X introuvable` | PowerShell aliases `curl` to `Invoke-WebRequest` | Use `curl.exe` explicitly, or native `Invoke-RestMethod` |
| Browser `ERR_EMPTY_RESPONSE` on login | Same container/host port mismatch as above | Same fix — `"8090:8090"` |

**Takeaway:** Docker port mappings are `host:container`; they silently swallow mismatches until something talks to the wrong side.

---

## 10. 60-second demo script (dashboard edition)

1. In one terminal: `cd moe-ids && docker compose ps` — six services green.
2. In another: `cd dashboard && docker compose ps` — gateway, auth, inference, frontend, postgres, redis, minio all up.
3. Browser → `http://localhost:3000` → auto-redirect to `/login`.
4. Click **Continue** (pre-filled with `admin@esprit.tn / Admin123!`) → lands on `/upload`.
5. Drag `moe-ids/tests/fixtures/sample_5g_10rows.csv` into the drop zone → **Start prediction**.
6. Show the results table: **Verdict badges**, probabilities, **per-expert gate weights** (dominant expert highlighted in accent color).
7. Open `http://localhost:3001` (Grafana) side-by-side — the request just made shows up on the `moe_ids_requests_total` panel within ~15s.
8. Punch line: **"The model didn't change. The user experience around it did."**

---

## 11. What's next (roadmap)

- **Phase B — Async ingestion:** `upload-svc` + Celery workers for multi-MB files, MinIO-backed storage, Postgres-backed prediction history.
- **Phase C — Live dashboard pages:** History list, Drift panel (reads PSI from `monitoring_db`), Fairness per 5G slice.
- **Phase D — Admin console:** Threshold slider (calls `POST /admin/reload` with new calibration), Train button (triggers `POST /admin/train`), Model registry browser (reads MLflow REST API).

---

## 12. Code pointers (new files worth reading)

- Gateway auth + inference proxies: [dashboard/gateway/app/routes/auth_proxy.py](dashboard/gateway/app/routes/auth_proxy.py), [inference_proxy.py](dashboard/gateway/app/routes/inference_proxy.py)
- Inference-svc → moe-ids bridge: [dashboard/inference/app/routes/predict.py](dashboard/inference/app/routes/predict.py)
- JWT dependency: [dashboard/gateway/app/deps/auth.py](dashboard/gateway/app/deps/auth.py)
- Frontend API client + types: [dashboard/frontend/src/lib/api.ts](dashboard/frontend/src/lib/api.ts)
- Design-token stylesheet: [dashboard/frontend/src/app/globals.css](dashboard/frontend/src/app/globals.css)
- UI primitives: [dashboard/frontend/src/components/ui.tsx](dashboard/frontend/src/components/ui.tsx)
- Pages: [login/page.tsx](dashboard/frontend/src/app/login/page.tsx), [upload/page.tsx](dashboard/frontend/src/app/upload/page.tsx)
- Compose topology: [dashboard/docker-compose.yml](dashboard/docker-compose.yml)