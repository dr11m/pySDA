#!/usr/bin/env python3
"""
Notification Interface - Интерфейс для уведомлений пользователя
"""

from abc import ABC, abstractmethod


class NotificationInterface(ABC):
    """Абстрактный интерфейс для уведомлений"""
    
    @abstractmethod
    def notify_user(self, message: str) -> bool:
        """
        Отправляет уведомление пользователю
        
        Args:
            message: Текст уведомления
            
        Returns:
            bool: True если уведомление отправлено успешно
        """
        pass 