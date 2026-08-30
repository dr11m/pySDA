"""Persistent browser profile paths per account."""

from datetime import datetime, timezone
from pathlib import Path

SESSION_VERIFIED_FILE = ".session_verified"
DEFAULT_PROFILE_ROOT = Path("browser_profiles")


class ProfileStore:
    """Manage per-account Chromium user data directories."""

    def __init__(self, root_dir: Path | None = None):
        self.root_dir = (root_dir or DEFAULT_PROFILE_ROOT).resolve()

    def get_profile_dir(self, account_name: str) -> Path:
        """Return profile directory for an account, creating it if needed."""
        profile_dir = self.root_dir / account_name
        profile_dir.mkdir(parents=True, exist_ok=True)
        return profile_dir

    def is_new_profile(self, account_name: str) -> bool:
        """Return True when profile directory has not been initialized yet."""
        profile_dir = self.root_dir / account_name
        return not profile_dir.exists() or not any(profile_dir.iterdir())

    def has_verified_session(self, account_name: str) -> bool:
        """Return True when profile previously had a verified Steam login."""
        marker_path = self.root_dir / account_name / SESSION_VERIFIED_FILE
        return marker_path.exists()

    def mark_session_verified(self, account_name: str) -> None:
        """Persist marker that profile has an active seeded Steam session."""
        profile_dir = self.get_profile_dir(account_name)
        marker_path = profile_dir / SESSION_VERIFIED_FILE
        marker_path.write_text(
            datetime.now(timezone.utc).isoformat(),
            encoding="utf-8",
        )

    def clear_session_verification(self, account_name: str) -> None:
        """Remove verified-session marker for an account profile."""
        marker_path = self.root_dir / account_name / SESSION_VERIFIED_FILE
        if marker_path.exists():
            marker_path.unlink()
