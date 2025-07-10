#!/usr/bin/env python3
"""
Реализация интерфейса хранения cookies в виде JSON файлов.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from src.interfaces.storage_interface import CookieStorageInterface
from src.utils.logger_setup import logger

class JsonCookieStorage(CookieStorageInterface):
    """
    Реализация хранения cookies в файлах формата JSON.
    Файлы хранятся в папке 'json_cookies'.
    """
    
    def __init__(self, **kwargs):
        # **kwargs используется для обратной совместимости, если фабрика передаст лишние параметры.
        # Всегда используем фиксированный путь для этой реализации
        self.storage_dir = Path("src/implementations/json_cookie_storage/cookies")
        self.storage_dir.mkdir(exist_ok=True)
    
    def save_cookies(self, username: str, cookies: Dict[str, str]) -> bool:
        """Сохранить cookies в JSON файл"""
        try:
            data = {
                "cookies": cookies,
                "last_update": datetime.now().isoformat()
            }
            
            with open(self.storage_dir / f"{username}_cookies.json", 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения cookie-файла для {username}: {e}")
            return False
    
    def load_cookies(self, username: str) -> Optional[Dict[str, str]]:
        """Загрузить cookies из JSON файла"""
        cookie_file = self.storage_dir / f"{username}_cookies.json"
        if not cookie_file.exists():
            return None
        
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('cookies')
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Ошибка загрузки cookie-файла для {username}: {e}")
            return None
    
    def delete_cookies(self, username: str) -> bool:
        """Удалить файл с cookies"""
        try:
            cookie_file = self.storage_dir / f"{username}_cookies.json"
            if cookie_file.exists():
                cookie_file.unlink()
                logger.info(f"Удален cookie-файл для {username}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления cookie-файла для {username}: {e}")
            return False
    
    def get_last_update(self, username: str) -> Optional[datetime]:
        """Получить время последнего обновления из файла"""
        cookie_file = self.storage_dir / f"{username}_cookies.json"
        if not cookie_file.exists():
            return None
            
        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            last_update_str = data.get("last_update")
            if last_update_str:
                return datetime.fromisoformat(last_update_str)
            
            return None
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Ошибка чтения времени обновления из cookie-файла для {username}: {e}")
            return None 