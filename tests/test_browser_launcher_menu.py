"""Tests for steam-browser account menu display."""

from pathlib import Path

from browser_launcher.config_reader import BrowserConfigReader
from browser_launcher.menu import AccountMenuItem, build_menu_items, render_menu
from browser_launcher.profile_store import ProfileStore


def _write_account_config(config_path: Path, description: str | None) -> None:
    lines = [
        "accounts:",
        "  atr1n4ik:",
        '    username: "atr1n4ik"',
        '    password: "secret"',
        '    mafile_path: "accounts_info/atr1n4ik.maFile"',
        '    steam_id: "76561198000000000"',
    ]
    if description is not None:
        lines.append(f'    description: "{description}"')
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_get_account_settings_includes_description(tmp_path: Path) -> None:
    """Account settings should expose the config.yaml description field."""
    config_path = tmp_path / "config.yaml"
    _write_account_config(config_path, "my main")

    reader = BrowserConfigReader(config_path)
    assert reader.load() is True

    settings = reader.get_account_settings("atr1n4ik")
    assert settings is not None
    assert settings.description == "my main"


def test_get_account_settings_missing_description_is_empty(tmp_path: Path) -> None:
    """Missing description in config.yaml should become an empty string."""
    config_path = tmp_path / "config.yaml"
    _write_account_config(config_path, None)

    reader = BrowserConfigReader(config_path)
    assert reader.load() is True

    settings = reader.get_account_settings("atr1n4ik")
    assert settings is not None
    assert settings.description == ""


def _menu_item(description: str) -> AccountMenuItem:
    return AccountMenuItem(
        index=1,
        account_name="atr1n4ik",
        username="atr1n4ik",
        proxy_label="direct",
        is_open=False,
        description=description,
    )


def test_render_menu_includes_account_description(capsys) -> None:
    """Menu row should show account name followed by config description."""
    render_menu([_menu_item("my main")])

    output = capsys.readouterr().out
    assert "atr1n4ik - my main" in output
    assert "(user: atr1n4ik, proxy ip: direct)" in output


def test_render_menu_omits_description_when_empty(capsys) -> None:
    """Menu row should keep the account name only when description is empty."""
    render_menu([_menu_item("")])

    output = capsys.readouterr().out
    assert "atr1n4ik -" not in output
    assert "atr1n4ik  (user: atr1n4ik, proxy ip: direct)" in output


def test_build_menu_items_copies_description(tmp_path: Path) -> None:
    """Built menu items should carry the account description from config."""
    config_path = tmp_path / "config.yaml"
    _write_account_config(config_path, "my main")

    reader = BrowserConfigReader(config_path)
    assert reader.load() is True

    items = build_menu_items(reader, ProfileStore(root_dir=tmp_path / "profiles"))
    assert len(items) == 1
    assert items[0].description == "my main"
