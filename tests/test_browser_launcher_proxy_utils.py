"""Tests for browser launcher proxy display helpers."""

from browser_launcher.proxy_format import format_proxy_label


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
