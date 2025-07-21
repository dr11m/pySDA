#!/usr/bin/env python3
"""
Менеджер паролей для CLI интерфейса
"""

from typing import Optional, Dict, Any
from .constants import Messages
from .display_formatter import DisplayFormatter
from src.utils.logger_setup import print_and_log


class PasswordManager:
    """Менеджер для работы с паролями Steam аккаунтов"""
    
    def __init__(self):
        self.formatter = DisplayFormatter()
    
    def change_password(self, account_context) -> bool:
        """
        Смена пароля Steam аккаунта
        
        Args:
            account_context: Контекст аккаунта
            
        Returns:
            bool: True если пароль успешно изменен
        """
        try:
            print_and_log(self.formatter.format_section_header("🔒 Смена пароля"))
            print_and_log("⚠️  ВНИМАНИЕ: Смена пароля может затронуть работу бота!")
            print_and_log("💡 Убедитесь, что у вас есть доступ к email и мобильному приложению")
            print_and_log("")
            
            # Заглушка - функция пока не реализована
            print_and_log(Messages.PASSWORD_CHANGE_NOT_IMPLEMENTED)
            print_and_log("💡 Эта функция будет реализована в будущих версиях")
            print_and_log("")
            print_and_log("Планируемая функциональность:")
            print_and_log("  • Проверка текущего пароля")
            print_and_log("  • Ввод нового пароля")
            print_and_log("  • Подтверждение через Steam Guard")
            print_and_log("  • Обновление конфигурации")
            print_and_log("  • Тестирование нового пароля")
            
            input("Нажмите Enter для продолжения...")
            return True
            
        except Exception as e:
            print_and_log(f"❌ Ошибка смены пароля: {e}", "ERROR")
            input("Нажмите Enter для продолжения...")
            return False
    
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """
        Проверка надежности пароля
        
        Args:
            password: Пароль для проверки
            
        Returns:
            Dict с результатами проверки
        """
        result = {
            'is_valid': True,
            'score': 0,
            'issues': []
        }
        
        # Минимальная длина
        if len(password) < 8:
            result['issues'].append("Пароль должен содержать минимум 8 символов")
            result['is_valid'] = False
        
        # Проверка наличия букв
        if not any(c.isalpha() for c in password):
            result['issues'].append("Пароль должен содержать буквы")
            result['is_valid'] = False
        
        # Проверка наличия цифр
        if not any(c.isdigit() for c in password):
            result['issues'].append("Пароль должен содержать цифры")
            result['is_valid'] = False
        
        # Подсчет очков надежности
        if len(password) >= 12:
            result['score'] += 2
        elif len(password) >= 8:
            result['score'] += 1
            
        if any(c.isupper() for c in password):
            result['score'] += 1
            
        if any(c.islower() for c in password):
            result['score'] += 1
            
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            result['score'] += 2
            
        return result 