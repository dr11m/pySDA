"""Interactive proxy selection menu for steam-browser."""

from dataclasses import dataclass
from typing import Dict, Optional

from browser_launcher.models import AccountSettings
from browser_launcher.proxy_format import format_proxy_label, parse_custom_proxy
from browser_launcher.proxy_utils import resolve_account_proxy

SEPARATOR = "=" * 50
CUSTOM_PROXY_HINT = (
    "Formats: host:port | host:port:username:password | "
    "http://username:password@host:port"
)


@dataclass(frozen=True)
class ProxySelection:
    """Resolved proxy choice for browser launch."""

    proxy_mapping: Optional[Dict[str, str]]
    cancelled: bool = False
    bypass_cs_deals: bool = False


def select_proxy_mapping(settings: AccountSettings) -> ProxySelection:
    """Ask user which proxy to use for the selected account."""
    account_proxy_mapping = resolve_account_proxy(
        settings.proxy_provider_config,
        settings.account_name,
    )
    account_proxy_label = format_proxy_label(account_proxy_mapping)

    while True:
        print()
        print("Proxy selection")
        print(SEPARATOR)
        print(f"  1. Steam via account proxy, cs.deals direct ({account_proxy_label})")
        print(f"  2. Account proxy ({account_proxy_label})")
        print("  3. Direct (no proxy)")
        print("  4. Custom proxy")
        print(SEPARATOR)
        print("  0. Back to account list")
        print(SEPARATOR)

        try:
            raw_value = input("Select proxy option: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return ProxySelection(proxy_mapping=None, cancelled=True)

        if raw_value == "0":
            return ProxySelection(proxy_mapping=None, cancelled=True)

        if raw_value == "1":
            return ProxySelection(
                proxy_mapping=account_proxy_mapping,
                bypass_cs_deals=True,
            )

        if raw_value == "2":
            return ProxySelection(proxy_mapping=account_proxy_mapping)

        if raw_value == "3":
            return ProxySelection(proxy_mapping=None)

        if raw_value == "4":
            custom_selection = _read_custom_proxy()
            if custom_selection.cancelled:
                continue
            return custom_selection

        print("Invalid choice. Enter 1, 2, 3, 4, or 0.")


def _read_custom_proxy() -> ProxySelection:
    """Read and validate a custom proxy string from user input."""
    print()
    print(CUSTOM_PROXY_HINT)
    try:
        raw_value = input("Enter proxy: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ProxySelection(proxy_mapping=None, cancelled=True)

    if not raw_value:
        print("Custom proxy was not provided.")
        return ProxySelection(proxy_mapping=None, cancelled=True)

    proxy_mapping = parse_custom_proxy(raw_value)
    if proxy_mapping is None:
        return ProxySelection(proxy_mapping=None)

    print(f"Using custom proxy: {format_proxy_label(proxy_mapping)}")
    return ProxySelection(proxy_mapping=proxy_mapping)
