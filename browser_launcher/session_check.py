"""Steam session detection helpers for browser launcher."""

from typing import Any, Dict, List

STEAM_LOGIN_COOKIE = "steamLoginSecure"
STEAM_COMMUNITY_URL = "https://steamcommunity.com"


def has_steam_login_cookie(cookies: List[Dict[str, Any]]) -> bool:
    """Return True when steamLoginSecure cookie is present."""
    for cookie in cookies:
        if cookie.get("name") != STEAM_LOGIN_COOKIE:
            continue
        if cookie.get("value"):
            return True
    return False


def context_has_steam_session(context: Any) -> bool:
    """Return True when browser context has an active Steam web session."""
    cookies = context.cookies(STEAM_COMMUNITY_URL)
    return has_steam_login_cookie(cookies)
