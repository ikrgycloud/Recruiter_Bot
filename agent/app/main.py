import sys

from app.api_client import ApiClient
from app.autostart import enable_autostart
from app.storage import load_session, save_session
from app.singleton import SingleInstance
from app.storage import clear_session
from app.tray import TrayAgent
from app.ui import AuthWindow


def start_authenticated(session: dict) -> bool:
    save_session(session)
    enable_autostart()
    return TrayAgent(session).start()


def main() -> None:
    instance = SingleInstance()
    if not instance.acquire():
        return
    session = load_session()
    if session and session.get("access_token"):
        if start_authenticated(session):
            return
        clear_session()
    AuthWindow(ApiClient(), start_authenticated).run()


if __name__ == "__main__":
    main()
