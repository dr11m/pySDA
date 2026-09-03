"""Interactive account selection menu for steam-browser."""

from dataclasses import dataclass
from typing import Any, List

from browser_launcher.config_reader import BrowserConfigReader
from browser_launcher.profile_store import ProfileStore
from browser_launcher.proxy_format import format_proxy_label
from browser_launcher.session_lock import SessionLock
from src.factories import create_instance_from_config


OPEN_MARKER = "[*]"
AVAILABLE_MARKER = "[ ]"
SEPARATOR = "=" * 50


@dataclass(frozen=True)
class AccountMenuItem:
    """One account row in the interactive menu."""

    index: int
    account_name: str
    username: str
    proxy_label: str
    is_open: bool
    description: str = ""


def build_menu_items(
    reader: BrowserConfigReader,
    profile_store: ProfileStore,
) -> List[AccountMenuItem]:
    """Build menu rows for all configured accounts."""
    items: List[AccountMenuItem] = []
    proxy_provider = _load_proxy_provider(reader)

    for index, account_name in enumerate(reader.list_accounts(), start=1):
        settings = reader.get_account_settings(account_name)
        if not settings:
            continue

        proxy_mapping = (
            proxy_provider.get_proxy(account_name)
            if proxy_provider is not None
            else None
        )
        proxy_label = format_proxy_label(proxy_mapping)

        profile_dir = profile_store.root_dir / account_name
        is_open = SessionLock(profile_dir, account_name).is_active()

        items.append(
            AccountMenuItem(
                index=index,
                account_name=account_name,
                username=settings.username,
                proxy_label=proxy_label,
                is_open=is_open,
                description=settings.description,
            )
        )

    return items


def _load_proxy_provider(reader: BrowserConfigReader) -> Any | None:
    """Create one proxy provider instance for the whole menu render."""
    account_names = reader.list_accounts()
    if not account_names:
        return None

    settings = reader.get_account_settings(account_names[0])
    if settings is None or not settings.proxy_provider_config:
        return None

    return create_instance_from_config(settings.proxy_provider_config)


def render_menu(items: List[AccountMenuItem]) -> None:
    """Print the account selection menu."""
    print()
    print("Steam Browser")
    print(SEPARATOR)
    print(f"{OPEN_MARKER} browser open   {AVAILABLE_MARKER} available")
    print(SEPARATOR)

    if not items:
        print("No accounts found in config.yaml")
        print(SEPARATOR)
        return

    for item in items:
        marker = OPEN_MARKER if item.is_open else AVAILABLE_MARKER
        display_name = item.account_name
        if item.description:
            display_name = f"{item.account_name} - {item.description}"
        print(
            f" {item.index:>2}. {marker} {display_name}"
            f"  (user: {item.username}, proxy ip: {item.proxy_label})"
        )

    print(SEPARATOR)
    print("  0. Exit")
    print(SEPARATOR)


def parse_selection(raw_value: str, items: List[AccountMenuItem]) -> int | None:
    """Parse user input into a menu index or None for exit."""
    value = raw_value.strip()
    if not value:
        return -1
    if value == "0":
        return None
    if not value.isdigit():
        return -1

    selected_index = int(value)
    matching = [item for item in items if item.index == selected_index]
    if not matching:
        return -1
    return selected_index


def find_item_by_index(
    items: List[AccountMenuItem], index: int
) -> AccountMenuItem | None:
    """Return menu item for the selected index."""
    for item in items:
        if item.index == index:
            return item
    return None
