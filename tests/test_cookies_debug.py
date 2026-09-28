#!/usr/bin/env python3
"""
Тест для отладки cookies после refresh token
"""

import os
import pickle
from pathlib import Path
from src.steampy.client import SteamClient

def test_cookies_after_refresh():
    """Тест cookies после refresh token"""
    print("🔍 Тест cookies после refresh token...")
    
    # Находим pkl файл
    accounts_dir = Path("accounts_info")
    pkl_files = list(accounts_dir.glob("*.pkl"))
    
    if not pkl_files:
        print("❌ Не найдены pkl файлы")
        return
    
    pkl_path = pkl_files[0]
    account_name = pkl_path.stem
    print(f"🎯 Тестируем аккаунт: {account_name}")
    
    # Загружаем сессию
    with open(pkl_path, 'rb') as f:
        session, refresh_token = pickle.load(f)
    
    print("Refresh token found")
    
    # Создаем SteamClient
    steam_client = SteamClient(
        username=account_name,
        session_path=str(pkl_path)
    )
    
    print("✅ SteamClient создан")
    
    # Пробуем refresh
    if steam_client._try_refresh_session():
        print("✅ Refresh успешен")
        
        # Показываем все cookies
        print("\n📋 Все cookies после refresh:")
        for cookie in steam_client._session.cookies:
            print(f"Cookie name={cookie.name} domain={cookie.domain} secure={cookie.secure} expires={cookie.expires}")
        
        # Ищем steamLoginSecure
        steam_login_secure = None
        for cookie in steam_client._session.cookies:
            if cookie.name == 'steamLoginSecure':
                steam_login_secure = cookie
                break
        
        if steam_login_secure:
            print(f"\n✅ Найден steamLoginSecure в домене {steam_login_secure.domain}")
        else:
            print("\n❌ steamLoginSecure не найден")
        
        # Проверяем steamLoginSecure во всех доменах
        print("\n🔍 Проверяем steamLoginSecure во всех доменах:")
        steam_login_secure_domains = []
        for cookie in steam_client._session.cookies:
            if cookie.name == 'steamLoginSecure':
                steam_login_secure_domains.append(cookie.domain)
                print(f"  ✅ {cookie.domain}")
        
        if steam_login_secure_domains:
            print(f"\n📊 steamLoginSecure найден в {len(steam_login_secure_domains)} доменах:")
            for domain in steam_login_secure_domains:
                print(f"  - {domain}")
        else:
            print("\n❌ steamLoginSecure не найден ни в одном домене")
    else:
        print("❌ Refresh не удался")

if __name__ == "__main__":
    test_cookies_after_refresh()
