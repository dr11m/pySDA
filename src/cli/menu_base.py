#!/usr/bin/env python3
"""Base classes for the CLI menu system."""

from abc import ABC, abstractmethod
import sys
from typing import Any, Callable, Dict, Optional

from .constants import Formatting
from src.utils.logger_setup import log_exception


class MenuItem:
    """Single menu action entry."""

    def __init__(self, key: str, label: str, action: Callable[[], Any], enabled: bool = True):
        self.key = key
        self.label = label
        self.action = action
        self.enabled = enabled

    def execute(self) -> Any:
        """Execute menu action."""
        if not self.enabled:
            return None
        return self.action()

    def __str__(self) -> str:
        return f"{self.key}. {self.label}"


class BaseMenu(ABC):
    """Base class for CLI menu screens."""

    def __init__(self, title: str):
        self.title = title
        self.items: Dict[str, MenuItem] = {}
        self.running = True

    def add_item(self, item: MenuItem) -> None:
        """Add a menu item."""
        self.items[item.key] = item

    def remove_item(self, key: str) -> None:
        """Remove a menu item by key."""
        if key in self.items:
            del self.items[key]

    def get_item(self, key: str) -> Optional[MenuItem]:
        """Get a menu item by key."""
        return self.items.get(key)

    def display_header(self) -> None:
        """Render menu header."""
        print(f"\n{Formatting.SEPARATOR}")
        print(self.title)
        print(Formatting.SEPARATOR)

    def display_items(self) -> None:
        """Render all enabled menu items."""
        for item in self.items.values():
            if item.enabled:
                print(item)

    def display_footer(self) -> None:
        """Render menu footer."""
        print(Formatting.LINE)

    def display_menu(self) -> None:
        """Render full menu."""
        self.display_header()
        self.display_items()
        self.display_footer()
        sys.stdout.flush()

    def get_user_choice(self) -> str:
        """Read user selection."""
        from .constants import Messages

        return input(Messages.CHOOSE_ACTION).strip()

    def handle_choice(self, choice: str) -> bool:
        """Handle user selection and return whether loop should continue."""
        item = self.get_item(choice)
        if item and item.enabled:
            try:
                result = item.execute()
                return self.process_action_result(choice, result)
            except Exception as error:
                self.handle_error(error)
                return True

        self.handle_invalid_choice(choice)
        return True

    def process_action_result(self, choice: str, result: Any) -> bool:
        """Process action result and return whether loop should continue."""
        return True

    def handle_invalid_choice(self, choice: str) -> None:
        """Handle invalid user choice."""
        from .constants import Messages

        print(Messages.INVALID_CHOICE)

    def handle_error(self, error: Exception) -> None:
        """Handle unexpected action error."""
        log_exception("Unhandled menu action error.")
        print(f"❌ Ошибка: {error}")

    def should_pause(self) -> bool:
        """Return whether pause is needed after action."""
        return True

    def pause(self) -> None:
        """Pause for user acknowledgement."""
        if self.should_pause():
            from .constants import Messages

            input(f"\n{Messages.PRESS_ENTER}")

    @abstractmethod
    def setup_menu(self) -> None:
        """Configure menu items."""

    def run(self) -> None:
        """Start menu loop."""
        self.setup_menu()

        while self.running:
            self.display_menu()
            choice = self.get_user_choice()

            if not self.handle_choice(choice):
                break

            self.pause()

    def stop(self) -> None:
        """Stop menu loop."""
        self.running = False


class NavigableMenu(BaseMenu):
    """Menu with a back action."""

    def __init__(self, title: str, back_key: str = "0", back_label: str = "⬅️  Назад"):
        super().__init__(title)
        self.back_key = back_key
        self.back_label = back_label

    def setup_menu(self) -> None:
        """Configure menu items in child classes."""

    def run(self) -> None:
        """Start menu loop and append back action."""
        self.setup_menu()
        self.add_item(MenuItem(self.back_key, self.back_label, self.go_back))

        while self.running:
            self.display_menu()
            choice = self.get_user_choice()

            if not self.handle_choice(choice):
                break

            self.pause()

    def go_back(self) -> None:
        """Stop current menu and return."""
        self.stop()

    def process_action_result(self, choice: str, result: Any) -> bool:
        """Handle navigation-specific action result."""
        if choice == self.back_key:
            return False
        return super().process_action_result(choice, result)

    def should_pause(self) -> bool:
        """Return whether pause is needed after action."""
        return True
