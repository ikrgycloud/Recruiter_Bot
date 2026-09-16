from pathlib import Path
from typing import TextIO

from app.config import DATA_DIR


class SingleInstance:
    def __init__(self) -> None:
        self.path = DATA_DIR / "agent.lock"
        self.handle: TextIO | None = None

    def acquire(self) -> bool:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+")
        handle.seek(0)
        if self.path.stat().st_size == 0:
            handle.write("1")
            handle.flush()
        try:
            if __import__("sys").platform == "win32":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            handle.close()
            return False
        self.handle = handle
        return True

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            if __import__("sys").platform == "win32":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None
