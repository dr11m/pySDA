"""Tests for Steam session liveness via market listings."""

from unittest.mock import Mock

from src.steampy.session_check import check_session_static
from src.steampy.models import SteamUrl

MYLISTINGS_URL = f"{SteamUrl.COMMUNITY_URL}/market/mylistings?start=0&count=100"


def test_check_session_static_treats_mylistings_http_400_as_dead() -> None:
    """HTTP 400 on market/mylistings must mark the session dead for cookie consumers."""
    session = Mock()
    response = Mock()
    response.status_code = 400
    response.url = MYLISTINGS_URL
    response.text = "[]"
    session.get.return_value = response

    assert check_session_static("anyuser", session) is False
    session.get.assert_called_once_with(MYLISTINGS_URL)


def test_check_session_static_treats_mylistings_http_200_as_alive() -> None:
    """HTTP 200 on market/mylistings must mark the session alive without scraping username HTML."""
    session = Mock()
    response = Mock()
    response.status_code = 200
    response.url = MYLISTINGS_URL
    response.text = "{}"
    session.get.return_value = response

    assert check_session_static("anyuser", session) is True
    session.get.assert_called_once_with(MYLISTINGS_URL)


def test_check_session_static_treats_login_redirect_as_dead() -> None:
    """A 200 that landed on a login URL is not a live market session."""
    session = Mock()
    response = Mock()
    response.status_code = 200
    response.url = f"{SteamUrl.COMMUNITY_URL}/login/home/"
    response.text = "<html>login</html>"
    session.get.return_value = response

    assert check_session_static("anyuser", session) is False
    session.get.assert_called_once_with(MYLISTINGS_URL)
