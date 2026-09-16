# Recruiter Automation Backend

FastAPI backend for company registration, authentication, agent heartbeats, and future recruiting workflows.

## Run locally

```powershell
docker compose up -d db
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API documentation is available at `http://localhost:8000/docs`.

The initial implementation creates tables on startup for local development. Add Alembic migrations before production deployment.
