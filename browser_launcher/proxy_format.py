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
