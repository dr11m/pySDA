"""Offline regression tests for account proxy routing and request timeouts."""

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import requests
from pydantic import ValidationError
from requests.adapters import HTTPAdapter

from src.steampy.client import SteamClient
from src.steampy.confirmation import ConfirmationExecutor
from src.steampy.login import LoginExecutor
from src.steampy.session_check import check_session_static
from src.cookie_manager import CookieManager
from src.trade_confirmation_manager import TradeConfirmationManager
from src.utils.logger_setup import logger

PROXIES: dict[str, str] = {
    "http": "http://proxy_user:proxy_password@account-proxy.invalid:8080",
    "https": "http://proxy_user:proxy_password@account-proxy.invalid:8080",
}


@dataclass
class HttpCall:
    """Arguments received at the HTTP transport boundary."""

    request: requests.PreparedRequest
    proxies: dict[str, str]
    timeout: float | tuple[float, float] | None


@pytest.fixture(autouse=True)
def http_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use an isolated runtime config and prohibit standalone proxy probes."""
    monkeypatch.chdir(tmp_path)
    config: dict[str, int | bool] = {
        "min_request_delay_ms": 0,
        "request_connect_timeout_seconds": 2,
        "request_read_timeout_seconds": 3,
        "check_ip_on_every_steam_request": False,
    }
    (tmp_path / "config.yaml").write_text(json.dumps(config), encoding="utf-8")

    def fail_probe(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Client construction must not probe the network")

    monkeypatch.setattr(requests, "get", fail_probe)


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> list[HttpCall]:
    """Capture real Requests routing decisions without opening sockets."""
    calls: list[HttpCall] = []

    def send(adapter: HTTPAdapter, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:
        calls.append(HttpCall(request, dict(kwargs.get("proxies") or {}), kwargs.get("timeout")))
        response: requests.Response = requests.Response()
        response.status_code = 200
        response.url = request.url
        response.request = request
        response._content = b'{"transfer_info": [{"url": "https://steamcommunity.com/login/settoken", "params": {}}]}'
        return response

    monkeypatch.setattr(HTTPAdapter, "send", send)
    return calls


def test_constructor_assigns_proxy_without_network_probe(transport: list[HttpCall]) -> None:
    """Configuring a client must complete before any network operation."""
    client: SteamClient = SteamClient(username="account", proxies=PROXIES)
    assert client._session.proxies == PROXIES
    assert client._session.trust_env is False
    assert transport == []


def test_account_routes_are_isolated(transport: list[HttpCall]) -> None:
    """Changing one account route must not mutate another account session."""
    other_proxies: dict[str, str] = {"http": "http://other.invalid:80", "https": "http://other.invalid:80"}
    first: SteamClient = SteamClient(username="first", proxies=PROXIES)
    second: SteamClient = SteamClient(username="second", proxies=other_proxies)
    second.set_proxies(None)
    first.api_call("GET", "IEconService", "GetTradeOffers", "v1")
    second.api_call("GET", "IEconService", "GetTradeOffers", "v1")
    assert [call.proxies for call in transport] == [PROXIES, {}]


def test_saved_host_adapter_cannot_bypass_current_timeout(tmp_path: Path, transport: list[HttpCall]) -> None:
    """Saved host-specific adapters must not bypass current request settings."""
    saved: requests.Session = requests.Session()
    saved.mount("https://api.steampowered.com/", HTTPAdapter())
    session_path: Path = tmp_path / "host-adapter.pkl"
    session_path.write_bytes(pickle.dumps((saved, "saved-refresh-token")))
    client: SteamClient = SteamClient(username="account", proxies=PROXIES, session_path=str(session_path))
    client.api_call("GET", "IEconService", "GetTradeOffers", "v1")
    assert transport[0].timeout == (2, 3)


def test_saved_adapter_keeps_configured_timing(transport: list[HttpCall]) -> None:
    """Adapters embedded in session pickles must retain timing attributes."""
    client: SteamClient = SteamClient(username="account", proxies=PROXIES)
    session: requests.Session = pickle.loads(pickle.dumps(client._session))
    session.get("https://steamcommunity.com/market/")
    assert transport[0].proxies == PROXIES
    assert transport[0].timeout == (2, 3)


def test_cookie_manager_clients_keep_account_route(transport: list[HttpCall]) -> None:
    """Both context creation and saved-session client creation keep the route."""
    manager: CookieManager = CookieManager(username="account", proxy=PROXIES, accounts_dir="accounts")
    manager.client.api_call("GET", "IEconService", "GetTradeOffers", "v1")
    restored: SteamClient | None = manager._create_steam_client()
    assert restored is not None
    restored.api_call("GET", "IEconService", "GetTradeOffers", "v1")
    assert len(transport) == 2
    assert all(call.proxies == PROXIES and call.timeout == (2, 3) for call in transport)


@pytest.mark.parametrize("proxies", [PROXIES, None])
def test_current_route_replaces_pickle_and_environment(
    proxies: dict[str, str] | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    transport: list[HttpCall],
) -> None:
    """Saved and environmental proxy settings must not override the account."""
    saved: requests.Session = requests.Session()
    saved.proxies = {"https": "http://old.invalid:80", "https://api.steampowered.com": "http://old.invalid:81"}
    session_path: Path = tmp_path / "saved.pkl"
    session_path.write_bytes(pickle.dumps((saved, "saved-refresh-token")))
    monkeypatch.setenv("HTTPS_PROXY", "http://environment.invalid:82")
    monkeypatch.setenv("ALL_PROXY", "http://environment.invalid:83")
    client: SteamClient = SteamClient(username="account", proxies=proxies, session_path=str(session_path))

    client.api_call("GET", "IEconService", "GetTradeOffers", "v1")

    assert client.refresh_token == "saved-refresh-token"
    assert client._session.proxies == (proxies or {})
    assert transport[0].proxies == (proxies or {})
    assert transport[0].timeout == (2, 3)


def test_login_refresh_api_and_confirmations_use_account_session(transport: list[HttpCall]) -> None:
    """All active Steam subsystems must share the configured account route."""
    client: SteamClient = SteamClient(username="account", proxies=PROXIES)
    login: LoginExecutor = LoginExecutor("76561198000000000", "account", "password", "c2VjcmV0", client._session)
    confirmations: ConfirmationExecutor = ConfirmationExecutor("c2VjcmV0", "76561198000000000", client._session)

    login._api_call("POST", "IAuthenticationService", "BeginAuthSessionViaCredentials")
    login._make_finalize_request("session-id", "refresh-token")
    client.api_call("GET", "IEconService", "GetTradeOffers", "v1")
    assert check_session_static("account", client._session) is True
    confirmations._fetch_confirmations_page()

    assert client.market._session is client._session
    assert len(transport) == 5
    assert all(call.proxies == PROXIES and call.timeout == (2, 3) for call in transport)


def test_temporary_delay_keeps_timeout_and_restores_adapter(transport: list[HttpCall]) -> None:
    """Login delay changes must preserve timeouts, including zero delay."""
    client: SteamClient = SteamClient(username="account", proxies=PROXIES)
    original: HTTPAdapter = client._session.get_adapter("https://steamcommunity.com/")
    with client.temporary_delay(0):
        client._session.get("https://steamcommunity.com/market/")
    client._session.get("https://steamcommunity.com/market/")

    assert client._session.get_adapter("https://steamcommunity.com/") is original
    assert all(call.timeout == (2, 3) for call in transport)


@pytest.mark.parametrize("proxies", [{}, {"http": "http://proxy.invalid:80"}])
def test_incomplete_proxy_mapping_is_rejected(proxies: dict[str, str]) -> None:
    """Incomplete proxy mappings must not enable a direct HTTPS route."""
    with pytest.raises(ValueError, match="http.*https"):
        SteamClient(username="account", proxies=proxies)


@pytest.mark.parametrize("key,value", [("request_connect_timeout_seconds", 0), ("request_read_timeout_seconds", -1)])
def test_invalid_timeout_is_rejected(key: str, value: int) -> None:
    """Nonpositive configured timeouts must fail before a request."""
    path: Path = Path("config.yaml")
    config: dict[str, int | bool] = json.loads(path.read_text(encoding="utf-8"))
    config[key] = value
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValidationError):
        SteamClient(username="account")


def test_missing_timeout_is_rejected() -> None:
    """A missing required timeout must not silently use a default."""
    Path("config.yaml").write_text('{"check_ip_on_every_steam_request": false}', encoding="utf-8")
    with pytest.raises(ValidationError):
        SteamClient(username="account")


def test_config_validation_hides_account_secrets() -> None:
    """Configuration errors must not print unrelated account credentials."""
    Path("config.yaml").write_text('{"accounts": {"account": {"password": "private-account-password"}}}', encoding="utf-8")
    with pytest.raises(ValidationError) as error:
        SteamClient(username="account")
    assert "private-account-password" not in str(error.value)


def test_request_logs_hide_query_secrets(transport: list[HttpCall]) -> None:
    """Request progress must be visible without logging credentials."""
    messages: list[str] = []
    sink: int = logger.add(lambda message: messages.append(str(message)), format="{message}", level="DEBUG")
    try:
        client: SteamClient = SteamClient(username="account", proxies=PROXIES)
        client.api_call("GET", "IEconService", "GetTradeOffers", "v1", {"access_token": "query-secret"})
    finally:
        logger.remove(sink)
    output: str = "\n".join(messages)
    assert "request started" in output
    assert "request completed" in output
    assert "elapsed=" in output
    assert "query-secret" not in output
    assert "proxy_password" not in output


def test_proxy_failure_does_not_retry_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing account proxy must remain an error with the same route."""
    calls: list[dict[str, str]] = []

    def send(adapter: HTTPAdapter, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:
        calls.append(dict(kwargs["proxies"]))
        raise requests.exceptions.ProxyError("Unavailable proxy")

    monkeypatch.setattr(HTTPAdapter, "send", send)
    client: SteamClient = SteamClient(username="account", proxies=PROXIES)
    with pytest.raises(requests.exceptions.ProxyError):
        client.api_call("GET", "IEconService", "GetTradeOffers", "v1")
    assert calls == [PROXIES]


def test_failure_logs_hide_exception_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exceptions containing proxy credentials must not enter request logs."""
    messages: list[str] = []

    def send(adapter: HTTPAdapter, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:
        raise requests.exceptions.ReadTimeout("secret-proxy-password secret-query-token")

    monkeypatch.setattr(HTTPAdapter, "send", send)
    sink: int = logger.add(lambda message: messages.append(str(message)), format="{message}", level="DEBUG")
    try:
        client: SteamClient = SteamClient(username="account", proxies=PROXIES)
        with pytest.raises(requests.exceptions.ReadTimeout):
            client._session.get("https://steamcommunity.com/market/?token=secret-query-token")
    finally:
        logger.remove(sink)
    output: str = "\n".join(messages)
    assert "request failed" in output
    assert "ReadTimeout" in output
    assert "secret-proxy-password" not in output
    assert "secret-query-token" not in output


def test_confirmation_token_logs_hide_cookie_values() -> None:
    """Extracting a token must not log cookie or token prefixes."""
    client: SteamClient = SteamClient(username="account", proxies=PROXIES)
    secret: str = "private-confirmation-access-token"
    client._session.cookies.set("steamLoginSecure", f"76561198000000000%7C%7C{secret}", domain="steamcommunity.com")
    manager: TradeConfirmationManager = TradeConfirmationManager.__new__(TradeConfirmationManager)
    manager.username = "account"
    messages: list[str] = []
    sink: int = logger.add(lambda message: messages.append(str(message)), format="{message}", level="DEBUG")
    try:
        assert manager._get_access_token(client) == secret
    finally:
        logger.remove(sink)
    assert secret[:15] not in "\n".join(messages)
