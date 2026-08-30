"""Pure proxy URL formatting helpers."""

from typing import Dict, Optional
from urllib.parse import urlparse


def format_proxy_label(proxy_mapping: Optional[Dict[str, str]]) -> str:
    """Return proxy endpoint for display without credentials."""
    endpoint = extract_proxy_endpoint(proxy_mapping)
    if endpoint is None:
        return "direct"
    return endpoint


def extract_proxy_endpoint(proxy_mapping: Optional[Dict[str, str]]) -> Optional[str]:
    """Extract host:port from a requests-style proxy mapping."""
    if not proxy_mapping:
        return None

    proxy_url = proxy_mapping.get("https") or proxy_mapping.get("http")
    if not proxy_url:
        return None

    parsed = urlparse(proxy_url)
    if not parsed.hostname:
        return None
    if parsed.port:
        return f"{parsed.hostname}:{parsed.port}"
    return parsed.hostname


def parse_custom_proxy(raw_value: str) -> Optional[Dict[str, str]]:
    """Parse user-provided proxy string into requests-style mapping."""
    proxy_url = raw_value.strip()
    if not proxy_url:
        return None

    if proxy_url.lower() in {"direct", "no_proxy", "none"}:
        return None

    if "@" not in proxy_url and proxy_url.count(":") >= 3:
        stripped = proxy_url
        scheme = "http"
        if proxy_url.startswith("http://"):
            stripped = proxy_url[7:]
        elif proxy_url.startswith("https://"):
            stripped = proxy_url[8:]
            scheme = "https"

        parts = stripped.split(":")
        if len(parts) >= 4:
            host = parts[0]
            port = parts[1]
            username = parts[2]
            password = parts[3]
            proxy_url = f"{scheme}://{username}:{password}@{host}:{port}"

    if not proxy_url.startswith(("http://", "https://")):
        proxy_url = f"http://{proxy_url}"

    return {
        "http": proxy_url,
        "https": proxy_url,
    }
