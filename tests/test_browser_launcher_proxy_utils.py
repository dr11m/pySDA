"""Tests for browser launcher proxy display helpers."""

from browser_launcher.proxy_format import format_proxy_label, parse_custom_proxy


def test_format_proxy_label_strips_credentials() -> None:
    """Proxy label should expose host:port only."""
    proxy_mapping = {
        "http": "http://user:secret@203.0.113.10:8000",
        "https": "http://user:secret@203.0.113.10:8000",
    }

    assert format_proxy_label(proxy_mapping) == "203.0.113.10:8000"


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
