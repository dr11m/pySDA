#!/usr/bin/env python3
"""
Реализация уведомлений через Telegram
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv

from src.interfaces.notification_interface import NotificationInterface
from src.utils.logger_setup import logger


class TelegramNotification(NotificationInterface):
    """Реализация уведомлений через Telegram"""
    
    def __init__(self, **kwargs):
        """Инициализация Telegram-уведомлений"""
        # Загружаем .env файл из папки с реализацией
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
        else:
            logger.warning(f"Файл .env не найден в {env_path}")
        
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.bot_token or not self.chat_id:
            logger.error("Не настроены TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID в .env файле")
            raise ValueError("Telegram уведомления не настроены")
    
    def notify_user(self, message: str) -> bool:
        """Отправляет уведомление через Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            params = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            logger.info("Telegram уведомление отправлено успешно")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка отправки Telegram уведомления: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка отправки Telegram уведомления: {e}")
            return False 

if __name__ == '__main__':
    from pathlib import Path
    import os
    print(f"[DEBUG] __file__ = {__file__}")
    env_path = Path(__file__).parent / '.env'
    print(f"[DEBUG] env_path = {env_path}")
    print(f"[DEBUG] env_path.exists() = {env_path.exists()}")
    if env_path.exists():
        print(f"[DEBUG] .env file content:")
        with open(env_path, encoding='utf-8') as f:
            print(f.read())
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)
    print(f"[DEBUG] TELEGRAM_BOT_TOKEN = {os.getenv('TELEGRAM_BOT_TOKEN')}")
    print(f"[DEBUG] TELEGRAM_CHAT_ID = {os.getenv('TELEGRAM_CHAT_ID')}")
    try:
        notif = TelegramNotification()
        print("[DEBUG] TelegramNotification создан успешно!")
    except Exception as e:
        print(f"[DEBUG] Ошибка при создании TelegramNotification: {e}") 