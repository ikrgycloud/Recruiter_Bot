import os
from pathlib import Path

from dotenv import load_dotenv


def _load_runtime_env() -> None:
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate, override=False)


_load_runtime_env()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api").rstrip("/")
AGENT_VERSION = os.getenv("AGENT_VERSION", "0.1.0")
DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / "RecruiterAgent"
SESSION_FILE = DATA_DIR / "session.json"
