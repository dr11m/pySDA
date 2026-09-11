"""Extension selection menu for steam-browser."""

from dataclasses import dataclass, field
from typing import List

from browser_launcher.extensions import ExtensionInfo

SEPARATOR = "=" * 50


@dataclass(frozen=True)
class ExtensionSelection:
    """Resolved extension choice for browser launch."""

    extension_paths: List[str] = field(default_factory=list)
    cancelled: bool = False


def select_extensions(available: List[ExtensionInfo]) -> ExtensionSelection:
    """Ask user which extension to load for the selected account."""
    while True:
        print()
        print("Extension selection")
        print(SEPARATOR)
        print("  1. Without extensions")
        for number, info in enumerate(available, start=2):
            print(f"  {number}. {info.name}")
        print(SEPARATOR)
        print("  0. Back to account list")
        print(SEPARATOR)

        try:
            raw_value = input("Select extension option: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return ExtensionSelection(cancelled=True)

        if raw_value == "0":
            return ExtensionSelection(cancelled=True)
        if raw_value == "1":
            return ExtensionSelection()
        if raw_value.isdigit():
            index: int = int(raw_value) - 2
            if 0 <= index < len(available):
                return ExtensionSelection(extension_paths=[available[index].path])

        print(f"Invalid choice. Enter 1-{len(available) + 1} or 0.")
