"""Tests for browser launcher proxy display helpers."""

import pytest

from browser_launcher.proxy_format import format_proxy_label, parse_custom_proxy
from browser_launcher.proxy_utils import CS_DEALS_PROXY_BYPASS, resolve_account_proxy, to_playwright_proxy

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


@pytest.mark.parametrize("provider_config", [{}, {"module_path": "unused", "password": "secret"}])
def test_missing_proxy_provider_cannot_select_direct(provider_config: dict[str, str]) -> None:
    """Missing provider configuration must stop account routing instead of selecting direct."""
    with pytest.raises(ValueError) as error:
        resolve_account_proxy(provider_config, "account")
    assert "secret" not in str(error.value)


def test_to_playwright_proxy_keeps_explicit_direct() -> None:
    """The explicit direct selection must remain available."""
    assert to_playwright_proxy(None) is None


@pytest.mark.parametrize(
    "proxy_mapping",
    [
        {},
        {"http": "http://proxy.invalid:8080"},
        {"https": "http://proxy.invalid:8080"},
        {"http": "", "https": "http://proxy.invalid:8080"},
        {"http": "http://proxy.invalid:8080", "https": ""},
    ],
)
def test_incomplete_proxy_mapping_cannot_select_direct(proxy_mapping: dict[str, str]) -> None:
    """Only an explicit None may select direct; incomplete account routes must fail."""
    with pytest.raises(ValueError):
        to_playwright_proxy(proxy_mapping)


@pytest.mark.parametrize(
    "proxy_url",
    [
        "http://user:secret@proxy.invalid",
        "proxy.invalid:8080",
        "http://",
        "http://user:secret@:8080",
        "http://[",
        "http://user:secret@proxy.invalid:secret",
        "http://user:secret@proxy.invalid:65536",
        "http://user:secret@proxy.invalid:0",
        "ftp://user:secret@proxy.invalid:8080",
    ],
)
def test_invalid_proxy_url_stops_routing_without_exposing_credentials(proxy_url: str) -> None:
    """Malformed routes must stop launch with a credential-free error."""
    proxy_mapping: dict[str, str] = {"http": proxy_url, "https": proxy_url}
    with pytest.raises(ValueError) as error:
        to_playwright_proxy(proxy_mapping)
    assert "secret" not in str(error.value)
