# Recruiter Automation Platform

Initial workspace for the recruiting automation platform.

## Components

- `backend/`: FastAPI service using PostgreSQL, JWT authentication, company registration, agent registration, and heartbeats.
- `agent/`: Python desktop agent with first-run registration/login, system startup registration, tray status, and five-second startup notification.
- `docker-compose.yml`: Local PostgreSQL 16 database.

## Start the backend

```powershell
docker compose up -d db
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Start the agent

In another terminal:

```powershell
cd agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

The first run opens a registration form for company email, company name, and company details only. The system hostname is used as the employee/system identity, and the app then saves that session and starts directly in the tray on later runs. The agent also shows a 5-second startup popup and is registered to auto-start on the device.

## Important next step

The current database bootstrap uses `create_all` for development. Before production, add Alembic migrations, a production secret, HTTPS, refresh-token rotation, email verification, and secure encrypted agent-token storage.
