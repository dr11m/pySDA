"""Tests for browser session lock handling."""

import json
from pathlib import Path

from browser_launcher.session_lock import LOCK_FILE_NAME, SessionLock


def test_acquire_and_release_lock(tmp_path: Path) -> None:
    """Lock file should be created on acquire and removed on release."""
    profile_dir = tmp_path / "acc1"
    session_lock = SessionLock(profile_dir, "acc1")

    assert session_lock.acquire() is True
    assert (profile_dir / LOCK_FILE_NAME).exists()

    session_lock.release()
    assert not (profile_dir / LOCK_FILE_NAME).exists()


def test_is_active_cleans_stale_lock(tmp_path: Path) -> None:
    """Stale lock with dead pid should be removed automatically."""
    profile_dir = tmp_path / "acc1"
    profile_dir.mkdir(parents=True)
    lock_path = profile_dir / LOCK_FILE_NAME
    lock_path.write_text(
        json.dumps({"pid": 999999999, "account_name": "acc1", "started_at": "now"}),
        encoding="utf-8",
    )

    session_lock = SessionLock(profile_dir, "acc1")

    assert session_lock.is_active() is False
    assert not lock_path.exists()
