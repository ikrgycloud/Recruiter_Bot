import threading
import time

from PIL import Image, ImageDraw
import pystray

from app.api_client import ApiClient, ApiError
from app.autostart import enable_autostart
from app.config import AGENT_VERSION
from app.storage import save_session
from app.ui import connect_mailbox, show_started_message


class TrayAgent:
    def __init__(self, session: dict):
        self.session = session
        self.client = ApiClient(session["access_token"])
        self.agent_id = session.get("agent_id")
        self.status = "Starting"
        self.running = True
        self.icon = pystray.Icon("RecruiterAgent", self._image(), "Recruiter Agent", self._menu())

    def _image(self) -> Image.Image:
        image = Image.new("RGB", (64, 64), "#2563eb")
        ImageDraw.Draw(image).ellipse((17, 17, 47, 47), fill="#ffffff")
        return image

    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem(lambda _: f"Status: {self.status}", None, enabled=False),
            pystray.MenuItem("Start with system", lambda _icon, _item: enable_autostart(), checked=lambda _item: True),
            pystray.MenuItem("Exit", lambda _icon, _item: self.stop()),
        )

    def _register_agent(self) -> None:
        registered = self.client.register_agent()
        self.agent_id = registered["id"]
        self.session["agent_id"] = self.agent_id
        save_session(self.session)

    def start(self) -> bool:
        try:
            if not self.agent_id:
                self._register_agent()
            agent_state = self.client.agent_status(self.agent_id)
            self.session["agent_id"] = self.agent_id
            self.session["mailbox_email"] = agent_state.get("mailbox_email")
            self.session["mailbox_connected"] = agent_state.get("mailbox_connected", False)
            save_session(self.session)
            if not agent_state.get("mailbox_connected"):
                connect_mailbox(self.client, self.agent_id)
                agent_state = self.client.agent_status(self.agent_id)
            try:
                self.client.heartbeat(self.agent_id)
            except ApiError as error:
                if error.status_code == 404:
                    self._register_agent()
                    self.client.heartbeat(self.agent_id)
                else:
                    raise
            self.status = "Running"
            show_started_message()
            enable_autostart()
            threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        except ApiError as error:
            if error.status_code == 401:
                return False
            self.status = "Offline"
        self.icon.run()
        return True

    def _heartbeat_loop(self) -> None:
        while self.running:
            try:
                self.client.heartbeat(self.agent_id)
                self.status = "Running"
            except ApiError:
                self.status = "Offline"
            time.sleep(30)

    def stop(self) -> None:
        self.running = False
        self.icon.stop()
