"""Tests for browser launcher cookie conversion."""

from browser_launcher.cookie_converter import session_dict_to_playwright_cookies


def test_session_dict_to_playwright_cookies_extracts_core_fields() -> None:
    """Converter should map nested session cookies to Playwright format."""
    session_data = {
        "cookies": {
            "steamcommunity.com": {
                "/": {
                    "sessionid": {
                        "name": "sessionid",
                        "value": "abc123",
                        "domain": "steamcommunity.com",
                        "path": "/",
                        "secure": True,
                        "expires": None,
                        "_rest": {"SameSite": "None"},
                    }
                }
            }
        }
    }

    cookies = session_dict_to_playwright_cookies(session_data)

    assert len(cookies) == 1
    assert cookies[0]["name"] == "sessionid"
    assert cookies[0]["value"] == "abc123"
    assert cookies[0]["domain"] == "steamcommunity.com"
    assert cookies[0]["secure"] is True
    assert cookies[0]["sameSite"] == "None"
