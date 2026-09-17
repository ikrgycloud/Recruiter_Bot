# Recruiter Automation Platform

Initial workspace for the recruiting automation platform.

## Components

- `backend/`: FastAPI service using PostgreSQL, JWT authentication, company registration, agent registration, and heartbeats.
- `frontend/`: React portal for recruiter/admin registration and login, live database-backed views, and provider integrations.
- `docker-compose.yml`: Three-service local stack: PostgreSQL, backend, and frontend.

## Start the complete application

```powershell
docker compose up -d --build
```

This starts exactly three containers:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- PostgreSQL: host port `5433`

The backend container uses `db:5432` internally. The web application uses `http://localhost:8000/api` by default.

API documentation: `http://localhost:8000/docs`

## Register and connect providers

Open the frontend at `http://localhost:5173`, select **Create an account** on the login page, and complete registration. After signing in, use **Integrations** to connect Gmail, Google Calendar, or Microsoft Outlook.

## Important next step

The current database bootstrap uses `create_all` for development. Before production, add Alembic migrations, production secrets, HTTPS, refresh-token rotation, email verification, and provider-token lifecycle management.
