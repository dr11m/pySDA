#!/usr/bin/env python3
"""
Cookie Checker - Автоматическая проверка и обновление cookies
"""

from typing import Optional, Callable, Any
import logging
from .constants import Messages
from .display_formatter import DisplayFormatter

logger = logging.getLogger(__name__)


class CookieChecker:
    """Проверщик cookies для автоматического обновления при необходимости"""
    
    def __init__(self, cookie_manager, formatter: DisplayFormatter):
        self.cookie_manager = cookie_manager
        self.formatter = formatter
    
    def ensure_valid_cookies(self, max_age_minutes: int = 120, show_info: bool = True) -> bool:
        """
        Убедиться, что cookies актуальны, обновить при необходимости
        
        Args:
            max_age_minutes: Максимальный возраст cookies в минутах
            show_info: Показывать информацию о процессе
            
        Returns:
            bool: True если cookies актуальны или успешно обновлены
        """
        try:
            # Проверяем актуальность cookies
            if self.cookie_manager.is_cookies_valid(max_age_minutes):
                if show_info:
                    logger.info("✅ Cookies актуальны")
                return True
            
            # Cookies неактуальны, обновляем
            if show_info:
                print("🔄 Cookies устарели, обновляем...")
            
            cookies = self.cookie_manager.update_cookies()
            
            if cookies:
                if show_info:
                    print("✅ Cookies успешно обновлены")
                return True
            else:
                if show_info:
                    print("❌ Не удалось обновить cookies")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки cookies: {e}")
            if show_info:
                print(f"❌ Ошибка проверки cookies: {e}")
            return False
    
    def with_valid_cookies(self, action: Callable[[], Any], max_age_minutes: int = 120, show_info: bool = True) -> Any:
        """
        Выполнить действие с предварительной проверкой cookies
        
        Args:
            action: Функция для выполнения
            max_age_minutes: Максимальный возраст cookies
            show_info: Показывать информацию о процессе
            
        Returns:
            Результат выполнения action или None при ошибке
        """
        if not self.ensure_valid_cookies(max_age_minutes, show_info):
            return None
        
        try:
            return action()
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения действия: {e}")
            if show_info:
                print(f"❌ Ошибка выполнения действия: {e}")
            return None


def requires_cookies(max_age_minutes: int = 120, show_info: bool = True):
    """
    Декоратор для методов, требующих актуальных cookies
    
    Args:
        max_age_minutes: Максимальный возраст cookies
        show_info: Показывать информацию о процессе
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # Предполагаем, что у объекта есть cookie_checker
            if hasattr(self, 'cookie_checker'):
                checker = self.cookie_checker
            elif hasattr(self, 'cookie_manager') and hasattr(self, 'formatter'):
                # Создаем временный checker
                checker = CookieChecker(self.cookie_manager, self.formatter)
            else:
                logger.error("❌ Объект не имеет cookie_checker или необходимых атрибутов")
                return None
            
            # Проверяем cookies перед выполнением
            if not checker.ensure_valid_cookies(max_age_minutes, show_info):
                return None
            
            # Выполняем оригинальную функцию
            return func(self, *args, **kwargs)
        
        return wrapper
    return decorator 