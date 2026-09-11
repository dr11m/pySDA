"""Tests for steam-browser extension selection menu."""

from browser_launcher.extension_menu import select_extensions
from browser_launcher.extensions import ExtensionInfo

AVAILABLE = [
    ExtensionInfo(name="sih", path="/ext/sih"),
    ExtensionInfo(name="trader", path="/ext/trader"),
]


def test_extension_menu_without_extensions(monkeypatch) -> None:
    """Option 1 should launch without extensions."""
    monkeypatch.setattr("builtins.input", lambda _: "1")

    selection = select_extensions(AVAILABLE)

    assert selection.cancelled is False
    assert selection.extension_paths == []


def test_extension_menu_picks_chosen_extension(monkeypatch) -> None:
    """Option 3 should load the second extension."""
    monkeypatch.setattr("builtins.input", lambda _: "3")

    selection = select_extensions(AVAILABLE)

    assert selection.cancelled is False
    assert selection.extension_paths == ["/ext/trader"]


def test_extension_menu_back_cancels(monkeypatch) -> None:
    """Option 0 should go back to the account list."""
    monkeypatch.setattr("builtins.input", lambda _: "0")

    selection = select_extensions(AVAILABLE)

    assert selection.cancelled is True


def test_extension_menu_retries_after_invalid_input(monkeypatch) -> None:
    """Invalid input should re-prompt instead of deciding."""
    answers = iter(["9", "abc", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    selection = select_extensions(AVAILABLE)

    assert selection.cancelled is False
    assert selection.extension_paths == ["/ext/sih"]


def test_extension_menu_eof_cancels(monkeypatch) -> None:
    """Closed stdin should cancel the selection."""

    def _raise(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise)

    selection = select_extensions(AVAILABLE)

    assert selection.cancelled is True
