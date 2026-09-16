import platform
import socket
import webbrowser
from typing import Any

import httpx

from app.config import AGENT_VERSION, BACKEND_URL


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ApiClient:
    def __init__(self, token: str | None = None):
        self.token = token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = httpx.request(method, f"{BACKEND_URL}{path}", headers=self._headers(), timeout=15, **kwargs)
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiError("Unable to connect to the Recruiter backend") from exc
        if response.is_error:
            raise ApiError(data.get("detail", "The request failed"), response.status_code)
        return data

    def register(self, data: dict[str, Any]) -> dict[str, Any]:
        payload = dict(data)
        payload.setdefault("full_name", socket.gethostname())
        payload.setdefault("employee_name", socket.gethostname())
        return self._request("POST", "/auth/register", json=payload)

    def login(self, email: str, password: str) -> dict[str, Any]:
        return self._request("POST", "/auth/login", json={"email": email, "password": password})

    def register_agent(self) -> dict[str, Any]:
        return self._request("POST", "/agents/register", json={
            "device_name": socket.gethostname(), "platform": platform.platform(), "version": AGENT_VERSION
        })

    def heartbeat(self, agent_id: str) -> dict[str, Any]:
        return self._request("POST", f"/agents/{agent_id}/heartbeat",
                             json={"status": "running", "version": AGENT_VERSION})

    def agent_status(self, agent_id: str) -> dict[str, Any]:
        return self._request("GET", f"/agents/{agent_id}")

    def connect_mailbox(self, agent_id: str) -> None:
        result = self._request("GET", "/integrations/google/authorize", params={"agent_id": agent_id})
        webbrowser.open(result["authorization_url"])
