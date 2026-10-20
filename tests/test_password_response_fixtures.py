"""Validate captured password wizard formats and reject ambiguous API values."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from src.password_changer import PasswordChanger
from src.steampy.security import (
    SteamPasswordChangeResponse,
    SteamRecoveryResponse,
    SteamRsaKeyResponse,
)

FIXTURES: Path = Path(__file__).resolve().parents[1] / "scripts" / "fixtures"


@pytest.mark.parametrize(
    "endpoint",
    [
        "AjaxSendAccountRecoveryCode",
        "AjaxPollAccountRecoveryConfirmation",
        "AjaxVerifyAccountRecoveryCode",
        "AjaxAccountRecoveryGetNextStep",
        "AjaxAccountRecoveryVerifyPassword",
    ],
)
def test_captured_recovery_responses_parse(endpoint: str) -> None:
    """Real sanitized responses must remain compatible with wizard parsing."""
    response: SteamRecoveryResponse = SteamRecoveryResponse.model_validate_json(
        (FIXTURES / f"steam_{endpoint}.success.sanitized.json").read_bytes()
    )
    assert not response.errorMsg


def test_captured_password_change_requires_credential_verification() -> None:
    """The captured navigation response allows verification without claiming a login."""
    response: SteamPasswordChangeResponse = SteamPasswordChangeResponse.model_validate_json(
        (FIXTURES / "steam_AjaxAccountRecoveryChangePassword.success.sanitized.json").read_bytes()
    )
    assert response.ready_to_verify


def test_captured_password_availability_parses() -> None:
    """Accept the boolean shape captured from Steam."""
    changer: PasswordChanger = _changer((FIXTURES / "steam_AjaxCheckPasswordAvailable.success.sanitized.json").read_bytes())
    assert changer._check_password_available("test-password") is True


@pytest.mark.parametrize("body", [b'{"available":"false"}', b'{"available":1}', b"{}"])
def test_ambiguous_password_availability_is_rejected(body: bytes) -> None:
    """Truthy strings or numbers must not authorize the password installation step."""
    assert _changer(body)._check_password_available("test-password") is False


def test_rsa_response_requires_key_fields() -> None:
    """A successful acknowledgement without an RSA key cannot be encrypted against."""
    assert _changer(b'{"success":true}')._get_rsa_key() is None


def test_captured_rsa_key_parses() -> None:
    """Check the actual public RSA response before using its key fields."""
    response: SteamRsaKeyResponse = SteamRsaKeyResponse.model_validate_json(
        (FIXTURES / "steam_getrsakey.success.sanitized.json").read_bytes()
    )
    assert response.confirmed
    assert int(response.publickey_mod, 16) > 0
    assert int(response.publickey_exp, 16) > 0


def _changer(body: bytes) -> PasswordChanger:
    """Provide a synthetic Steam response without network or account credentials."""
    import json

    response: Mock = Mock(status_code=200, content=body)
    response.json.return_value = json.loads(body)
    session: Mock = Mock()
    session.post.return_value = response
    changer: PasswordChanger = PasswordChanger.__new__(PasswordChanger)
    changer.steam_client = SimpleNamespace(_session=session)
    changer.account_context = SimpleNamespace(username="example_account")
    changer._help_session_id = lambda url: "test-csrf"
    return changer
