"""Tests for Steam session detection helpers."""

from browser_launcher.session_check import has_steam_login_cookie


def test_has_steam_login_cookie_detects_active_session() -> None:
    """steamLoginSecure cookie should mark session as active."""
    cookies = [{"name": "steamLoginSecure", "value": "token", "domain": "steamcommunity.com"}]

    assert has_steam_login_cookie(cookies) is True


def test_has_steam_login_cookie_requires_value() -> None:
    """Empty steamLoginSecure cookie should not count as active session."""
    cookies = [{"name": "steamLoginSecure", "value": "", "domain": "steamcommunity.com"}]

    assert has_steam_login_cookie(cookies) is False
