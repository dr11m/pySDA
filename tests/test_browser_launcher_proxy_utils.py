"""Tests for browser launcher proxy display helpers."""

from browser_launcher.proxy_format import format_proxy_label, parse_custom_proxy
from browser_launcher.proxy_utils import CS_DEALS_PROXY_BYPASS, to_playwright_proxy

ACCOUNT_PROXY = {
    "http": "http://user:secret@203.0.113.10:8000",
    "https": "http://user:secret@203.0.113.10:8000",
}


def test_format_proxy_label_strips_credentials() -> None:
    """Proxy label should expose host:port only."""
    assert format_proxy_label(ACCOUNT_PROXY) == "203.0.113.10:8000"


def test_format_proxy_label_returns_direct_when_missing() -> None:
    """Missing proxy mapping should be shown as direct connection."""
    assert format_proxy_label(None) == "direct"
    assert format_proxy_label({}) == "direct"


def test_parse_custom_proxy_supports_host_port_credentials_format() -> None:
    """Custom parser should support host:port:user:pass format."""
    proxy_mapping = parse_custom_proxy("203.0.113.10:8000:user:secret")

    assert proxy_mapping is not None
    assert proxy_mapping["http"] == "http://user:secret@203.0.113.10:8000"


def test_parse_custom_proxy_supports_url_format() -> None:
    """Custom parser should support full proxy URL format."""
    proxy_mapping = parse_custom_proxy("http://user:secret@203.0.113.10:8000")

    assert proxy_mapping is not None
    assert proxy_mapping["https"] == "http://user:secret@203.0.113.10:8000"


def test_to_playwright_proxy_has_no_bypass_by_default() -> None:
    """Full-proxy mode should send every host, including cs.deals, through the proxy."""
    playwright_proxy = to_playwright_proxy(ACCOUNT_PROXY)

    assert playwright_proxy is not None
    assert playwright_proxy["server"] == "http://203.0.113.10:8000"
    assert "bypass" not in playwright_proxy


def test_to_playwright_proxy_bypasses_cs_deals_when_requested() -> None:
    """Split mode should keep Steam on the proxy and send cs.deals direct."""
    playwright_proxy = to_playwright_proxy(ACCOUNT_PROXY, bypass_cs_deals=True)

    assert playwright_proxy is not None
    assert playwright_proxy["bypass"] == CS_DEALS_PROXY_BYPASS
