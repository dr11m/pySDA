#!/usr/bin/env python3
"""
Тест для принудительного использования refresh token
"""

import os
import pickle
from src.steampy.client import SteamClient
from src.utils.delayed_http_adapter import DelayedHTTPAdapter

def test_refresh_token_force():
    """Тест принудительного использования refresh token"""
    print("🧪 Тестируем принудительное использование refresh token...")
    
    account_name = "JkzbuMjpDL"
    pkl_path = f"accounts_info/{account_name}.pkl"
    
    # Проверяем, есть ли pkl файл с refresh token
    if not os.path.exists(pkl_path):
        print("❌ Pkl файл не найден, сначала нужно выполнить вход")
        return
    
    print(f"✅ Найден pkl файл: {pkl_path}")
    
    # Загружаем данные из pkl файла
    with open(pkl_path, 'rb') as f:
        session_data = pickle.load(f)
    
    if isinstance(session_data, tuple):
        session, refresh_token = session_data
        print(f"✅ Найден refresh token: {refresh_token[:20]}...")
    else:
        print("❌ Старый формат pkl файла без refresh token")
        return
    
    # Создаем SteamClient с существующими данными
    print("🔄 Создаем SteamClient с существующими данными...")
    
    steam_client = SteamClient(
        username=account_name,
        session_path=pkl_path
    )
    
    # Добавляем адаптер без задержки для теста
    adapter = DelayedHTTPAdapter(delay=0)
    steam_client._session.mount('http://', adapter)
    steam_client._session.mount('https://', adapter)
    
    print(f"🔄 Проверяем refresh token для {account_name}...")
    
    # Принудительно проверяем refresh token
    if steam_client.refresh_token:
        print(f"🔄 Найден refresh token, пробуем обновить сессию...")
        if steam_client._try_refresh_session():
            print("✅ Сессия успешно обновлена через refresh token!")
        else:
            print("❌ Не удалось обновить сессию через refresh token")
    else:
        print("❌ Refresh token не найден")

if __name__ == "__main__":
    test_refresh_token_force()
    print("\n�� Тест завершен!") 