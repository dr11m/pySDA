from typing import List, Optional, Dict
import time
from urllib.parse import urlparse

from src.utils.logger_setup import logger

class ProxyManager:
    """
    Управляет пулом прокси-серверов.
    - Загружает список прокси.
    - Выдает следующий доступный прокси по кругу (Round Robin).
    - Временно блокирует прокси при ошибках.
    """

    def __init__(self, proxy_list: Optional[List[str]] = None):
        """
        Инициализирует менеджер прокси.
        :param proxy_list: Список прокси в формате 'ip:port:login:password' или 'ip:port'.
        """
        self.proxies = self._parse_proxies(proxy_list if proxy_list else [])
        self.banned_proxies: Dict[str, float] = {}  # key: proxy_key, value: unban_timestamp
        self.current_proxy_index = -1
        
        if self.proxies:
            logger.info(f"Загружено {len(self.proxies)} прокси.")
        else:
            logger.info("Прокси не настроены, все запросы будут выполняться напрямую.")

    def _parse_proxies(self, proxy_list: List[str]) -> List[Dict[str, str]]:
        """Парсит список прокси-строк в словари, совместимые с requests."""
        parsed = []
        for proxy_str in proxy_list:
            try:
                parts = proxy_str.strip().split(':')
                if len(parts) == 4:
                    # ip:port:login:pass
                    host, port, user, pwd = parts
                    proxy_url = f"http://{user}:{pwd}@{host}:{port}"
                elif len(parts) == 2:
                    # ip:port
                    host, port = parts
                    proxy_url = f"http://{host}:{port}"
                else:
                    logger.warning(f"Неверный формат прокси, пропускаем: {proxy_str}")
                    continue
                
                parsed.append({
                    "http": proxy_url,
                    "https": proxy_url
                })
            except Exception as e:
                logger.warning(f"Ошибка парсинга прокси '{proxy_str}': {e}")
        return parsed

    def _get_proxy_key(self, proxy_dict: Dict[str, str]) -> str:
        """Возвращает уникальный ключ для прокси (например, 'login:pass@ip:port')."""
        url = urlparse(proxy_dict['http'])
        return f"{url.username}:{url.password}@{url.hostname}:{url.port}" if url.username else f"{url.hostname}:{url.port}"

    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        """
        Возвращает следующий доступный прокси.
        Пропускает забаненные прокси.
        """
        if not self.proxies:
            return None

        # Проверяем и разбаниваем устаревшие баны
        for key, unban_time in list(self.banned_proxies.items()):
            if time.time() > unban_time:
                logger.info(f"Прокси {key} разбанен.")
                del self.banned_proxies[key]

        # Ищем следующий рабочий прокси
        for _ in range(len(self.proxies)):
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            proxy = self.proxies[self.current_proxy_index]
            proxy_key = self._get_proxy_key(proxy)
            
            if proxy_key not in self.banned_proxies:
                logger.info(f"Используется прокси: {proxy_key}")
                return proxy

        logger.error("Все доступные прокси забанены!")
        return None

    def ban_current_proxy(self, ban_hours: int = 1):
        """
        Блокирует текущий используемый прокси.
        """
        if not self.proxies or self.current_proxy_index == -1:
            return
            
        proxy_to_ban = self.proxies[self.current_proxy_index]
        proxy_key = self._get_proxy_key(proxy_to_ban)
        
        if proxy_key in self.banned_proxies:
            return # Уже забанен

        unban_timestamp = time.time() + ban_hours * 3600
        self.banned_proxies[proxy_key] = unban_timestamp
        
        logger.warning(f"Прокси {proxy_key} забанен на {ban_hours} час(а).") 