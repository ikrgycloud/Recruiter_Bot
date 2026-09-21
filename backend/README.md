# Recruiter Automation Backend

FastAPI backend for company registration, authentication, user-owned provider integrations, and recruiting workflows.

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

## Gmail rescheduling workflow

After Google is connected, the backend checks the Gmail inbox in the background. Reschedule requests are classified and appear in **Dashboard → Approval Queue**. With automatic rescheduling disabled, a recruiter reviews each proposed calendar slot and confirms it from that page.

Use **Dashboard → Settings** to choose whether the app suggests available times and to set working days and shift hours. When suggestions are enabled, the app checks the candidate's request and Google Calendar, then puts its suggested free time in the Approval Queue. A recruiter must approve before the meeting moves or a confirmation is sent. When suggestions are disabled, the recruiter chooses a date and time; the app checks calendar availability and the saved working schedule before applying the approved change. Suggestions preserve the meeting duration, use the Google Calendar time zone, try a clearly requested date first, and otherwise propose the next available slot on a selected working day during the configured shift. Ambiguous requests stay in the queue for manual review.

The inbox sync interval is controlled by **GOOGLE_SYNC_INTERVAL_SECONDS** (minimum 30 seconds). The first background sync reads the inbox; later syncs stop when they reach a previously stored message.

## Google token expired or revoked

If Gmail or Calendar access expires, the Integrations page reports **Reconnect required**. Choose **Reconnect Google** and approve the requested Gmail and Calendar permissions with the account you want the application to use. The callback replaces the saved connection, and inbox polling resumes. The backend pauses repeated retries for a rejected connection and logs one reconnect warning instead of printing a traceback on every poll.

For a deployed app, open **Google Auth Platform → Audience** in Google Cloud Console and check the publishing status. An External OAuth app left in **Testing** issues refresh tokens that expire after seven days for Gmail and Calendar scopes. Move the app to **In production** and complete Google's verification requirements for the requested scopes, then reconnect the account. Production status prevents that Testing-mode seven-day expiry; Google can still revoke tokens for other security or account reasons. Keep the OAuth client secret private, and make sure the authorized redirect URI exactly matches **GOOGLE_REDIRECT_URI**. See Google's [refresh-token guidance](https://developers.google.com/identity/protocols/oauth2#expiration) and [OAuth verification requirements](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview).
