"""Keep the read-only password collector bound to the configured account route."""

from pathlib import Path
import pickle
from types import SimpleNamespace
from typing import Any

import pytest
import requests
import yaml

from scripts.fetch_password_flow import fetch_password_flow


@pytest.mark.parametrize("foreign", [False, True])
def test_capture_uses_current_route_and_checks_cookie_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign: bool) -> None:
    """Saved proxies and environment variables cannot change the account's current route."""
    monkeypatch.chdir(tmp_path)
    selected_id: str = "76561198000000000"
    config: dict[str, Any] = {
        "accounts": {"alias": {"username": "example_account", "steam_id": selected_id}},
        "proxy_provider": {"module_path": "test_provider", "class_name": "TestProvider"},
        "min_request_delay_ms": 0,
        "request_connect_timeout_seconds": 2,
        "request_read_timeout_seconds": 3,
        "check_ip_on_every_steam_request": False,
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    saved: requests.Session = requests.Session()
    saved.proxies = {"http": "http://old.invalid:80", "https": "http://old.invalid:80"}
    saved.cookies.set("sessionid", "test-csrf", domain="help.steampowered.com")
    owner: str = "76561198000000099" if foreign else selected_id
    saved.cookies.set("steamLoginSecure", f"{owner}%7C%7Ctest-token", domain="help.steampowered.com")
    session_path: Path = tmp_path / "example_account.pkl"
    session_path.write_bytes(pickle.dumps((saved, "test-refresh")))
    original: bytes = session_path.read_bytes()
    route: dict[str, str] = {"http": "http://current.invalid:8080", "https": "http://current.invalid:8080"}
    monkeypatch.setenv("HTTPS_PROXY", "http://environment.invalid:80")
    provider_accounts: list[str] = []

    def get_proxy(account: str) -> dict[str, str]:
        provider_accounts.append(account)
        return route

    monkeypatch.setattr("scripts.fetch_password_flow.create_instance_from_config", lambda settings: SimpleNamespace(get_proxy=get_proxy))
    calls: list[requests.PreparedRequest] = []

    def send(adapter: requests.adapters.HTTPAdapter, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:
        calls.append(request)
        assert request.method == "GET"
        assert kwargs["proxies"] == route
        assert kwargs["timeout"] == (2, 3)
        response: requests.Response = requests.Response()
        response.status_code = 200
        response.url = request.url
        response._content = b"<html>private original response</html>"
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    output: Path = tmp_path / "private"
    if foreign:
        with pytest.raises(ValueError, match="configured account"):
            fetch_password_flow("alias", session_path, output)
        assert calls == []
        assert not output.exists()
    else:
        raw_path: Path = fetch_password_flow("alias", session_path, output)
        assert raw_path.read_bytes() == b"<html>private original response</html>"
        assert len(calls) == 1
    assert provider_accounts == ["alias"]
    assert session_path.read_bytes() == original
