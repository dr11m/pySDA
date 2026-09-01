"""Data models for the browser launcher."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AccountSettings:
    """Resolved settings for one configured account."""

    account_name: str
    username: str
    cookie_storage_config: Dict[str, Any]
    proxy_provider_config: Dict[str, Any]
    description: str = ""


@dataclass(frozen=True)
class LaunchOptions:
    """Runtime options for opening a browser session."""

    account_name: str
    start_url: Optional[str]
    config_path: Path
    profile_root: Path
    refresh_cookies: bool
    proxy_mapping: Optional[Dict[str, str]] = None
    verify_steam_session: bool = False
    seed_cookies: bool = False
    bypass_cs_deals: bool = False
