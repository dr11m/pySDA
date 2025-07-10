import json
from pathlib import Path
from typing import Dict, Optional, Union

from src.interfaces.proxy_provider import ProxyProviderInterface


class JsonProxyProvider(ProxyProviderInterface):
    def __init__(self, **kwargs):
        # Всегда используем фиксированный путь для этой реализации
        self.json_path = Path('src/implementations/json_proxy/proxies.json')
        self._proxies = self._load_proxies()

    def _load_proxies(self) -> Dict[str, str]:
        if not self.json_path.exists():
            return {}
        with open(self.json_path, 'r') as f:
            return json.load(f)

    def get_proxy(self, account_name: str) -> Optional[Dict[str, str]]:
        proxy_url = self._proxies.get(account_name)

        if not proxy_url or proxy_url.lower() == 'no_proxy':
            return None

        # Конвертируем формат host:port:username:password в username:password@host:port
        if ':' in proxy_url and proxy_url.count(':') >= 3:
            # Парсим формат "http://host:port:username:password"
            if proxy_url.startswith('http://'):
                proxy_url = proxy_url[7:]  # убираем http://
            
            parts = proxy_url.split(':')
            if len(parts) >= 4:
                host = parts[0]
                port = parts[1]
                username = parts[2]
                password = parts[3]
                formatted_proxy = f"http://{username}:{password}@{host}:{port}"
                
                return {
                    'http': formatted_proxy,
                    'https': formatted_proxy
                }

        # Если уже в правильном формате, используем как есть
        return {
            'http': proxy_url,
            'https': proxy_url
        } 