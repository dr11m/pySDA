"""CLI entry point for steam-browser."""

import argparse
import sys
from pathlib import Path

from loguru import logger

from browser_launcher.config_reader import BrowserConfigReader
from browser_launcher.launcher import BrowserLauncher
from browser_launcher.menu import (
    build_menu_items,
    find_item_by_index,
    parse_selection,
    render_menu,
)
from browser_launcher.models import LaunchOptions
from browser_launcher.profile_store import ProfileStore


DEFAULT_START_URL = "https://steamcommunity.com/"


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="steam-browser",
        description="Interactive browser launcher for pySDA accounts.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to pySDA config.yaml (default: config.yaml)",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_START_URL,
        help=f"Start URL (default: {DEFAULT_START_URL})",
    )
    parser.add_argument(
        "--profile-root",
        default=None,
        help="Override browser profile root directory (default: ./browser_profiles)",
    )
    parser.add_argument(
        "--refresh-cookies",
        action="store_true",
        help="Force re-seed cookies from storage on launch",
    )
    return parser


def _load_reader(config_path: str) -> BrowserConfigReader:
    """Load config reader or exit with an error."""
    reader = BrowserConfigReader(config_path)
    if not reader.load():
        logger.error("Config file not found: {}", config_path)
        sys.exit(1)
    return reader


def _run_interactive_menu(args: argparse.Namespace) -> None:
    """Show account menu and launch browser for the selected account."""
    reader = _load_reader(args.config)
    profile_root = Path(args.profile_root) if args.profile_root else None
    profile_store = ProfileStore(root_dir=profile_root) if profile_root else ProfileStore()
    launcher = BrowserLauncher(profile_store=profile_store)

    while True:
        items = build_menu_items(reader, profile_store)
        render_menu(items)

        if not items:
            return

        try:
            raw_value = input("Select account number: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return

        selected_index = parse_selection(raw_value, items)
        if selected_index is None:
            return
        if selected_index == -1:
            print("Invalid choice. Enter account number or 0 to exit.")
            continue

        selected_item = find_item_by_index(items, selected_index)
        if selected_item is None:
            print("Invalid choice. Enter account number or 0 to exit.")
            continue

        if selected_item.is_open:
            print(
                f"Account '{selected_item.account_name}' is already open. "
                "Close its browser window first."
            )
            continue

        settings = reader.get_account_settings(selected_item.account_name)
        if settings is None:
            print(f"Account '{selected_item.account_name}' is not configured correctly.")
            continue

        options = LaunchOptions(
            account_name=selected_item.account_name,
            start_url=args.url,
            config_path=Path(args.config),
            profile_root=profile_store.root_dir,
            refresh_cookies=args.refresh_cookies,
        )
        launcher.open_account(settings, options)
        print(f"Browser for '{selected_item.account_name}' was closed.")


def main() -> None:
    """CLI main entry point."""
    parser = _build_parser()
    args = parser.parse_args()
    _run_interactive_menu(args)


if __name__ == "__main__":
    main()
