#!/usr/bin/env python3
"""
Storage Interface - Интерфейс для хранения cookies
Пользователь может реализовать этот интерфейс для БД, файлов или других способов хранения
"""

import json
from abc import ABC, abstractmethod
from typing import Dict, Optional
from datetime import datetime
from pathlib import Path

from src.utils.logger_setup import logger


class CookieStorageInterface(ABC):
    """Абстрактный интерфейс для хранения cookies"""
    
    @abstractmethod
    def save_cookies(self, username: str, cookies: Dict[str, str]) -> bool:
        """
        Сохранить cookies для пользователя
        
        Args:
            username: Имя пользователя Steam
            cookies: Словарь cookies
            
        Returns:
            bool: True если успешно сохранено
        """
        pass
    
    @abstractmethod
    def load_cookies(self, username: str) -> Optional[Dict[str, str]]:
        """
        Загрузить cookies для пользователя
        
        Args:
            username: Имя пользователя Steam
            
        Returns:
            Optional[Dict[str, str]]: Словарь cookies или None если не найдено
        """
        pass
    
    @abstractmethod
    def delete_cookies(self, username: str) -> bool:
        """
        Удалить cookies для пользователя
        
        Args:
            username: Имя пользователя Steam
            
        Returns:
            bool: True если успешно удалено
        """
        pass
    
    @abstractmethod
    def get_last_update(self, username: str) -> Optional[datetime]:
        """
        Получить время последнего обновления cookies
        
        Args:
            username: Имя пользователя Steam
            
        Returns:
            Optional[datetime]: Время последнего обновления или None
        """
        pass


class FileCookieStorage(CookieStorageInterface):
    """Реализация хранения cookies в файлах (пример)"""
    
    def __init__(self, storage_dir: str = "accounts_info"):
        self.storage_dir = Path(storage_dir)
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
        except Exception:
            return False
    
    def load_cookies(self, username: str) -> Optional[Dict[str, str]]:
        """Загрузить cookies из JSON файла с проверкой времени"""
        try:
            cookie_file = self.storage_dir / f"{username}_cookies.json"
            if not cookie_file.exists():
                return None
            
            with open(cookie_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Проверяем время последнего обновления
            if max_age_minutes and 'last_update' in data:
                last_update = datetime.fromisoformat(data['last_update'])
                age = (datetime.now() - last_update).total_seconds() / 60
                
                if age > max_age_minutes:
                    logger.info(f"Cookies для {username} устарели ({age:.1f} минут)")
                    return None
            
            return data.get('cookies', {})
        except Exception:
            return None
    
    def delete_cookies(self, username: str) -> bool:
        """Удалить файл с cookies"""
        try:
            cookie_file = self.storage_dir / f"{username}_cookies.json"
            if cookie_file.exists():
                cookie_file.unlink()
            return True
        except Exception:
            return False
    
    def get_last_update(self, username: str) -> Optional[datetime]:
        """Получить время последнего обновления из файла"""
        try:
            cookie_file = self.storage_dir / f"{username}_cookies.json"
            if not cookie_file.exists():
                return None
            
            with open(cookie_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            last_update_str = data.get("last_update")
            if last_update_str:
                return datetime.fromisoformat(last_update_str)
            
            return None
        except Exception:
            return None 