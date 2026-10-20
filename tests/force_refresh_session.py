#!/usr/bin/env python3
"""
Пример использования интегрированной функциональности обновления сессии
"""

import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.steampy.client import SteamClient
from src.utils.logger_setup import logger

def example_refresh_session():
    """Пример обновления сессии"""
    
    # Пример 1: Создание клиента с существующей сессией
    username = "example_account"  # Замените на реальное имя пользователя
    session_path = f"accounts_info/{username}.pkl"
    
    print("📋 Пример 1: Создание клиента с существующей сессией")
    print(f"👤 Пользователь: {username}")
    print(f"📁 Путь к сессии: {session_path}")
    
    try:
        # Создаем клиент
        client = SteamClient(
            username=username,
            session_path=session_path
        )
        
        # Проверяем, есть ли refresh token
        if client.refresh_token:
            print(f"✅ Refresh token найден: {client.refresh_token[:20]}...")
            
            # Пробуем обновить сессию
            print("🔄 Обновляем сессию...")
            success = client._try_refresh_session()
            
            if success:
                print("✅ Сессия успешно обновлена!")
                
                # Проверяем активность сессии
                if client.is_session_alive():
                    print("✅ Сессия активна!")
                else:
                    print("⚠️ Сессия не активна")
            else:
                print("❌ Не удалось обновить сессию")
        else:
            print("❌ Refresh token не найден")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def example_new_cookies_method():
    """Пример использования нового метода get_steam_login_cookies"""
    
    print("\n📋 Пример 2: Использование get_steam_login_cookies")
    
    # Тестовый refresh token (замените на реальный)
    test_refresh_token = "your_refresh_token_here"
    
    try:
        # Создаем клиент
        client = SteamClient(username="test_user")
        
        # Получаем новые cookies
        print("🔄 Получаем новые cookies...")
        new_cookies = client.get_steam_login_cookies(test_refresh_token)
        
        print(f"✅ Получены cookies:")
        print(f"  - steamLoginSecure: {new_cookies['steamLoginSecure'][:20]}...")
        print(f"  - sessionid: {new_cookies['sessionid']}")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    print("🚀 Примеры использования интегрированной функциональности обновления сессии")
    print("=" * 70)
    
    # Запускаем примеры
    example_refresh_session()
    #example_new_cookies_method()