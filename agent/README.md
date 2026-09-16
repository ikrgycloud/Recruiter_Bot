# Desktop Agent

The agent is a small desktop client for recruiters. It provides first-run registration/login, starts with the operating system, sends a heartbeat to the backend, and displays a tray icon with running status.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m app.main
```

## Build a Windows executable

```powershell
python -m PyInstaller --noconfirm --clean --windowed --name RecruiterAgent --add-data ".env.example;." app/main.py
```

The backend URL is configured in `.env` or the packaged configuration. The generated executable will launch in the background and register itself on first run using the current system hostname plus the company details entered by the user.
