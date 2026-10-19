"""Offline regressions for manual security actions on one selected account."""

from pathlib import Path
import pickle
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs

import pytest
import requests
import yaml
from bs4 import BeautifulSoup
from loguru import logger

from src.cli.config_manager import ConfigManager
from src.cli.menus import SettingsMenu
from src.cookie_manager import CookieManager
from src.password_changer import PasswordChanger
from src.steampy.client import SteamClient
from src.steampy.login import LoginExecutor
from src.steampy.security import SessionRevocationResult, SessionRevocationStatus, account_session_id
from src.utils.delayed_http_adapter import SteamHttpSettings
from src.implementations.cookie_storage.json_storage.storage import JsonCookieStorage


def _password_changer(tmp_path: Path) -> PasswordChanger:
    """Use real configuration persistence without constructing network clients."""
    config_path: Path = tmp_path / "config.yaml"
    config_path.write_text(
        "# preserve this comment\naccounts:\n"
        "  selected_alias:\n    username: steam_login\n    password: old-password\n"
        "  other_alias:\n    username: other_login\n    password: other-password\n"
        "request_read_timeout_seconds: 30\n",
        encoding="utf-8",
    )
    config: ConfigManager = ConfigManager(str(config_path))
    assert config.load_config()
    assert config.select_account("selected_alias")
    manager: CookieManager = CookieManager.__new__(CookieManager)
    manager.password = "old-password"
    manager.username = "steam_login"
    manager.accounts_dir = tmp_path
    manager.session_file = tmp_path / "steam_login.pkl"
    manager.storage = JsonCookieStorage.__new__(JsonCookieStorage)
    manager.storage.storage_dir = tmp_path
    manager.cookies_cache = {"old": "cookies"}
    manager.last_update = None
    manager.client = _security_client(_SteamResponseAdapter(200, b""))
    manager.client._password = "old-password"
    manager.steam_client = _security_client(_SteamResponseAdapter(200, b""))
    manager.steam_client._password = "old-password"
    manager.steam_client.storage = manager.storage
    manager.steam_client._session.cookies.set("sessionid", "help-session", domain="help.steampowered.com")
    manager.steam_client._session.cookies.set("steamLoginSecure", "76561198000000000%7C%7Chelp-token", domain="help.steampowered.com")
    context: Any = SimpleNamespace(account_name="selected_alias", username="steam_login", config_manager=config, cookie_manager=manager)
    changer: PasswordChanger = PasswordChanger(context)
    changer.steam_client = manager.steam_client
    changer.recovery_params = {"s": "test-recovery", "account": "steam_login", "reset": "1", "lost": "0", "issueid": "406"}
    return changer


@pytest.mark.parametrize("body", [b"<html>Sign in</html>", b"{}", b'{"success":false}', b'{"success":0}'])
def test_password_change_rejects_unconfirmed_http_200(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    """A login page or an explicit failure must not overwrite the password."""
    changer: PasswordChanger = _password_changer(tmp_path)
    response: requests.Response = requests.Response()
    response.status_code = 200
    response._content = body
    changer.steam_client._session.post = lambda *args, **kwargs: response
    changer.steam_client._get_session_id = lambda: "test-session"
    monkeypatch.setattr(changer, "_check_password_available", lambda password: True)
    monkeypatch.setattr(changer, "_get_rsa_key", lambda: {"timestamp": "10"})
    monkeypatch.setattr(changer, "_encrypt_password", lambda password, key: "test-ciphertext")

    assert changer._set_new_password("new-password") is False
    assert changer.account_context.config_manager.accounts_settings["selected_alias"]["password"] == "old-password"


def test_confirmed_password_survives_reload_for_only_selected_account(tmp_path: Path) -> None:
    """Changing the password must survive restart and update both resident clients."""
    changer: PasswordChanger = _password_changer(tmp_path)

    assert changer._update_configuration("new-password") is True

    config_path: Path = tmp_path / "config.yaml"
    on_disk: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert on_disk["accounts"]["selected_alias"]["password"] == "new-password"
    assert on_disk["accounts"]["other_alias"]["password"] == "other-password"
    assert on_disk["request_read_timeout_seconds"] == 30
    assert config_path.read_text(encoding="utf-8").startswith("# preserve this comment")
    assert changer.account_context.cookie_manager.password == "new-password"
    assert changer.account_context.cookie_manager.client._password == "new-password"
    assert changer.account_context.cookie_manager.steam_client._password == "new-password"


def test_password_update_refreshes_cloned_configuration_views(tmp_path: Path) -> None:
    """A worker config clone must not retain the old password in its full document."""
    changer: PasswordChanger = _password_changer(tmp_path)
    config: ConfigManager = changer.account_context.config_manager.clone()
    config.select_account("selected_alias")
    config.update_account_password("selected_alias", "new-password")
    assert config.get_full_config()["accounts"]["selected_alias"]["password"] == "new-password"
    assert config.get("password") == "new-password"


def test_failed_config_replace_keeps_old_file_and_runtime_password(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An interrupted file replacement must not leave a partial config or runtime drift."""
    changer: PasswordChanger = _password_changer(tmp_path)
    original: bytes = (tmp_path / "config.yaml").read_bytes()

    def fail_replace(*args: object) -> None:
        raise PermissionError("simulated file replacement failure")

    monkeypatch.setattr("os.replace", fail_replace)

    assert changer._update_configuration("new-password") is False
    assert (tmp_path / "config.yaml").read_bytes() == original
    assert changer.account_context.cookie_manager.password == "old-password"


@pytest.mark.parametrize("body", [b'{"hash":"wizard/HelpWithLogin"}', b'{"html":"<div>Next page</div>"}'])
def test_native_password_wizard_navigation_requires_new_password_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    """Steam's current hash/html responses need a credential check, not a guessed success field."""
    changer: PasswordChanger = _password_changer(tmp_path)
    response: requests.Response = requests.Response()
    response.status_code = 200
    response._content = body
    changer.steam_client._session.post = lambda *args, **kwargs: response
    changer.steam_client._get_session_id = lambda: "test-session"
    monkeypatch.setattr(changer, "_check_password_available", lambda password: True)
    monkeypatch.setattr(changer, "_get_rsa_key", lambda: {"timestamp": "10"})
    monkeypatch.setattr(changer, "_encrypt_password", lambda password, key: "test-ciphertext")
    attempts: list[str] = []

    def check_password(password: str) -> bool:
        attempts.append(password)
        changer.steam_client._session = requests.Session()
        changer.steam_client._session.cookies.set("sessionid", "verified-session", domain="store.steampowered.com")
        return True

    monkeypatch.setattr(changer.steam_client, "login_with_password", check_password, raising=False)
    assert changer._set_new_password("new-password") is True
    assert attempts == ["new-password"]


class _SteamResponseAdapter(requests.adapters.BaseAdapter):
    """Exercise request preparation and redirect handling without any network."""

    def __init__(self, status: int, body: bytes, location: str = "", timeout: bool = False) -> None:
        self.status: int = status
        self.body: bytes = body
        self.location: str = location
        self.timeout: bool = timeout
        self.requests: list[requests.PreparedRequest] = []

    def send(self, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:
        self.requests.append(request)
        assert len(self.requests) == 1, "A destructive POST must never be retried or followed"
        if self.timeout:
            raise requests.Timeout("simulated timeout")
        response: requests.Response = requests.Response()
        response.status_code = self.status
        response._content = self.body
        response.url = request.url
        response.request = request
        if self.location:
            response.headers["Location"] = self.location
        return response

    def close(self) -> None:
        """No external resource is owned by this adapter."""


def _security_client(adapter: _SteamResponseAdapter) -> SteamClient:
    """Use a real Requests session with an in-memory HTTP boundary."""
    client: SteamClient = SteamClient.__new__(SteamClient)
    client.username = "steam_login"
    client.steam_id = "76561198000000000"
    client.request_timeout = (1.0, 1.0)
    client._session = requests.Session()
    client._session.trust_env = False
    client._session.cookies.set("sessionid", "test-session", domain="store.steampowered.com")
    client._session.cookies.set("steamLoginSecure", "76561198000000000%7C%7Ctest-token", domain="store.steampowered.com")
    client._session.mount("https://", adapter)
    client.refresh_token = "test-refresh-token"
    client.was_login_executed = True
    client.storage = None
    return client


@pytest.mark.parametrize("accepted", [True, False])
def test_password_verification_uses_a_fresh_session_and_does_not_reuse_refresh_token(
    monkeypatch: pytest.MonkeyPatch, accepted: bool
) -> None:
    """Only an actual credential login can prove the newly entered password is active."""
    client: SteamClient = _security_client(_SteamResponseAdapter(200, b""))
    client.steam_guard = {"shared_secret": "test-shared-secret", "identity_secret": "test-identity-secret"}
    client._http_settings = SteamHttpSettings(
        min_request_delay_ms=0,
        request_connect_timeout_seconds=1,
        request_read_timeout_seconds=1,
        check_ip_on_every_steam_request=False,
    )
    old_session: requests.Session = client._session
    attempts: list[str] = []

    def executor(steam_id: str, username: str, password: str, shared_secret: str, session: requests.Session) -> Any:
        assert steam_id == "76561198000000000"
        assert username == "steam_login"
        assert not session.cookies
        attempts.append(password)

        def login() -> tuple[requests.Session, str]:
            if not accepted:
                raise requests.HTTPError("simulated rejected login")
            session.cookies.set("sessionid", "new-session", domain="store.steampowered.com")
            session.cookies.set("steamLoginSecure", "76561198000000000%7C%7Cnew-token", domain="store.steampowered.com")
            return session, "new-refresh-token"

        return SimpleNamespace(login=login)

    monkeypatch.setattr("src.steampy.client.LoginExecutor", executor)

    assert client.login_with_password("new-password") is accepted
    assert attempts == ["new-password"]
    if accepted:
        assert client._session is not old_session
        assert client.refresh_token == "new-refresh-token"
    else:
        assert client._session is old_session
        assert client.refresh_token == "test-refresh-token"


def test_verified_session_replaces_only_selected_cache_and_survives_config_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After remote verification, runtime and saved sessions must reflect the real new password."""
    changer: PasswordChanger = _password_changer(tmp_path)
    manager: CookieManager = changer.account_context.cookie_manager
    old_client: SteamClient = manager.client
    other_file: Path = tmp_path / "other_login.pkl"
    other_file.write_bytes(b"other session")
    manager.steam_client._session.cookies.set("sessionid", "verified-session", domain="store.steampowered.com")
    manager.steam_client.refresh_token = "verified-refresh"
    manager.steam_client._password = "new-password"

    assert manager.save_verified_session("new-password") is True

    def fail_update(*args: object) -> None:
        raise PermissionError("simulated config replacement failure")

    monkeypatch.setattr(changer.account_context.config_manager, "update_account_password", fail_update)
    assert changer._update_configuration("new-password") is False
    assert manager.password == manager.client._password == manager.steam_client._password == "new-password"
    assert manager.client is manager.steam_client
    assert not old_client._session.cookies
    session, token = pickle.loads(manager.session_file.read_bytes())
    assert session.cookies.get("sessionid", domain="store.steampowered.com") == "verified-session"
    assert token == "verified-refresh"
    assert manager.storage.load_cookies("steam_login") == manager.cookies_cache
    assert manager.last_update.tzinfo is not None
    assert other_file.read_bytes() == b"other session"
    assert yaml.safe_load((tmp_path / "config.yaml").read_text())["accounts"]["selected_alias"]["password"] == "old-password"


def test_session_save_failure_preserves_existing_pickle_and_reports_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An interrupted session write must preserve the previous complete file."""
    changer: PasswordChanger = _password_changer(tmp_path)
    manager: CookieManager = changer.account_context.cookie_manager
    manager.session_file.write_bytes(b"previous complete pickle")

    def fail_replace(*args: object) -> None:
        raise PermissionError("simulated session replacement failure")

    monkeypatch.setattr("os.replace", fail_replace)
    assert manager.save_verified_session("new-password") is False
    assert manager.session_file.read_bytes() == b"previous complete pickle"
    assert manager.password == "new-password"


@pytest.mark.parametrize(
    "status,body,location,expected",
    [
        (302, b"", "/twofactor/manage", SessionRevocationStatus.CONFIRMED),
        (302, b"", "/login/", SessionRevocationStatus.REJECTED),
        (302, b"", "https://example.com/twofactor/manage", SessionRevocationStatus.UNKNOWN),
        (302, b"", "https://[", SessionRevocationStatus.UNKNOWN),
        (200, b'{"success":1}', "", SessionRevocationStatus.CONFIRMED),
        (200, b'{"success":false}', "", SessionRevocationStatus.REJECTED),
        (200, b'{"success":"1"}', "", SessionRevocationStatus.UNKNOWN),
        (200, b"{}", "", SessionRevocationStatus.UNKNOWN),
        (200, b"<html>Sign in</html>", "", SessionRevocationStatus.UNKNOWN),
        (403, b"", "", SessionRevocationStatus.REJECTED),
        (500, b"", "", SessionRevocationStatus.UNKNOWN),
    ],
)
def test_revoke_sessions_classifies_steam_response_without_following_redirects(
    status: int, body: bytes, location: str, expected: SessionRevocationStatus
) -> None:
    """A login redirect, malformed body or server failure must not report success."""
    adapter: _SteamResponseAdapter = _SteamResponseAdapter(status, body, location)
    client: SteamClient = _security_client(adapter)

    assert client.revoke_all_sessions() is expected
    assert len(adapter.requests) == 1
    assert adapter.requests[0].url == "https://store.steampowered.com/twofactor/manage_action"
    fixture: Path = Path(__file__).parents[1] / "scripts/fixtures/steam_twofactor_manage.form.sanitized.html"
    form = BeautifulSoup(fixture.read_text(encoding="utf-8"), "html.parser").find("form")
    assert form["method"] == adapter.requests[0].method
    assert adapter.requests[0].url == "https://store.steampowered.com" + form["action"]
    native_fields: dict[str, list[str]] = {field["name"]: [field["value"]] for field in form.find_all("input")}
    native_fields["sessionid"] = ["test-session"]
    assert parse_qs(adapter.requests[0].body) == native_fields


def test_revoke_timeout_is_uncertain_and_is_not_retried() -> None:
    """A timeout may occur after Steam accepted the operation."""
    adapter: _SteamResponseAdapter = _SteamResponseAdapter(200, b"", timeout=True)
    client: SteamClient = _security_client(adapter)
    assert client.revoke_all_sessions() is SessionRevocationStatus.UNKNOWN
    assert len(adapter.requests) == 1


def test_revoke_refuses_cookies_for_a_different_account() -> None:
    """A mismatched cookie jar must never sign out another Steam account."""
    adapter: _SteamResponseAdapter = _SteamResponseAdapter(200, b'{"success":1}')
    client: SteamClient = _security_client(adapter)
    client.steam_id = "76561198000000001"
    assert client.revoke_all_sessions() is SessionRevocationStatus.REJECTED
    assert not adapter.requests


@pytest.mark.parametrize("domain", ["help.steampowered.com", ""])
def test_password_session_rejects_foreign_cookies_sent_to_help(domain: str) -> None:
    """Check the cookies Requests would actually send, including hostless cookies."""
    client: SteamClient = _security_client(_SteamResponseAdapter(200, b""))
    client._session.cookies.set("steamLoginSecure", "76561198000000001%7C%7Cforeign", domain=domain)
    client._session.cookies.set("sessionid", "help-session", domain="help.steampowered.com")
    assert account_session_id(client._session, client.steam_id, "https://help.steampowered.com/en/wizard/") is None


def test_security_requires_cookies_for_the_destination_and_unambiguous_session_id() -> None:
    """Community-only authentication cannot authorize a Store security action."""
    session: requests.Session = requests.Session()
    session.cookies.set("steamLoginSecure", "76561198000000000%7C%7Ctoken", domain="steamcommunity.com")
    session.cookies.set("sessionid", "community-session", domain="steamcommunity.com")
    url: str = "https://store.steampowered.com/twofactor/manage_action"
    assert account_session_id(session, "76561198000000000", url) is None
    session.cookies.set("steamLoginSecure", "76561198000000000%7C%7Ctoken", domain="store.steampowered.com")
    session.cookies.set("sessionid", "store-session", domain="store.steampowered.com")
    assert account_session_id(session, "76561198000000000", url) == "store-session"
    session.cookies.set("sessionid", "conflicting-session")
    assert account_session_id(session, "76561198000000000", url) is None


def test_password_preflight_requires_shared_secret(tmp_path: Path) -> None:
    """Reject an account before changing credentials if fresh verification cannot run."""
    changer: PasswordChanger = _password_changer(tmp_path)
    changer.steam_client.steam_guard = {"identity_secret": "test-identity-secret"}
    changer.account_context.config_manager.accounts_settings["selected_alias"]["steam_id"] = "76561198000000000"
    assert changer._verify_steam_guard_data() is False


def test_rsa_key_uses_steam_username_instead_of_account_alias(tmp_path: Path) -> None:
    """A local alias must never be sent as the Steam login."""
    changer: PasswordChanger = _password_changer(tmp_path)
    submitted: list[dict[str, str]] = []

    def post(url: str, data: dict[str, str]) -> Any:
        submitted.append(data)
        return SimpleNamespace(status_code=200, json=lambda: {"publickey_mod": "ab", "publickey_exp": "01", "timestamp": "10"})

    changer.steam_client._session.post = post
    changer.steam_client._get_session_id = lambda: "test-session"
    assert changer._get_rsa_key() is not None
    assert submitted[0]["username"] == "steam_login"


def test_password_wizard_sends_csrf_for_help_instead_of_store(tmp_path: Path) -> None:
    """Imported sessions can have different CSRF cookies for different Steam services."""
    changer: PasswordChanger = _password_changer(tmp_path)
    adapter: _SteamResponseAdapter = _SteamResponseAdapter(200, b'{"success":true}')
    changer.steam_client._session.mount("https://", adapter)
    changer.steam_client._session.cookies.set("sessionid", "different-store-session", domain="store.steampowered.com")
    assert changer._send_recovery_request() is True
    assert parse_qs(adapter.requests[0].body)["sessionid"] == ["help-session"]


@pytest.mark.parametrize("method", ["_get_next_step", "_verify_old_password"])
def test_password_wizard_preserves_native_change_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    """A normal password change must not replace Steam's lost=0 with the old hardcoded lost=2."""
    changer: PasswordChanger = _password_changer(tmp_path)
    adapter: _SteamResponseAdapter = _SteamResponseAdapter(200, b'{"success":true}')
    changer.steam_client._session.mount("https://", adapter)
    monkeypatch.setattr(changer, "_get_rsa_key", lambda: {"timestamp": "10"})
    monkeypatch.setattr(changer, "_encrypt_password", lambda password, key: "ciphertext")
    assert getattr(changer, method)() is True
    payload: dict[str, list[str]] = parse_qs(adapter.requests[0].body)
    assert payload["lost"] == ["0"]
    assert payload["reset"] == ["1"]


@pytest.mark.parametrize("reset,lost", [("0", "0"), ("1", "2"), ("1", "8"), ("", "0")])
def test_password_change_refuses_recovery_route_before_any_submission(tmp_path: Path, reset: str, lost: str) -> None:
    """The CLI must not submit a password under a lost-access or unknown wizard route."""
    changer: PasswordChanger = _password_changer(tmp_path)
    adapter: _SteamResponseAdapter = _SteamResponseAdapter(200, b'{"success":true}')
    changer.steam_client._session.mount("https://", adapter)
    changer.recovery_params["reset"] = reset
    changer.recovery_params["lost"] = lost
    assert changer._set_new_password("new-password") is False
    assert not adapter.requests


@pytest.mark.parametrize("link_mode,expected", [("native", True), ("lost-access", False), ("missing", False)])
def test_password_initialization_requires_native_change_link(tmp_path: Path, link_mode: str, expected: bool) -> None:
    """Read the exact route from the native link instead of inventing missing flags."""
    changer: PasswordChanger = _password_changer(tmp_path)
    fixture: Path = Path(__file__).parents[1] / "scripts/fixtures/steam_password_change.link.sanitized.html"
    html: str = fixture.read_text(encoding="utf-8")
    if link_mode == "lost-access":
        html = html.replace("lost=0", "lost=2")
    elif link_mode == "missing":
        html = "<p>No recognized continuation</p>"
    response: requests.Response = requests.Response()
    response.status_code = 200
    response._content = ("steam_login\n" + html).encode()
    response.url = "https://help.steampowered.com/en/wizard/HelpWithLoginInfoSendCode/?s=REDACTED&account=REDACTED&reset=1&issueid=406"
    response.history = [requests.Response()]
    changer.steam_client._session.get = lambda *args, **kwargs: response
    assert changer._initialize_recovery(changer.steam_client.steam_id) is expected
    if expected:
        assert changer.recovery_params["lost"] == "0"


@pytest.mark.parametrize(
    "method", ["_send_recovery_request", "_poll_confirmation", "_verify_recovery_code", "_get_next_step", "_verify_old_password"]
)
def test_password_wizard_does_not_treat_non_json_as_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    """An expired session returning a login page must stop the wizard."""
    changer: PasswordChanger = _password_changer(tmp_path)
    response: requests.Response = requests.Response()
    response.status_code = 200
    response._content = b"<html>Sign in</html>"
    changer.steam_client._session.post = lambda *args, **kwargs: response
    changer.steam_client._session.get = lambda *args, **kwargs: response
    changer.steam_client._get_session_id = lambda: "test-session"
    monkeypatch.setattr(changer, "_get_rsa_key", lambda: {"timestamp": "10"})
    monkeypatch.setattr(changer, "_encrypt_password", lambda password, key: "ciphertext")
    assert getattr(changer, method)() is False


def test_password_error_does_not_log_exception_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requests may include recovery tokens in exceptions; display only the error class."""
    changer: PasswordChanger = _password_changer(tmp_path)
    output: list[str] = []

    def fail_post(*args: object, **kwargs: object) -> None:
        raise requests.Timeout("https://help.steampowered.com/?s=SECRET-RECOVERY-TOKEN")

    changer.steam_client._session.post = fail_post
    changer.steam_client._get_session_id = lambda: "test-session"
    monkeypatch.setattr("src.password_changer.print_and_log", lambda message, *args: output.append(message))
    assert changer._send_recovery_request() is False
    assert "SECRET-RECOVERY-TOKEN" not in "\n".join(output)


def test_fresh_login_failure_does_not_log_auth_response_or_request_secrets(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Credential verification must not leak request IDs or tokens through the existing login executor."""
    executor: LoginExecutor = LoginExecutor("76561198000000000", "steam_login", "test-password", "test-shared-secret", requests.Session())
    response: requests.Response = requests.Response()
    response.status_code = 200
    response._content = b'{"response":{"client_id":"id","steamid":"76561198000000000","request_id":"SECRET-AUTH-RESPONSE"}}'
    monkeypatch.setattr(executor, "_send_login_request", lambda: response)
    monkeypatch.setattr("src.steampy.login.guard.generate_one_time_code", lambda secret: "test-code")

    def fail_api(*args: object, **kwargs: object) -> None:
        raise requests.Timeout("https://api.steampowered.com/?token=SECRET-REQUEST-TOKEN")

    monkeypatch.setattr(executor, "_api_call", fail_api)
    logged: list[str] = []
    sink: int = logger.add(logged.append, format="{message}")
    try:
        with pytest.raises(requests.Timeout):
            executor.login()
    finally:
        logger.remove(sink)
    captured = capsys.readouterr()
    output: str = "\n".join(logged) + captured.out + captured.err
    assert "SECRET-AUTH-RESPONSE" not in output
    assert "SECRET-REQUEST-TOKEN" not in output


@pytest.mark.parametrize("status", [200, 500, 403])
def test_revoke_cleans_only_the_selected_account_when_request_is_not_rejected(tmp_path: Path, status: int) -> None:
    """Remote success or uncertainty discards local credentials without touching other accounts or maFiles."""
    adapter: _SteamResponseAdapter = _SteamResponseAdapter(status, b'{"success":1}')
    client: SteamClient = _security_client(adapter)
    storage: JsonCookieStorage = JsonCookieStorage.__new__(JsonCookieStorage)
    storage.storage_dir = tmp_path
    storage.save_cookies("steam_login", {"sessionid": "test-session"})
    storage.save_cookies("other_login", {"sessionid": "other-session"})
    session_file: Path = tmp_path / "steam_login.pkl"
    session_file.write_bytes(b"saved selected session")
    other_file: Path = tmp_path / "other_login.pkl"
    other_file.write_bytes(b"saved other session")
    mafile: Path = tmp_path / "steam_login.maFile"
    mafile.write_bytes(b"authenticator must stay unchanged")
    manager: CookieManager = CookieManager.__new__(CookieManager)
    manager.username = "steam_login"
    manager.storage = storage
    manager.session_file = session_file
    manager.steam_client = client
    manager.client = client
    manager.cookies_cache = {"cached": "secret"}
    manager.last_update = None
    manager.get_steam_client = lambda: client

    result = manager.revoke_all_sessions()

    if status == 403:
        assert result.status is SessionRevocationStatus.REJECTED
        assert session_file.exists()
        assert storage.load_cookies("steam_login") is not None
        assert client.refresh_token == "test-refresh-token"
    else:
        assert result.local_cleanup_complete is True
        assert not session_file.exists()
        assert storage.load_cookies("steam_login") is None
        assert manager.cookies_cache is None
        assert manager.steam_client is None
        assert client.refresh_token is None
        assert not client._session.cookies
    assert other_file.read_bytes() == b"saved other session"
    assert storage.load_cookies("other_login") == {"sessionid": "other-session"}
    assert mafile.read_bytes() == b"authenticator must stay unchanged"


@pytest.mark.parametrize("answer", ["n", ""])
def test_settings_cancel_does_not_revoke_or_clear_selection(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    """Cancellation through the real menu must not perform any account operation."""

    def unexpected_revoke() -> None:
        raise AssertionError("Cancelled action attempted to revoke sessions")

    context: Any = SimpleNamespace(
        account_name="selected_alias", username="steam_login", cookie_manager=SimpleNamespace(revoke_all_sessions=unexpected_revoke)
    )
    cli: Any = SimpleNamespace(active_account_context=context, selected_account_name="selected_alias")
    menu: SettingsMenu = SettingsMenu(cli)
    menu.setup_menu()
    monkeypatch.setattr("builtins.input", lambda prompt: answer)

    item = menu.get_item("4")
    assert item is not None
    assert item.execute() is False
    assert cli.active_account_context is context
    assert cli.selected_account_name == "selected_alias"


@pytest.mark.parametrize("status", list(SessionRevocationStatus))
def test_settings_revoke_releases_selection_without_reauthentication(
    monkeypatch: pytest.MonkeyPatch, status: SessionRevocationStatus
) -> None:
    """After a sent action the CLI must not immediately recreate a revoked session."""
    context: Any = SimpleNamespace(
        account_name="selected_alias",
        username="steam_login",
        cookie_manager=SimpleNamespace(revoke_all_sessions=lambda: SessionRevocationResult(status, True)),
    )
    cli: Any = SimpleNamespace(active_account_context=context, selected_account_name="selected_alias")
    menu: SettingsMenu = SettingsMenu(cli)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    menu.logout_all_sessions()

    if status is SessionRevocationStatus.REJECTED:
        assert cli.active_account_context is context
        assert cli.selected_account_name == "selected_alias"
    else:
        assert cli.active_account_context is None
        assert cli.selected_account_name is None
        assert menu.running is False
