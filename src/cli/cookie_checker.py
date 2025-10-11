#!/usr/bin/env python3
"""
Cookie Checker - Автоматическая проверка и обновление cookies
"""

from typing import Optional, Callable, Any
from .display_formatter import DisplayFormatter
from src.utils.logger_setup import logger
from src.cookie_manager import CookieManager
from src.utils.logger_setup import print_and_log
from .config_manager import global_config

class CookieChecker:
    """Проверщик cookies для автоматического обновления при необходимости"""
    
    def __init__(self, cookie_manager, formatter: DisplayFormatter):
        self.cookie_manager: CookieManager = cookie_manager
        self.formatter: DisplayFormatter = formatter
    
    def ensure_valid_cookies(self, max_age_minutes: int = None) -> bool:
        """
        Убедиться, что cookies актуальны, обновить при необходимости
        
        Args:
            max_age_minutes: Максимальный возраст cookies в минутах (если None, используется значение из конфига)
            
        Returns:
            bool: True если cookies актуальны или успешно обновлены
        """
        try:
            # Используем значение из конфига, если не передано явно
            if max_age_minutes is None:
                max_age_minutes = global_config.get_max_cookie_age_minutes()
            
            # Проверяем актуальность cookies
            if self.cookie_manager.is_cookies_valid(max_age_minutes):
                print_and_log("✅ Cookies актуальны")
                return True
            
            # Cookies неактуальны, обновляем
            print_and_log("🔄 Cookies устарели, обновляем...")
            
            cookies = self.cookie_manager.update_cookies()
            
            if cookies:
                print_and_log("✅ Cookies успешно обновлены")
                return True
            else:
                print_and_log("❌ Не удалось обновить cookies")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки cookies: {e}")
            return False
    


def requires_cookies(max_age_minutes: int = None, show_info: bool = True):
    """
    Декоратор для методов, требующих актуальных cookies
    
    Args:
        max_age_minutes: Максимальный возраст cookies (если None, используется значение из конфига)
        show_info: Показывать информацию о процессе
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # Используем значение из конфига, если не передано явно
            actual_max_age = max_age_minutes if max_age_minutes is not None else global_config.get_max_cookie_age_minutes()
            
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
            if not checker.ensure_valid_cookies(actual_max_age):
                return None
            
            # Выполняем оригинальную функцию
            return func(self, *args, **kwargs)
        
        return wrapper
    return decorator 