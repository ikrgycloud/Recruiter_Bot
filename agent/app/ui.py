import socket
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from app.api_client import ApiClient, ApiError


class AuthWindow:
    def __init__(self, client: ApiClient, on_authenticated: Callable[[dict], None]):
        self.client = client
        self.on_authenticated = on_authenticated
        self.root = tk.Tk()
        self.root.title("Recruiter Agent")
        self.root.geometry("460x560")
        self.root.resizable(False, False)
        self.fields: dict[str, tk.Entry] = {}
        self.password_visible = False
        self.mode = "register"
        self._render()

    def _render(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()
        ttk.Label(self.root, text="Recruiter Agent", font=("Segoe UI", 20, "bold")).pack(pady=(24, 4))
        ttk.Label(self.root, text="Register this employee on this system").pack(pady=(0, 18))
        self.fields = {}
        specs = [
            ("full_name", "Employee name"),
            ("company_email", "Employee email"),
            ("password", "Password"),
            ("confirm_password", "Confirm password"),
        ]
        for key, label in specs:
            ttk.Label(self.root, text=label).pack(anchor="w", padx=42)
            field = ttk.Frame(self.root)
            field.pack(fill="x", padx=42, pady=(2, 10))
            entry = ttk.Entry(field, width=36,
                              show="*" if key in {"password", "confirm_password"} else "")
            entry.pack(side="left", ipady=4)
            if key in {"password", "confirm_password"}:
                ttk.Button(field, text="👁", width=3,
                           command=self.toggle_password_visibility).pack(side="left", padx=(6, 0))
            self.fields[key] = entry
        ttk.Button(self.root, text="Register this system", command=self.submit).pack(pady=12, ipadx=30, ipady=4)

    def submit(self) -> None:
        values = {key: entry.get().strip() for key, entry in self.fields.items()}
        email = values.get("company_email", "")
        if "@" not in email or not email.split("@")[-1]:
            messagebox.showerror("Invalid email", "Please enter a valid company email address")
            return
        if len(values["password"]) < 8:
            messagebox.showerror("Invalid password", "Password must contain at least 8 characters")
            return
        if values["password"] != values["confirm_password"]:
            messagebox.showerror("Password mismatch", "Passwords do not match")
            return
        try:
            result = self.client.register(values)
            self.root.destroy()
            self.on_authenticated(result)
        except ApiError as exc:
            messagebox.showerror("Could not continue", exc.message)

    def toggle_password_visibility(self) -> None:
        self.password_visible = not self.password_visible
        for key in ("password", "confirm_password"):
            self.fields[key].configure(show="" if self.password_visible else "*")

    def run(self) -> None:
        self.root.mainloop()


def show_started_message() -> None:
    def popup() -> None:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.geometry("320x72+{}+{}".format(root.winfo_screenwidth() - 350, root.winfo_screenheight() - 130))
        ttk.Label(root, text="Recruiter Agent is running", padding=18).pack()
        root.after(5000, root.destroy)
        root.mainloop()
    threading.Thread(target=popup, daemon=True).start()


def connect_mailbox(client: ApiClient, agent_id: str) -> bool:
    result = {"connected": False}
    root = tk.Tk()
    root.title("Connect recruiter mailbox")
    root.geometry("480x230")
    root.resizable(False, False)
    ttk.Label(root, text="Connect the mailbox for this agent", font=("Segoe UI", 16, "bold")).pack(pady=(25, 8))
    ttk.Label(root, text="Choose the Gmail account in your browser. The selected account will be stored\nfor this system, and the agent will remain idle until it is connected.",
              justify="center").pack(pady=5)
    status = ttk.Label(root, text="Not connected")
    status.pack(pady=10)

    def open_google() -> None:
        try:
            client.connect_mailbox(agent_id)
            status.configure(text="Browser opened. Waiting for account selection...")
        except ApiError as exc:
            status.configure(text=exc.message)

    def poll() -> None:
        if result["connected"]:
            return
        try:
            agent = client.agent_status(agent_id)
            if agent.get("mailbox_connected"):
                result["connected"] = True
                status.configure(text=f"Connected: {agent.get('mailbox_email')}")
                root.after(1200, root.destroy)
                return
        except ApiError as exc:
            status.configure(text=exc.message)
        root.after(3000, poll)

    ttk.Button(root, text="Choose Gmail account", command=open_google).pack(pady=6, ipadx=18, ipady=4)
    ttk.Button(root, text="Connect later", command=root.destroy).pack()
    root.after(3000, poll)
    root.mainloop()
    return result["connected"]
