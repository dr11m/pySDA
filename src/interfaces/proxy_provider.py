from abc import ABC, abstractmethod
from typing import Dict, Optional


class ProxyProviderInterface(ABC):
    @abstractmethod
    def get_proxy(self, account_name: str) -> Optional[Dict[str, str]]:
        """
        Возвращает прокси для указанного аккаунта.

        :param account_name: Имя аккаунта.
        :return: Словарь с настройками прокси для библиотеки requests
                 (например, {'http': 'http://...', 'https': 'https://...'}),
                 или None, если прокси не используется.
        """
        ... 