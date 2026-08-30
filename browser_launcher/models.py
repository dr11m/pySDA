"""Data models for the browser launcher."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class AccountSettings:
    """Resolved settings for one configured account."""

    account_name: str
    username: str
    cookie_storage_config: Dict[str, Any]
    proxy_provider_config: Dict[str, Any]


@dataclass(frozen=True)
class LaunchOptions:
    """Runtime options for opening a browser session."""

    account_name: str
    start_url: str
    config_path: Path
    profile_root: Path
    refresh_cookies: bool
