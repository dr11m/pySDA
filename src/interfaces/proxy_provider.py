"""Required per-account proxy routes supplied by storage providers."""

from abc import ABC, abstractmethod


class ProxyProviderInterface(ABC):
    """Resolve account routes without silent direct fallbacks."""

    @abstractmethod
    def get_proxy(self, account_name: str) -> dict[str, str] | None:
        """Resolve a configured account route without silent direct fallback.

        Args:
            account_name: Account whose proxy setting is required.

        Returns:
            Both HTTP and HTTPS proxy URLs, or None for explicit no_proxy.

        Raises:
            ValueError: The account setting is missing or empty.
        """
        ...
