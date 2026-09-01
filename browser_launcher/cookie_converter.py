"""Convert pySDA cookie storage format to Playwright cookies."""

from typing import Any, Dict, List


def session_dict_to_playwright_cookies(session_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert session_to_dict payload into Playwright cookie dicts."""
    nested_cookies = session_data.get("cookies", session_data)
    if not isinstance(nested_cookies, dict):
        return []

    playwright_cookies: List[Dict[str, Any]] = []

    for domain, paths in nested_cookies.items():
        if not isinstance(paths, dict):
            continue
        for path, cookie_names in paths.items():
            if not isinstance(cookie_names, dict):
                continue
            for cookie_attrs in cookie_names.values():
                if not isinstance(cookie_attrs, dict):
                    continue
                name = cookie_attrs.get("name")
                value = cookie_attrs.get("value")
                if not name or value is None:
                    continue

                cookie: Dict[str, Any] = {
                    "name": name,
                    "value": value,
                    "domain": cookie_attrs.get("domain") or domain,
                    "path": cookie_attrs.get("path", path),
                    "secure": bool(cookie_attrs.get("secure", False)),
                }

                expires = cookie_attrs.get("expires")
                if expires:
                    cookie["expires"] = int(expires)

                rest = cookie_attrs.get("_rest", {}) or {}
                if rest.get("HttpOnly") is not None:
                    cookie["httpOnly"] = True

                same_site = rest.get("SameSite")
                if same_site in {"Strict", "Lax", "None"}:
                    cookie["sameSite"] = same_site

                playwright_cookies.append(cookie)

    return playwright_cookies
