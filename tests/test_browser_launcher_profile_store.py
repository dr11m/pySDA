"""Tests for browser profile session verification markers."""

from browser_launcher.profile_store import SESSION_VERIFIED_FILE, ProfileStore


def test_profile_session_verification_marker(tmp_path) -> None:
    """Verified session marker should be created and cleared."""
    store = ProfileStore(root_dir=tmp_path)

    assert store.has_verified_session("acc1") is False

    store.mark_session_verified("acc1")
    assert store.has_verified_session("acc1") is True
    assert (tmp_path / "acc1" / SESSION_VERIFIED_FILE).exists()

    store.clear_session_verification("acc1")
    assert store.has_verified_session("acc1") is False
