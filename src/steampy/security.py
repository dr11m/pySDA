"""Validated responses and outcomes for Steam account security actions."""

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, StrictBool
from requests import PreparedRequest, Request, Session
from urllib.parse import unquote


class SteamSecurityResponse(BaseModel):
    """Require an explicit Steam acknowledgement instead of accepting HTTP 200."""

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, hide_input_in_errors=True)

    success: StrictBool | Literal[0, 1]
    errorMsg: str | None = None

    @property
    def confirmed(self) -> bool:
        """Return whether Steam explicitly accepted the action without an error."""
        return bool(self.success) and not self.errorMsg


class SteamRecoveryResponse(BaseModel):
    """Validate the optional acknowledgement and error used by the recovery wizard."""

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, hide_input_in_errors=True)

    success: StrictBool | Literal[0, 1] | None = None
    errorMsg: str | None = None


class SteamPasswordAvailabilityResponse(BaseModel):
    """Require the boolean availability field observed in Steam's response."""

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, hide_input_in_errors=True)

    available: StrictBool


class SteamRsaKeyResponse(SteamSecurityResponse):
    """Require the complete RSA key before attempting password encryption."""

    publickey_mod: str
    publickey_exp: str
    timestamp: str


class SteamPasswordChangeResponse(SteamRecoveryResponse):
    """Parse the navigation or acknowledgement returned by Steam's password wizard."""

    hash: str | None = None
    html: str | None = None

    @property
    def ready_to_verify(self) -> bool:
        """Allow a credential check only after a recognized, non-rejected wizard response."""
        if self.errorMsg or (self.success is not None and not self.success):
            return False
        return bool(self.success or self.hash or self.html)


def account_session_id(session: Session, steam_id: str, url: str) -> str | None:
    """Return a CSRF cookie only if the actual destination authenticates the expected account."""
    request: PreparedRequest = session.prepare_request(Request("POST", url))
    cookies: list[tuple[str, str]] = [
        (name.strip(), value)
        for part in request.headers.get("Cookie", "").split(";")
        if "=" in part
        for name, value in [part.split("=", 1)]
    ]
    login_ids: set[str] = {unquote(value).split("||", 1)[0] for name, value in cookies if name == "steamLoginSecure"}
    session_ids: set[str] = {value for name, value in cookies if name == "sessionid"}
    if login_ids == {str(steam_id)} and len(session_ids) == 1:
        return next(iter(session_ids)) or None
    return None


class SessionRevocationStatus(str, Enum):
    """Distinguish a confirmed result from rejection and an uncertain request."""

    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SessionRevocationResult:
    """Describe the remote result and cleanup of this account's local sessions."""

    status: SessionRevocationStatus
    local_cleanup_complete: bool
