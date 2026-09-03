"""Read-only access to pySDA config.yaml for browser launcher."""

from pathlib import Path
from typing import Any, Dict, List

from ruamel.yaml import YAML

from browser_launcher.models import AccountSettings


class BrowserConfigReader:
    """Load account definitions from config.yaml without touching pySDA runtime."""

    def __init__(self, config_path: str | Path = "config.yaml"):
        self.config_path = Path(config_path)
        self._config_data: Dict[str, Any] | None = None
        self._yaml = YAML()

    def load(self) -> bool:
        """Load configuration from disk."""
        if not self.config_path.exists():
            return False
        with open(self.config_path, "r", encoding="utf-8") as config_file:
            self._config_data = self._yaml.load(config_file) or {}
        return True

    def list_accounts(self) -> List[str]:
        """Return configured account names."""
        if not self._config_data:
            return []
        accounts = self._config_data.get("accounts", {})
        return list(accounts.keys())

    def get_account_settings(self, account_name: str) -> AccountSettings | None:
        """Resolve account settings for launcher use."""
        if not self._config_data:
            return None

        accounts = self._config_data.get("accounts", {})
        account_config = accounts.get(account_name)
        if not account_config:
            return None

        username = account_config.get("username")
        if not username:
            return None

        return AccountSettings(
            account_name=account_name,
            username=username,
            cookie_storage_config=self._config_data.get("cookie_storage", {}),
            proxy_provider_config=self._config_data.get("proxy_provider", {}),
            description=str(account_config.get("description") or ""),
        )

    def get_global(self, key: str, default: Any = None) -> Any:
        """Return a top-level config value."""
        if not self._config_data:
            return default
        return self._config_data.get(key, default)
