# Dashboard — AI-Driven Attack Detection

Microservices dashboard for the 6G Network Anomaly Detection project.

## Quick start

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

Health checks:
- Gateway: http://localhost:8000/health
- Auth: http://localhost:8001/health
- Upload: http://localhost:8002/health
- Inference: http://localhost:8003/health
- Report: http://localhost:8004/health
- Frontend: http://localhost:3000
- MinIO console: http://localhost:9001

## Default admin

On first startup the `auth-svc` seeds a default admin user:
- email: `admin@esprit.tn`
- password: `Admin123!`

Login:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@esprit.tn","password":"Admin123!"}'
```

See `DASHBOARD_BUILD_GUIDE.md` at the repo root for the full plan.
