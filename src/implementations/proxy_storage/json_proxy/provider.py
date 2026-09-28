"""JSON file-based proxy provider for per-account proxy configuration."""

import json
from pathlib import Path
from typing import Dict

from src.interfaces.proxy_provider import ProxyProviderInterface

PROXIES_FILE = Path(__file__).parent / "proxies.json"


class JsonProxyProvider(ProxyProviderInterface):
    """Load account proxy mappings from a local JSON file."""

    def __init__(self, **kwargs):
        self.json_path = PROXIES_FILE
        self._proxies = self._load_proxies()

    def _load_proxies(self) -> Dict[str, str]:
        """Load proxy mappings from the configured JSON file."""
        with open(self.json_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def get_proxy(self, account_name: str) -> dict[str, str] | None:
        """Resolve an explicitly configured account route.

        Args:
            account_name: Account whose proxy setting is required.

        Returns:
            HTTP and HTTPS proxies, or None for explicit no_proxy.

        Raises:
            ValueError: The account setting is missing or empty.
        """
        proxy_url: str | None = self._proxies.get(account_name)

        if proxy_url is None or not proxy_url.strip():
            raise ValueError(f"Proxy is not configured for account '{account_name}'; use 'no_proxy' for direct access")

        proxy_url = proxy_url.strip()
        if proxy_url.lower() == "no_proxy":
            return None

        if "@" not in proxy_url and ":" in proxy_url and proxy_url.count(":") >= 3:
            stripped = proxy_url
            if proxy_url.startswith("http://"):
                stripped = proxy_url[7:]
            elif proxy_url.startswith("https://"):
                stripped = proxy_url[8:]

            parts = stripped.split(":")
            if len(parts) >= 4:
                host = parts[0]
                port = parts[1]
                username = parts[2]
                password = parts[3]
                scheme = "https" if proxy_url.startswith("https://") else "http"
                formatted_proxy = f"{scheme}://{username}:{password}@{host}:{port}"

                return {
                    "http": formatted_proxy,
                    "https": formatted_proxy,
                }

        return {
            "http": proxy_url,
            "https": proxy_url,
        }
