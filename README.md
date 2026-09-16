# Recruiter Automation Platform

Initial workspace for the recruiting automation platform.

## Components

- `backend/`: FastAPI service using PostgreSQL, JWT authentication, company registration, agent registration, and heartbeats.
- `agent/`: Python desktop agent with first-run registration/login, system startup registration, tray status, and five-second startup notification.
- `frontend/`: React portal for recruiter/admin login and live database-backed views.
- `docker-compose.yml`: Three-service local stack: PostgreSQL, backend, and frontend.

## Start the complete application

```powershell
docker compose up -d --build
```

This starts exactly three containers:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- PostgreSQL: host port `5433`

The backend container uses `db:5432` internally. The desktop agent uses `http://localhost:8000/api` when it runs on the same system.

API documentation: `http://localhost:8000/docs`

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

The first run opens employee registration, then asks you to connect the mailbox for that agent. The agent remains `awaiting_mailbox` until a Gmail account is selected through Google OAuth. After connection, it changes to `running`, sends heartbeats, shows the five-second popup, and registers for auto-start.

## Important next step

The current database bootstrap uses `create_all` for development. Before production, add Alembic migrations, a production secret, HTTPS, refresh-token rotation, email verification, and secure encrypted agent-token storage.
