"""BeginAuth responses without auth ids must fail with actionable errors."""

import time

import pytest
import requests

from src.steampy.exceptions import ApiException, TooManyRequests
from src.steampy.login import LoginExecutor
from src.utils.logger_setup import logger

STEAM_ID: str = "76561198000000000"


def _executor() -> LoginExecutor:
    """Build a login executor that never touches the network."""
    return LoginExecutor(STEAM_ID, "steam_login", "test-password", "c2VjcmV0", requests.Session())


def _response(payload: bytes, status: int = 200) -> requests.Response:
    """Wrap a raw body as a Steam API response."""
    response: requests.Response = requests.Response()
    response.status_code = status
    response._content = payload
    return response


def test_begin_auth_params_returns_ids_on_success() -> None:
    """A complete BeginAuth body must yield the three auth ids."""
    executor: LoginExecutor = _executor()
    response: requests.Response = _response(b'{"response":{"client_id":123,"steamid":"76561198000000000","request_id":"test-request"}}')
    assert executor._begin_auth_params(response) == {
        "client_id": 123,
        "steamid": "76561198000000000",
        "request_id": "test-request",
    }


def test_rate_limited_begin_auth_raises_too_many_requests() -> None:
    """A rate-limit body without client_id must not surface as KeyError."""
    executor: LoginExecutor = _executor()
    response: requests.Response = _response(b'{"response":{"interval":71,"extended_error_message":"Please wait and try again later."}}')
    with pytest.raises(TooManyRequests, match="too many requests"):
        executor._begin_auth_params(response)


def test_begin_auth_without_ids_reports_missing_keys() -> None:
    """An id-less body must name the missing keys instead of raising KeyError."""
    executor: LoginExecutor = _executor()
    response: requests.Response = _response(b'{"response":{"steamid":"76561198000000000"}}')
    with pytest.raises(ApiException, match="client_id"):
        executor._begin_auth_params(response)


def test_begin_auth_error_does_not_log_secret_values() -> None:
    """Key names may be logged; ids and tokens must not."""
    executor: LoginExecutor = _executor()
    response: requests.Response = _response(
        b'{"response":{"steamid":"76561198000000000","request_id":"SECRET-REQUEST-ID",'
        b'"interval":71,"extended_error_message":"Please wait."}}'
    )
    logged: list[str] = []
    sink: int = logger.add(logged.append, format="{message}")
    try:
        with pytest.raises(TooManyRequests):
            executor._begin_auth_params(response)
    finally:
        logger.remove(sink)
    assert "SECRET-REQUEST-ID" not in "\n".join(logged)


def test_poll_waits_for_refresh_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Polling must retry a token-less answer instead of raising KeyError."""
    executor: LoginExecutor = _executor()
    calls: list[str] = []

    def fake_api(
        method: str,
        service: str,
        endpoint: str,
        version: str = "v1",
        params: dict | None = None,
    ) -> requests.Response:
        calls.append(endpoint)
        if len(calls) == 1:
            return _response(b'{"response":{}}')
        return _response(b'{"response":{"refresh_token":"new-refresh"}}')

    monkeypatch.setattr(executor, "_api_call", fake_api)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    executor._pool_sessions_steam("123", "test-request")
    assert executor.refresh_token == "new-refresh"
    assert calls == ["PollAuthSessionStatus", "PollAuthSessionStatus"]


def test_poll_timeout_raises_api_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Polling without a token must give up with a clear error."""
    executor: LoginExecutor = _executor()

    def fake(*args: object, **kwargs: object) -> requests.Response:
        return _response(b'{"response":{}}')

    monkeypatch.setattr(executor, "_api_call", fake)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    with pytest.raises(ApiException, match="no refresh token"):
        executor._pool_sessions_steam("123", "test-request")
