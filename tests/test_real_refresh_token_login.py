#!/usr/bin/env python3
"""
Реальный тест для входа через refresh token и обновления cookies в БД
"""

import os
import pickle
from pathlib import Path
from src.steampy.client import SteamClient
from src.utils.delayed_http_adapter import DelayedHTTPAdapter
from src.implementations.cookie_storage.sql_storage import SqlAlchemyCookieStorage

def test_real_refresh_token_login():
    """Реальный тест входа через refresh token и обновления cookies в БД"""
    print("🔑 Реальный тест входа через refresh token и обновления cookies в БД...")
    
    # Выбираем аккаунт для тестирования
    account_name = "JkzbuMjpDL"  # Можно изменить на другой аккаунт
    pkl_path = f"accounts_info/{account_name}.pkl"
    
    print(f"🎯 Тестируем аккаунт: {account_name}")
    
    # Проверяем, есть ли pkl файл с refresh token
    if not os.path.exists(pkl_path):
        print(f"❌ Pkl файл не найден: {pkl_path}")
        print("💡 Сначала нужно выполнить вход для этого аккаунта")
        return False
    
    print(f"✅ Найден pkl файл: {pkl_path}")
    
    # Загружаем данные из pkl файла
    try:
        with open(pkl_path, 'rb') as f:
            session_data = pickle.load(f)
        
        if isinstance(session_data, tuple):
            session, refresh_token = session_data
            print("Refresh token found")
        else:
            print("❌ Старый формат pkl файла без refresh token")
            return False
    except Exception as e:
        print(f"❌ Ошибка загрузки pkl файла: {e}")
        return False
    
    # Создаем SteamClient с существующими данными
    print("🔄 Создаем SteamClient с существующими данными...")
    
    try:
        steam_client = SteamClient(
            username=account_name,
            session_path=pkl_path
        )
        
        # Добавляем адаптер с задержкой 0 для теста
        adapter = DelayedHTTPAdapter(delay=0, timeout=steam_client.request_timeout, username=steam_client.username)
        steam_client._session.mount('http://', adapter)
        steam_client._session.mount('https://', adapter)
        
        print(f"✅ SteamClient создан для {account_name}")
        
    except Exception as e:
        print(f"❌ Ошибка создания SteamClient: {e}")
        return False
    
    # Проверяем refresh token и обновляем сессию
    print(f"🔄 Проверяем refresh token для {account_name}...")
    
    if not steam_client.refresh_token:
        print("❌ Refresh token не найден в клиенте")
        return False
    
    print(f"🔄 Найден refresh token, пробуем обновить сессию...")
    
    # Выполняем обновление через refresh token
    if steam_client._try_refresh_session():
        print("✅ Сессия успешно обновлена через refresh token!")
        
        # Теперь получаем cookies из обновленной сессии
        print("🍪 Получаем cookies из обновленной сессии...")
        from src.utils.cookies_and_session import session_to_dict
        cookies = session_to_dict(steam_client._session)
        
        if cookies:
            print(f"✅ Получено {len(cookies)} cookies из сессии")
            
            # Сохраняем cookies в БД
            print("💾 Сохраняем cookies в БД...")
            storage = SqlAlchemyCookieStorage()
            
            if storage.save_cookies(account_name, cookies):
                print("✅ Cookies успешно сохранены в БД")
                
                # Проверяем, что cookies сохранились
                saved_cookies = storage.load_cookies(account_name)
                if saved_cookies:
                    print(f"✅ Cookies загружены из БД: {len(saved_cookies)} cookies")
                    
                    # Проверяем критически важные cookies в сложной структуре
                    critical_cookies = ['sessionid', 'steamLoginSecure']
                    found_cookies = []
                    
                    # Ищем cookies в сложной структуре
                    if 'cookies' in saved_cookies:
                        for domain, paths in saved_cookies['cookies'].items():
                            for path, cookies_dict in paths.items():
                                for cookie_name, cookie_data in cookies_dict.items():
                                    if cookie_name in critical_cookies:
                                        found_cookies.append(cookie_name)
                                        print(f"✅ Критический cookie '{cookie_name}' найден в домене {domain}")
                    
                    # Проверяем, что все критически важные cookies найдены
                    missing_cookies = [cookie for cookie in critical_cookies if cookie not in found_cookies]
                    if missing_cookies:
                        for cookie_name in missing_cookies:
                            print(f"⚠️ Критический cookie '{cookie_name}' не найден")
                    else:
                        print("✅ Все критически важные cookies найдены")
                    
                    # Показываем количество доменов и cookies
                    if 'cookies' in saved_cookies:
                        domains_count = len(saved_cookies['cookies'])
                        total_cookies = sum(len(paths) for domain, paths in saved_cookies['cookies'].items() 
                                          for path, cookies_dict in paths.items())
                        print(f"\n📋 Структура cookies: {domains_count} доменов, {total_cookies} путей")
                        
                        # Показываем домены
                        for domain in saved_cookies['cookies'].keys():
                            print(f"  Домен: {domain}")
                    
                    return True
                else:
                    print("❌ Cookies не загружены из БД")
                    return False
            else:
                print("❌ Не удалось сохранить cookies в БД")
                return False
        else:
            print("❌ Не удалось получить cookies из сессии")
            return False
    else:
        print("❌ Не удалось обновить сессию через refresh token")
        return False

def test_cookies_validation_after_refresh():
    """Тест валидации cookies после обновления через refresh token"""
    print("\n✅ Тестируем валидацию cookies после обновления...")
    
    account_name = "JkzbuMjpDL"
    storage = SqlAlchemyCookieStorage()
    
    # Загружаем cookies из БД
    cookies = storage.load_cookies(account_name)
    
    if not cookies:
        print("❌ Cookies не найдены в БД")
        return False
    
    print(f"✅ Cookies загружены из БД для {account_name}")
    print(f"📋 Количество cookies: {len(cookies)}")
    
    # Проверяем наличие критически важных cookies в сложной структуре
    critical_cookies = ['sessionid', 'steamLoginSecure']
    found_cookies = []
    
    # Ищем cookies в сложной структуре
    if 'cookies' in cookies:
        for domain, paths in cookies['cookies'].items():
            for path, cookies_dict in paths.items():
                for cookie_name, cookie_data in cookies_dict.items():
                    if cookie_name in critical_cookies:
                        found_cookies.append(cookie_name)
                        print(f"✅ Критический cookie '{cookie_name}' присутствует в домене {domain}")
    
    # Проверяем, что все критически важные cookies найдены
    missing_cookies = [cookie for cookie in critical_cookies if cookie not in found_cookies]
    if missing_cookies:
        print(f"⚠️ Отсутствуют критически важные cookies: {missing_cookies}")
        return False
    else:
        print("✅ Все критически важные cookies присутствуют")
        return True

def test_session_alive_after_refresh():
    """Тест активности сессии после обновления через refresh token"""
    print("\n🔄 Тестируем активность сессии после обновления...")
    
    account_name = "JkzbuMjpDL"
    pkl_path = f"accounts_info/{account_name}.pkl"
    
    if not os.path.exists(pkl_path):
        print("❌ Pkl файл не найден")
        return False
    
    try:
        # Создаем SteamClient
        steam_client = SteamClient(
            username=account_name,
            session_path=pkl_path
        )
        
        # Проверяем активность сессии
        if steam_client.check_session_static(account_name, steam_client._session):
            print("✅ Сессия активна после обновления через refresh token")
            return True
        else:
            print("❌ Сессия неактивна после обновления")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка проверки сессии: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Запуск реального теста входа через refresh token...")
    
    # Тест 1: Вход через refresh token и обновление cookies в БД
    success1 = test_real_refresh_token_login()
    
    if success1:
        # Тест 2: Валидация cookies после обновления
        success2 = test_cookies_validation_after_refresh()
        
        # Тест 3: Проверка активности сессии
        success3 = test_session_alive_after_refresh()
        
        if success1 and success2 and success3:
            print("\n🎉 Все тесты прошли успешно!")
            print("✅ Вход через refresh token работает")
            print("✅ Cookies обновляются в БД")
            print("✅ Сессия остается активной")
        else:
            print("\n⚠️ Некоторые тесты не прошли")
    else:
        print("\n❌ Основной тест не прошел")
    
    print("\n�� Тест завершен!")
