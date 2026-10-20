"""Proxy parsing helpers for Playwright."""

from typing import Any, Dict, Optional
from urllib.parse import ParseResult, urlparse

from browser_launcher.proxy_format import format_proxy_label
from src.factories import create_instance_from_config

CS_DEALS_PROXY_BYPASS = "cs.deals,.cs.deals"


def resolve_account_proxy(
    proxy_provider_config: Dict[str, Any],
    account_name: str,
) -> Optional[Dict[str, str]]:
    """Resolve an account route from an explicitly configured proxy provider.

    Args:
        proxy_provider_config: Provider module and class configuration.
        account_name: Account whose route is required.

    Returns:
        Account proxy mapping, or None for the provider's explicit no_proxy marker.

    Raises:
        ValueError: Required provider configuration is missing.
    """
    if not proxy_provider_config or not proxy_provider_config.get("module_path") or not proxy_provider_config.get("class_name"):
        raise ValueError("Account proxy provider must specify module_path and class_name")
    provider: Any = create_instance_from_config(proxy_provider_config)
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
    """Convert an explicit route without falling back to direct on invalid proxies.

    Args:
        proxy_mapping: Both account proxy routes, or None for explicit direct access.
        bypass_cs_deals: Whether cs.deals should use direct access.

    Returns:
        Playwright proxy settings, or None only for explicit direct access.

    Raises:
        ValueError: The configured mapping or proxy URL is incomplete or invalid.
    """
    if proxy_mapping is None:
        return None
    if not proxy_mapping.get("http") or not proxy_mapping.get("https"):
        raise ValueError("Account proxy must specify both http and https routes")

    proxy_url: str = proxy_mapping["https"]
    try:
        parsed: ParseResult = urlparse(proxy_url)
        port: int | None = parsed.port
    except ValueError:
        raise ValueError("Account proxy URL is invalid") from None
    if parsed.scheme not in {"http", "https", "socks4", "socks5"} or not parsed.hostname or not port:
        raise ValueError("Account proxy URL must specify a supported scheme, host and port")

    playwright_proxy: Dict[str, str] = {
        "server": f"{parsed.scheme}://{parsed.hostname}:{port}",
    }

    if parsed.username:
        playwright_proxy["username"] = parsed.username
    if parsed.password:
        playwright_proxy["password"] = parsed.password
    if bypass_cs_deals:
        playwright_proxy["bypass"] = CS_DEALS_PROXY_BYPASS

    return playwright_proxy
