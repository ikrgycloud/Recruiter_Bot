import os
import sys
from pathlib import Path


APP_NAME = "RecruiterAgent"


def executable_path() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    return str(Path(sys.executable).resolve())


def enable_autostart() -> None:
    exe = executable_path()
    if sys.platform == "win32":
        import winreg
        command = f'"{exe}"'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)

        startup_dir = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup_dir.mkdir(parents=True, exist_ok=True)
        startup_script = startup_dir / f"{APP_NAME}.cmd"
        startup_script.write_text(f'@echo off\r\nstart "" "{exe}"\r\n', encoding="utf-8")
    elif sys.platform.startswith("linux"):
        path = Path.home() / ".config" / "autostart" / f"{APP_NAME}.desktop"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"[Desktop Entry]\nType=Application\nName={APP_NAME}\nExec={exe}\nX-GNOME-Autostart-enabled=true\n", encoding="utf-8")


def disable_autostart() -> None:
    if sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        startup_script = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / f"{APP_NAME}.cmd"
        startup_script.unlink(missing_ok=True)
    elif sys.platform.startswith("linux"):
        (Path.home() / ".config" / "autostart" / f"{APP_NAME}.desktop").unlink(missing_ok=True)
