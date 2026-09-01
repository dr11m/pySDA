"""Tests for steam-browser proxy selection menu."""

from browser_launcher.models import AccountSettings
from browser_launcher.proxy_menu import select_proxy_mapping

ACCOUNT_PROXY = {
    "http": "http://user:secret@203.0.113.10:8000",
    "https": "http://user:secret@203.0.113.10:8000",
}


def _settings() -> AccountSettings:
    return AccountSettings(
        account_name="acc1",
        username="acc1",
        cookie_storage_config={},
        proxy_provider_config={"module_path": "unused"},
    )


def test_proxy_menu_option_1_splits_steam_proxy_and_cs_deals_direct(
    monkeypatch,
) -> None:
    """Option 1 should use the account proxy and bypass cs.deals."""
    monkeypatch.setattr(
        "browser_launcher.proxy_menu.resolve_account_proxy",
        lambda *_args, **_kwargs: ACCOUNT_PROXY,
    )
    monkeypatch.setattr("builtins.input", lambda _: "1")

    selection = select_proxy_mapping(_settings())

    assert selection.cancelled is False
    assert selection.proxy_mapping == ACCOUNT_PROXY
    assert selection.bypass_cs_deals is True


def test_proxy_menu_option_2_sends_all_traffic_through_account_proxy(
    monkeypatch,
) -> None:
    """Option 2 should use the account proxy for every host."""
    monkeypatch.setattr(
        "browser_launcher.proxy_menu.resolve_account_proxy",
        lambda *_args, **_kwargs: ACCOUNT_PROXY,
    )
    monkeypatch.setattr("builtins.input", lambda _: "2")

    selection = select_proxy_mapping(_settings())

    assert selection.cancelled is False
    assert selection.proxy_mapping == ACCOUNT_PROXY
    assert selection.bypass_cs_deals is False


def test_proxy_menu_option_3_uses_direct_connection(monkeypatch) -> None:
    """Option 3 should open the browser without a proxy."""
    monkeypatch.setattr(
        "browser_launcher.proxy_menu.resolve_account_proxy",
        lambda *_args, **_kwargs: ACCOUNT_PROXY,
    )
    monkeypatch.setattr("builtins.input", lambda _: "3")

    selection = select_proxy_mapping(_settings())

    assert selection.cancelled is False
    assert selection.proxy_mapping is None
    assert selection.bypass_cs_deals is False
