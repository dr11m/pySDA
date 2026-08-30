"""Track active browser sessions per account."""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


LOCK_FILE_NAME = ".session.lock"


@dataclass(frozen=True)
class SessionLockInfo:
    """Metadata stored for an active browser session."""

    pid: int
    account_name: str
    started_at: str


class SessionLock:
    """Manage per-account lock files for running browser sessions."""

    def __init__(self, profile_dir: Path, account_name: str):
        self.profile_dir = profile_dir
        self.account_name = account_name
        self.lock_path = profile_dir / LOCK_FILE_NAME

    def is_active(self) -> bool:
        """Return True when a live browser session holds the lock."""
        info = self._read_lock()
        if info is None:
            return False
        if not _is_process_alive(info.pid):
            self.release()
            return False
        return True

    def acquire(self) -> bool:
        """Create a lock file when no active session exists."""
        if self.is_active():
            return False

        self.release()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        payload = SessionLockInfo(
            pid=os.getpid(),
            account_name=self.account_name,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self.lock_path.write_text(
            json.dumps(payload.__dict__, ensure_ascii=True),
            encoding="utf-8",
        )
        return True

    def release(self) -> None:
        """Remove lock file for the account profile."""
        if self.lock_path.exists():
            self.lock_path.unlink()

    def _read_lock(self) -> SessionLockInfo | None:
        """Read lock metadata from disk."""
        if not self.lock_path.exists():
            return None

        payload = json.loads(self.lock_path.read_text(encoding="utf-8"))
        pid = int(payload.get("pid", 0))
        account_name = str(payload.get("account_name", ""))
        started_at = str(payload.get("started_at", ""))
        if not pid or not account_name:
            return None

        return SessionLockInfo(
            pid=pid,
            account_name=account_name,
            started_at=started_at,
        )


def _is_process_alive(pid: int) -> bool:
    """Check whether a process id is still running."""
    if pid <= 0:
        return False

    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout.strip().lower()
        if not output or "no tasks are running" in output:
            return False
        return str(pid) in result.stdout

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
