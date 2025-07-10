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