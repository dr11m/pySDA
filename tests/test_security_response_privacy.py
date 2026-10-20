"""Offline regressions for private confirmation responses and uncertain revocation outcomes."""

from pathlib import Path

from loguru import logger
import pytest
import requests

from src.steampy.client import SteamClient
from src.steampy.confirmation import Confirmation, ConfirmationExecutor
from src.steampy.exceptions import ConfirmationExpected
from src.steampy.security import SessionRevocationStatus


class _ResponseAdapter(requests.adapters.BaseAdapter):
    """Return one controlled response without opening a network connection."""

    def __init__(self, status: int, body: bytes, location: str = "") -> None:
        self.status: int = status
        self.body: bytes = body
        self.location: str = location
        self.requests: list[requests.PreparedRequest] = []

    def send(self, request: requests.PreparedRequest, **kwargs: object) -> requests.Response:
        """Record the actual request and provide the synthetic server response."""
        self.requests.append(request)
        response: requests.Response = requests.Response()
        response.status_code = self.status
        response._content = self.body
        response.url = request.url
        response.request = request
        if self.location:
            response.headers["Location"] = self.location
        return response

    def close(self) -> None:
        """Own no external resources."""


@pytest.mark.parametrize("status", [200, 503])
def test_confirmation_list_does_not_dump_private_response(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    """Return confirmation data to its caller without saving or logging response secrets."""
    monkeypatch.chdir(tmp_path)
    body: bytes = b'{"success":true,"conf":[{"id":"1","nonce":"SECRET-CONFIRMATION-NONCE","creator_id":"2"}]}'
    adapter: _ResponseAdapter = _ResponseAdapter(status, body)
    session: requests.Session = requests.Session()
    session.trust_env = False
    session.mount("https://", adapter)
    executor: ConfirmationExecutor = ConfirmationExecutor("c2VjcmV0", "76561198000000000", session)
    monkeypatch.setattr(executor, "CONFIRMATION_RETRY_COUNT", 1)
    logged: list[str] = []
    error_message: str = ""
    sink_id: int = logger.add(lambda message: logged.append(str(message)))
    try:
        if status == 200:
            confirmations: list[Confirmation] = executor._get_confirmations()
            assert len(confirmations) == 1
            assert confirmations[0].nonce == "SECRET-CONFIRMATION-NONCE"
        else:
            with pytest.raises(ConfirmationExpected) as captured_error:
                executor._get_confirmations()
            error_message = str(captured_error.value)
    finally:
        logger.remove(sink_id)
        session.close()

    assert not (tmp_path / "debug_confirmations_page.txt").exists()
    assert "SECRET-CONFIRMATION-NONCE" not in "\n".join(logged) + error_message
    assert len(adapter.requests) == 1


def test_confirmation_acknowledgement_does_not_log_response_payload() -> None:
    """The acknowledgement may include sensitive fields that must stay out of logs."""
    body: bytes = b'{"success":true,"token":"SECRET-CONFIRMATION-RESPONSE"}'
    adapter: _ResponseAdapter = _ResponseAdapter(200, body)
    session: requests.Session = requests.Session()
    session.trust_env = False
    session.mount("https://", adapter)
    executor: ConfirmationExecutor = ConfirmationExecutor("c2VjcmV0", "76561198000000000", session)
    logged: list[str] = []
    sink_id: int = logger.add(lambda message: logged.append(str(message)))
    try:
        result: dict[str, object] = executor._send_confirmation(Confirmation("1", "nonce", 2))
    finally:
        logger.remove(sink_id)
        session.close()

    assert result["success"] is True
    assert "SECRET-CONFIRMATION-RESPONSE" not in "\n".join(logged)
    assert len(adapter.requests) == 1


@pytest.mark.parametrize("status", [302, 303])
@pytest.mark.parametrize("location", ["/twofactor/manage", "/login/"])
def test_revocation_redirect_is_uncertain_without_acknowledgement(status: int, location: str) -> None:
    """A redirect after the POST proves neither success nor rejection and must not be followed."""
    adapter: _ResponseAdapter = _ResponseAdapter(status, b"", location)
    client: SteamClient = SteamClient.__new__(SteamClient)
    client.username = "steam_login"
    client.steam_id = "76561198000000000"
    client.request_timeout = (1.0, 1.0)
    client._session = requests.Session()
    client._session.trust_env = False
    client._session.cookies.set("sessionid", "session", domain="store.steampowered.com")
    client._session.cookies.set("steamLoginSecure", "76561198000000000%7C%7Ctoken", domain="store.steampowered.com")
    client._session.mount("https://", adapter)
    try:
        result: SessionRevocationStatus = client.revoke_all_sessions()
    finally:
        client._session.close()

    assert result is SessionRevocationStatus.UNKNOWN
    assert len(adapter.requests) == 1
    assert adapter.requests[0].method == "POST"
