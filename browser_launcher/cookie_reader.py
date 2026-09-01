"""Read-only cookie loading for browser launcher."""

from typing import Any, Dict, List, Optional

from browser_launcher.cookie_converter import session_dict_to_playwright_cookies
from src.factories import create_instance_from_config


def load_playwright_cookies(
    cookie_storage_config: Dict[str, Any],
    username: str,
) -> List[Dict[str, Any]]:
    """Load cookies for an account and convert them for Playwright."""
    if not cookie_storage_config:
        return []

    storage = create_instance_from_config(cookie_storage_config)
    session_data: Optional[Dict[str, Any]] = storage.load_cookies(username)
    if not session_data:
        return []

    return session_dict_to_playwright_cookies(session_data)
