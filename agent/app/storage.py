import json
from pathlib import Path

from app.config import DATA_DIR, SESSION_FILE


def save_session(session: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(session), encoding="utf-8")


def load_session() -> dict | None:
    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def clear_session() -> None:
    SESSION_FILE.unlink(missing_ok=True)
