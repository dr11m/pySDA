#!/usr/bin/env python3
"""
Реализация уведомлений через логгер
"""

from src.interfaces.notification_interface import NotificationInterface
from src.utils.logger_setup import logger


class LoggerNotification(NotificationInterface):
    """Реализация уведомлений через логгер"""
    
    def __init__(self, **kwargs):
        """Инициализация логгер-уведомлений"""
        pass
    
    def notify_user(self, message: str) -> bool:
        """Отправляет уведомление через логгер"""
        try:
            logger.critical(f"🔔 УВЕДОМЛЕНИЕ: {message}")
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки логгер-уведомления: {e}")
            return False 