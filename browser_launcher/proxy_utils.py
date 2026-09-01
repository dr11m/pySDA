"""Proxy parsing helpers for Playwright."""

from typing import Any, Dict, Optional
from urllib.parse import urlparse

from browser_launcher.proxy_format import extract_proxy_endpoint, format_proxy_label
from src.factories import create_instance_from_config

CS_DEALS_PROXY_BYPASS = "cs.deals,.cs.deals"


def resolve_account_proxy(
    proxy_provider_config: Dict[str, Any],
    account_name: str,
) -> Optional[Dict[str, str]]:
    """Resolve requests-style proxy mapping for an account."""
    if not proxy_provider_config:
        return None
    provider = create_instance_from_config(proxy_provider_config)
    return provider.get_proxy(account_name)


__all__ = [
    "CS_DEALS_PROXY_BYPASS",
    "format_proxy_label",
    "resolve_account_proxy",
    "to_playwright_proxy",
]


def to_playwright_proxy(
    proxy_mapping: Optional[Dict[str, str]],
    bypass_cs_deals: bool = False,
) -> Optional[Dict[str, str]]:
    """Convert requests-style proxy dict to Playwright proxy settings."""
    if not proxy_mapping:
        return None

    proxy_url = proxy_mapping.get("https") or proxy_mapping.get("http")
    if not proxy_url:
        return None

    endpoint = extract_proxy_endpoint(proxy_mapping)
    if endpoint is None:
        return None

    parsed = urlparse(proxy_url)
    if not parsed.hostname or not parsed.port:
        return None

    scheme = parsed.scheme or "http"
    playwright_proxy: Dict[str, str] = {
        "server": f"{scheme}://{parsed.hostname}:{parsed.port}",
    }

    if parsed.username:
        playwright_proxy["username"] = parsed.username
    if parsed.password:
        playwright_proxy["password"] = parsed.password
    if bypass_cs_deals:
        playwright_proxy["bypass"] = CS_DEALS_PROXY_BYPASS

    return playwright_proxy
