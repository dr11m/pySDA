"""Reject foreign saved and refreshed cookies before enabling account operations."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from src.cookie_manager import CookieManager
from src.steampy.client import SteamClient
from src.steampy.login import InvalidCredentials

STEAM_ID: str = "76561198000000000"
FOREIGN_ID: str = "76561198000000099"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SteamClient:
    """Construct a real account client with a transport that cannot reach Steam."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "min_request_delay_ms: 0\nrequest_connect_timeout_seconds: 2\n"
        "request_read_timeout_seconds: 3\ncheck_ip_on_every_steam_request: false\n",
        encoding="utf-8",
    )
    account: SteamClient = SteamClient(username="selected", steam_id=STEAM_ID, session_path=str(tmp_path / "selected.pkl"))
    account.steam_guard = {"shared_secret": "c2VjcmV0", "identity_secret": "c2VjcmV0"}
    account._session.get = Mock(return_value=SimpleNamespace(status_code=200, url="https://steamcommunity.com/market/mylistings"))
    account.save_session = Mock(return_value=True)
    return account


def _cookies(session: requests.Session, steam_id: str) -> None:
    """Populate the cookies actually sent to the community destination."""
    session.cookies.clear()
    session.cookies.set("steamLoginSecure", f"{steam_id}%7C%7Ctest-token", domain="steamcommunity.com")
    session.cookies.set("sessionid", "test-csrf", domain="steamcommunity.com")


@pytest.mark.parametrize("already_logged_in", [False, True])
def test_foreign_saved_cookies_cannot_enable_client(client: SteamClient, monkeypatch: pytest.MonkeyPatch, already_logged_in: bool) -> None:
    """Even a stale ready flag cannot authorize cookies belonging to another account."""
    _cookies(client._session, FOREIGN_ID)
    client.was_login_executed = already_logged_in
    refresh: Mock = Mock()
    monkeypatch.setattr(client, "update_session", refresh)
    client.login_if_need_to()
    assert client.was_login_executed is False
    refresh.assert_called_once_with()
    client._session.get.assert_not_called()


def test_owned_saved_cookies_remain_reusable(client: SteamClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The account ownership guard preserves ordinary reuse of the right session."""
    _cookies(client._session, STEAM_ID)
    refresh: Mock = Mock()
    monkeypatch.setattr(client, "update_session", refresh)
    client.login_if_need_to()
    assert client.was_login_executed is True
    refresh.assert_not_called()
    client._session.get.assert_called_once()


def test_cookie_manager_rejects_foreign_live_session(client: SteamClient) -> None:
    """HTTP 200 alone must not make a wrong account's cached cookies usable."""
    _cookies(client._session, FOREIGN_ID)
    manager: CookieManager = CookieManager.__new__(CookieManager)
    manager.username = "selected"
    manager.steam_id = STEAM_ID
    manager.steam_client = client
    assert manager._is_session_alive() is False
    client._session.get.assert_not_called()


def test_foreign_refresh_result_is_not_saved_or_authorized(client: SteamClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Refresh results must be checked before setting ready flags or persisting them."""
    _cookies(client._session, STEAM_ID)
    client.refresh_token = "test-refresh"

    class ForeignRefresh:
        """Return a mismatched refresh result without network access."""

        def __init__(self, *args: Any) -> None:
            self.session: requests.Session = client._session

        def get_web_cookies(self, *args: Any) -> None:
            _cookies(self.session, FOREIGN_ID)

    monkeypatch.setattr("src.steampy.client.LoginExecutor", ForeignRefresh)
    assert client._try_refresh_session() is False
    assert client.was_login_executed is False
    client.save_session.assert_not_called()


def test_foreign_full_login_result_is_not_saved_or_authorized(client: SteamClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A full login result must authenticate the configured Steam ID before use."""
    foreign: requests.Session = requests.Session()
    _cookies(foreign, FOREIGN_ID)
    monkeypatch.setattr(client, "_try_refresh_session", lambda: False)
    executor: Mock = Mock()
    executor.login.return_value = (foreign, "foreign-refresh")
    monkeypatch.setattr("src.steampy.client.LoginExecutor", Mock(return_value=executor))
    with pytest.raises(InvalidCredentials, match="configured account"):
        client.update_session()
    assert client.was_login_executed is False
    client.save_session.assert_not_called()
