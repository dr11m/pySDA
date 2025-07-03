#!/usr/bin/env python3
"""
Cookie Manager - Модуль-синглтон для управления Steam cookies
"""

import os
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any
from threading import Lock

from src.utils.logger_setup import logger
from src.steampy.client import SteamClient
from src.interfaces.storage_interface import CookieStorageInterface, FileCookieStorage


class CookieManager:
    """Синглтон для управления Steam cookies"""
    
    _instance: Optional['CookieManager'] = None
    _lock = Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, 
                 username: str = None,
                 password: str = None,
                 mafile_path: str = None,
                 steam_id: str = None,
                 storage: CookieStorageInterface = None,
                 accounts_dir: str = "accounts_info",
                 proxy_manager=None):
        
        # Предотвращаем повторную инициализацию
        if hasattr(self, '_initialized'):
            return
        
        self.username = username
        self.password = password
        self.mafile_path = mafile_path
        self.steam_id = steam_id
        self.proxy_manager = proxy_manager
        
        # Инициализация хранилища
        self.storage = storage or FileCookieStorage(accounts_dir)
        
        # Папка для сессий steampy
        self.accounts_dir = Path(accounts_dir)
        self.accounts_dir.mkdir(exist_ok=True)
        self.session_file = self.accounts_dir / f"{username}.pkl"
        
        # Состояние
        self.steam_client: Optional[SteamClient] = None
        self.last_update: Optional[datetime] = None
        self.cookies_cache: Optional[Dict[str, str]] = None
        
        self._initialized = True
        
        logger.info(f"🍪 Cookie Manager инициализирован для {username}")
        logger.info(f"📁 Сессии: {self.session_file}")
        logger.info(f"📄 MaFile: {mafile_path}")
    
    def session_to_dict(self, session) -> Dict[str, str]:
        """Преобразование сессии в словарь cookies"""
        try:
            if hasattr(session, 'cookies'):
                if hasattr(session.cookies, 'get_dict'):
                    # requests.cookies.RequestsCookieJar
                    return session.cookies.get_dict()
                else:
                    # Другие типы cookie jar
                    cookies = {}
                    for cookie in session.cookies:
                        cookies[cookie.name] = cookie.value
                    return cookies
            return {}
        except Exception as e:
            logger.error(f"Ошибка преобразования сессии в словарь: {e}")
            return {}
    
    def dict_to_session_cookies(self, cookies_dict: Dict[str, str], session) -> bool:
        """Загрузка cookies из словаря в сессию"""
        try:
            session.cookies.clear()
            session.cookies.update(cookies_dict)
            logger.info(f"Загружено {len(cookies_dict)} cookies в сессию")
            return True
        except Exception as e:
            logger.error(f"Ошибка загрузки cookies в сессию: {e}")
            return False
    
    def _get_proxy_for_client(self) -> Optional[Dict[str, str]]:
        """Получение прокси для Steam клиента"""
        if not self.proxy_manager:
            return None
        
        try:
            current_proxy = self.proxy_manager.get_current_proxy()
            if not current_proxy:
                logger.error("Нет доступных прокси")
                return None
            
            proxy_dict = self.proxy_manager.proxy_to_dict(current_proxy)
            logger.info(f"🌐 Используем прокси: {self.proxy_manager.proxy_to_key(current_proxy)}")
            return proxy_dict
        except Exception as e:
            logger.error(f"Ошибка получения прокси: {e}")
            return None
    
    def _handle_proxy_ban(self) -> bool:
        """Обработка бана прокси и переключение на следующий"""
        if not self.proxy_manager:
            return False
        
        try:
            current_proxy = self.proxy_manager.get_current_proxy()
            if current_proxy:
                logger.warning(f"🚫 Баним текущий прокси: {self.proxy_manager.proxy_to_key(current_proxy)}")
                self.proxy_manager.ban_proxy(current_proxy, ban_duration_minutes=30)
            
            next_proxy = self.proxy_manager.rotate_to_next_proxy()
            if next_proxy:
                logger.info(f"🔄 Переключились на прокси: {self.proxy_manager.proxy_to_key(next_proxy)}")
                return True
            else:
                logger.error("🚫 Нет доступных прокси для переключения")
                return False
        except Exception as e:
            logger.error(f"Ошибка обработки бана прокси: {e}")
            return False
    
    def _create_steam_client(self) -> Optional[SteamClient]:
        """Создание Steam клиента с прокси"""
        try:
            proxies = self._get_proxy_for_client() if self.proxy_manager else None
            
            steam_client = SteamClient(
                session_path=str(self.session_file),
                username=self.username,
                password=self.password,
                steam_id=self.steam_id,
                steam_guard=self.mafile_path,
                proxies=proxies
            )
            
            logger.info("✅ Steam клиент создан")
            return steam_client
        except Exception as e:
            logger.error(f"❌ Ошибка создания Steam клиента: {e}")
            return None
    
    def _is_session_alive(self) -> bool:
        """Проверка актуальности текущей сессии"""
        if not self.steam_client:
            return False
        
        try:
            # Используем статический метод проверки сессии
            is_alive = self.steam_client.check_session_static(
                self.username, 
                self.steam_client._session
            )
            
            if is_alive:
                logger.info("✅ Сессия активна")
            else:
                logger.info("❌ Сессия неактивна")
            
            return is_alive
        except Exception as e:
            logger.error(f"❌ Ошибка проверки сессии: {e}")
            return False
    
    def _login_and_save_session(self) -> bool:
        """Выполнение входа и сохранение сессии"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔑 Создаем Steam клиента (попытка {attempt + 1})...")
                self.steam_client = self._create_steam_client()
                
                if not self.steam_client:
                    logger.error("Не удалось создать Steam клиента")
                    continue
                
                # Проверяем существующую сессию
                if self._is_session_alive():
                    logger.info("✅ Используем существующую активную сессию")
                    self.steam_client.was_login_executed = True
                    return True
                
                # Если сессия неактивна - выполняем новый вход
                logger.info("🔄 Сессия неактивна, выполняем новый вход...")
                self.steam_client._session.cookies.clear()
                
                # Выполняем вход
                self.steam_client.login_if_need_to()
                
                # Сохраняем сессию
                logger.info("💾 Сохраняем сессию...")
                self.steam_client.save_session(str(self.accounts_dir), username=self.username)
                
                self.steam_client.was_login_executed = True
                
                logger.info("✅ Успешный вход и сохранение сессии")
                return True
                
            except Exception as e:
                logger.error(f"❌ Ошибка входа (попытка {attempt + 1}): {e}")
                
                # Проверяем, связана ли ошибка с прокси
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ['429', 'too many requests', 'proxy', 'connection']):
                    if self.proxy_manager and attempt < max_retries - 1:
                        logger.info("🔄 Ошибка связана с прокси, пробуем переключиться...")
                        if self._handle_proxy_ban():
                            continue
                
                if attempt == max_retries - 1:
                    logger.debug(traceback.format_exc())
        
        logger.error(f"❌ Все попытки входа исчерпаны ({max_retries})")
        return False
    
    def is_cookies_valid(self, max_age_minutes: int = 120) -> bool:
        """Проверка актуальности cookies"""
        # Проверяем время последнего обновления
        last_update = self.storage.get_last_update(self.username)
        if not last_update:
            logger.info("🔄 Cookies никогда не обновлялись")
            return False
        
        time_passed = datetime.now() - last_update
        max_age = timedelta(minutes=max_age_minutes)
        
        if time_passed > max_age:
            logger.info(f"⏰ Cookies устарели (прошло {int(time_passed.total_seconds() // 60)} минут)")
            return False
        
        # Проверяем наличие cookies в кэше или хранилище
        if not self.cookies_cache:
            self.cookies_cache = self.storage.load_cookies(self.username)
        
        if not self.cookies_cache:
            logger.info("🔄 Cookies не найдены в хранилище")
            return False
        
        # Проверяем ключевые cookies
        required_cookies = ['sessionid', 'steamLoginSecure']
        for cookie_name in required_cookies:
            if cookie_name not in self.cookies_cache:
                logger.info(f"❌ Отсутствует обязательный cookie: {cookie_name}")
                return False
        
        logger.info(f"✅ Cookies актуальны (возраст: {int(time_passed.total_seconds() // 60)} минут)")
        return True
    
    def update_cookies(self, force: bool = False) -> Optional[Dict[str, str]]:
        """
        Основной метод обновления cookies
        
        Args:
            force: Принудительное обновление независимо от актуальности
            
        Returns:
            Dict[str, str] или None: Актуальные cookies
        """
        try:
            # Проверяем актуальность cookies
            if not force and self.is_cookies_valid():
                logger.info("✅ Cookies актуальны, обновление не требуется")
                return self.cookies_cache or self.storage.load_cookies(self.username)
            
            logger.info(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Обновление cookies для {self.username}")
            
            # Выполняем вход и получаем новую сессию
            if not self._login_and_save_session():
                logger.error("❌ Не удалось войти в Steam")
                return None
            
            # Получаем cookies из сессии
            cookies = self.session_to_dict(self.steam_client._session)
            if not cookies:
                logger.error("❌ Не удалось получить cookies из сессии")
                return None
            
            logger.info(f"🍪 Получено {len(cookies)} cookies")
            
            # Показываем важные cookies
            important = ['sessionid', 'steamLoginSecure']
            for cookie_name in important:
                if cookie_name in cookies:
                    value = cookies[cookie_name][:20] + "..." if len(cookies[cookie_name]) > 20 else cookies[cookie_name]
                    logger.info(f"   {cookie_name}: {value}")
            
            # Сохраняем cookies в хранилище
            if self.storage.save_cookies(self.username, cookies):
                logger.info("✅ Cookies сохранены в хранилище")
                self.cookies_cache = cookies
                self.last_update = datetime.now()
            else:
                logger.warning("⚠️ Не удалось сохранить cookies в хранилище")
            
            return cookies
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления cookies: {e}")
            logger.debug(traceback.format_exc())
            return None
    
    def get_cookies(self, auto_update: bool = True) -> Optional[Dict[str, str]]:
        """
        Получение актуальных cookies
        
        Args:
            auto_update: Автоматически обновлять cookies если нужно
            
        Returns:
            Dict[str, str] или None: Актуальные cookies
        """
        # Если есть кэш и он актуален - возвращаем его
        if self.cookies_cache and self.is_cookies_valid():
            return self.cookies_cache
        
        # Пробуем загрузить из хранилища
        if not self.cookies_cache:
            self.cookies_cache = self.storage.load_cookies(self.username)
        
        # Если cookies все еще актуальны - возвращаем
        if self.cookies_cache and self.is_cookies_valid():
            return self.cookies_cache
        
        # Если нужно автообновление - обновляем
        if auto_update:
            return self.update_cookies()
        
        logger.warning("⚠️ Cookies неактуальны, но автообновление отключено")
        return self.cookies_cache
    
    def get_steam_client(self) -> Optional[SteamClient]:
        """Получение настроенного Steam клиента с сессией из pkl"""
        # Если клиент уже есть и сессия активна - возвращаем его
        if self.steam_client and hasattr(self.steam_client, 'was_login_executed') and self.steam_client.was_login_executed:
            return self.steam_client
        
        # Проверяем актуальность cookies
        cookies = self.get_cookies()
        if not cookies:
            logger.error("Не удалось получить актуальные cookies для клиента")
            return None
        
        # Если у нас еще нет steam_client или он не готов, создаем/инициализируем его
        if not self.steam_client:
            logger.info("🔄 Создаем Steam клиента для работы с актуальными cookies...")
            self.steam_client = self._create_steam_client()
            if not self.steam_client:
                logger.error("❌ Не удалось создать Steam клиента")
                return None
        
        # Убеждаемся, что у клиента есть активная сессия
        if not hasattr(self.steam_client, 'was_login_executed') or not self.steam_client.was_login_executed:
            logger.info("🔄 Проверяем активность сессии...")
            try:
                # Проверяем активность текущей сессии
                if self._is_session_alive():
                    logger.info("✅ Сессия активна")
                    self.steam_client.was_login_executed = True
                else:
                    logger.info("⚠️ Сессия неактивна, выполняем вход...")
                    # Выполняем вход
                    if not self._login_and_save_session():
                        logger.error("❌ Не удалось выполнить вход")
                        return None
            except Exception as e:
                logger.error(f"❌ Ошибка проверки сессии: {e}")
                # Пробуем выполнить вход в случае ошибки
                try:
                    if not self._login_and_save_session():
                        logger.error("❌ Не удалось выполнить вход после ошибки")
                        return None
                except Exception as login_error:
                    logger.error(f"❌ Критическая ошибка входа: {login_error}")
                    return None
        
        return self.steam_client
    
    def clear_cache(self):
        """Очистка кэша cookies"""
        self.cookies_cache = None
        self.last_update = None
        logger.info("🧹 Кэш cookies очищен")


# Глобальный экземпляр (будет создан при первом импорте)
_cookie_manager_instance: Optional[CookieManager] = None


def get_cookie_manager(**kwargs) -> CookieManager:
    """Получение глобального экземпляра Cookie Manager"""
    global _cookie_manager_instance
    
    if _cookie_manager_instance is None:
        _cookie_manager_instance = CookieManager(**kwargs)
    
    return _cookie_manager_instance


def initialize_cookie_manager(username: str, password: str, mafile_path: str, 
                            steam_id: str = None, storage: CookieStorageInterface = None,
                            accounts_dir: str = "accounts_info", proxy_manager=None) -> CookieManager:
    """Инициализация глобального Cookie Manager"""
    global _cookie_manager_instance
    
    _cookie_manager_instance = CookieManager(
        username=username,
        password=password, 
        mafile_path=mafile_path,
        steam_id=steam_id,
        storage=storage,
        accounts_dir=accounts_dir,
        proxy_manager=proxy_manager
    )
    
    return _cookie_manager_instance 