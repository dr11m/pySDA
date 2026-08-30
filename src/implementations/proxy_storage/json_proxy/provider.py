"""JSON file-based proxy provider for per-account proxy configuration."""

import json
from pathlib import Path
from typing import Dict, Optional

from src.interfaces.proxy_provider import ProxyProviderInterface

PROXIES_FILE = Path(__file__).parent / "proxies.json"


class JsonProxyProvider(ProxyProviderInterface):
    """Load account proxy mappings from a local JSON file."""

    def __init__(self, **kwargs):
        self.json_path = PROXIES_FILE
        self._proxies = self._load_proxies()

    def _load_proxies(self) -> Dict[str, str]:
        """Load proxy mappings from the configured JSON file."""
        if not self.json_path.exists():
            return {}
        with open(self.json_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def get_proxy(self, account_name: str) -> Optional[Dict[str, str]]:
        """Return requests-compatible proxy settings for an account."""
        proxy_url = self._proxies.get(account_name)

        if not proxy_url or str(proxy_url).lower() == "no_proxy":
            return None

        proxy_url = str(proxy_url)

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
