#!/usr/bin/env python3
"""JSON-based cookie storage implementation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from src.interfaces.storage_interface import CookieStorageInterface
from src.utils.logger_setup import log_exception


class JsonCookieStorage(CookieStorageInterface):
    """Store account cookies in JSON files under the storage directory."""

    def __init__(self, **kwargs):
        self.storage_dir = Path("src/implementations/cookie_storage/json_storage/cookies")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_cookies(self, username: str, cookies: Dict[str, str]) -> bool:
        """Save cookies for an account."""
        try:
            payload = {
                "cookies": cookies,
                "last_update": datetime.now().isoformat(),
            }
            with open(self.storage_dir / f"{username}_cookies.json", "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2, ensure_ascii=False)
            return True
        except Exception:
            log_exception(f"Failed to save cookie file for '{username}'.")
            return False

    def load_cookies(self, username: str) -> Optional[Dict[str, str]]:
        """Load cookies for an account."""
        cookie_file = self.storage_dir / f"{username}_cookies.json"
        if not cookie_file.exists():
            return None

        try:
            with open(cookie_file, "r", encoding="utf-8") as file:
                payload = json.load(file)
            return payload.get("cookies")
        except Exception:
            log_exception(f"Failed to load cookie file for '{username}'.")
            return None

    def delete_cookies(self, username: str) -> bool:
        """Delete cookie file for an account."""
        try:
            cookie_file = self.storage_dir / f"{username}_cookies.json"
            if cookie_file.exists():
                cookie_file.unlink()
            return True
        except Exception:
            log_exception(f"Failed to delete cookie file for '{username}'.")
            return False

    def get_last_update(self, username: str) -> Optional[datetime]:
        """Return last cookie update timestamp for an account."""
        cookie_file = self.storage_dir / f"{username}_cookies.json"
        if not cookie_file.exists():
            return None

        try:
            with open(cookie_file, "r", encoding="utf-8") as file:
                payload = json.load(file)
            last_update = payload.get("last_update")
            if last_update:
                return datetime.fromisoformat(last_update)
            return None
        except Exception:
            log_exception(f"Failed to read last update from cookie file for '{username}'.")
            return None
