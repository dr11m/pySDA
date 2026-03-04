#!/usr/bin/env python3
"""
Cookie Manager - Модуль для управления Steam cookies для конкретного аккаунта
"""

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Any
from src.utils.logger_setup import logger, print_and_log, log_exception
from src.steampy.client import SteamClient
from src.interfaces.storage_interface import CookieStorageInterface as StorageInterface
from src.utils.delayed_http_adapter import DelayedHTTPAdapter
from src.utils.cookies_and_session import session_to_dict
from src.cli.config_manager import global_config


class CookieManager:
    """Менеджер для управления Steam cookies для конкретного аккаунта"""
    
    def __init__(self, 
                 username: str = None,
                 password: str = None,
                 mafile_path: str = None,
                 steam_id: str = None,
                 storage: StorageInterface = None,
                 accounts_dir: str = "accounts_info",
                 proxy: Optional[Dict[str, str]] = None,
                 request_delay_sec: float = 0):
        
        self.username = username
        self.password = password
        self.mafile_path = mafile_path
        self.steam_id = steam_id
        self.proxy = proxy
        self.request_delay_sec = request_delay_sec  # Сохраняем задержку
        
        # Инициализация хранилища
        self.storage = storage
        
        # Папка для сессий steampy
        self.accounts_dir = Path(accounts_dir)
        self.accounts_dir.mkdir(exist_ok=True)
        self.session_file = self.accounts_dir / f"{username}.pkl"
        
        # Состояние
        self.steam_client: Optional[SteamClient] = None
        self.last_update: Optional[datetime] = None
        self.cookies_cache: Optional[Dict[str, str]] = None
        
        # Создаем SteamClient здесь, как и было раньше
        self.client = SteamClient(
            username=username,
            password=password,
            steam_guard=mafile_path,
            steam_id=steam_id,
            proxies=proxy,
            storage=storage
        )

        # Если указано отсутствие прокси, гарантируем прямое соединение для сессии
        if proxy is None and hasattr(self.client, "_session"):
            self._enforce_direct_connection(self.client._session)

        # И здесь же монтируем адаптер, если это необходимо
        if request_delay_sec > 0:
            adapter = DelayedHTTPAdapter(delay=request_delay_sec)
            self.client._session.mount('http://', adapter)
            self.client._session.mount('https://', adapter)
            logger.debug(f"Для клиента '{username}' установлен HTTP/S адаптер с задержкой {request_delay_sec:.2f} сек.")
        
        logger.info(f"🍪 Cookie Manager инициализирован для {username}")
        logger.info(f"📁 Сессии: {self.session_file}")
        logger.info(f"📄 MaFile: {mafile_path}")
        if self.proxy:
            logger.info(f"🌐 Используется прокси: {self.proxy.get('http')}")
    

    def dict_to_session_cookies(self, cookies_dict: Dict[str, str], session) -> bool:
        """Загрузка cookies из словаря в сессию"""
        try:
            session.cookies.clear()
            session.cookies.update(cookies_dict)
            logger.info(f"Загружено {len(cookies_dict)} cookies в сессию")
            return True
        except Exception as e:
            log_exception("Failed to load cookies into session.")
            logger.error(f"Ошибка загрузки cookies в сессию: {e}")
            return False
    
    def _create_steam_client(self) -> Optional[SteamClient]:
        """Создание Steam клиента с прокси"""
        try:
            steam_client = SteamClient(
                session_path=str(self.session_file),
                username=self.username,
                password=self.password,
                steam_id=self.steam_id,
                steam_guard=self.mafile_path,
                proxies=self.proxy,
                storage=self.storage
            )
            
            # Если прокси нет — принудительно прямое соединение (без ENV и старых прокси)
            if self.proxy is None and hasattr(steam_client, "_session"):
                self._enforce_direct_connection(steam_client._session)


            # Устанавливаем HTTP адаптер с задержкой если она настроена
            if hasattr(self, 'request_delay_sec') and self.request_delay_sec > 0:
                adapter = DelayedHTTPAdapter(delay=self.request_delay_sec)
                steam_client._session.mount('http://', adapter)
                steam_client._session.mount('https://', adapter)
                logger.debug(f"Для нового Steam клиента '{self.username}' установлен HTTP адаптер с задержкой {self.request_delay_sec:.2f} сек.")
            
            logger.info("✅ Steam клиент создан")
            return steam_client
        except Exception as e:
            log_exception("Failed to create Steam client.")
            logger.error(f"❌ Ошибка создания Steam клиента: {e}")
            return None

    def _enforce_direct_connection(self, session) -> None:
        """Отключает любые прокси и ENV-прокси для переданной сессии requests."""
        if hasattr(session, "trust_env"):  # Страхуем себя от системных прокси
            session.trust_env = False
        if hasattr(session, "proxies") and isinstance(session.proxies, dict):
            session.proxies.clear()
    
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
            log_exception("Failed to check session status.")
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
                
                # Выполняем вход
                self.steam_client.login_if_need_to()
                
                # Сохраняем сессию
                logger.info("💾 Сохраняем сессию...")
                self.steam_client.save_session(str(self.accounts_dir), username=self.username)
                
                self.steam_client.was_login_executed = True
                
                logger.info("✅ Успешный вход и сохранение сессии")
                return True
                
            except Exception as e:
                log_exception("Login attempt failed.")
                logger.error(f"❌ Ошибка входа (попытка {attempt + 1}): {e}")
                
                # Упрощенная обработка ошибок без смены прокси
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ['429', 'too many requests', 'proxy', 'connection']):
                    logger.warning("Проблема с соединением или прокси. Повторная попытка через некоторое время...")
                    time.sleep(5) # Пауза перед следующей попыткой
                
        logger.error(f"❌ Все попытки входа исчерпаны ({max_retries})")
        return False
    
    def is_cookies_valid(self, max_age_minutes: int = None) -> bool:
        """Проверка актуальности cookies"""
        # Используем значение из конфига, если не передано явно
        if max_age_minutes is None:
            max_age_minutes = global_config.get_max_cookie_age_minutes()
        
        # Проверяем время последнего обновления
        last_update = self.storage.get_last_update(self.username)
        if not last_update:
            logger.info("🔄 Cookies никогда не обновлялись")
            return False
        
        # Приводим оба времени к UTC для корректного сравнения
        now_utc = datetime.now(timezone.utc)
        if last_update.tzinfo is None:
            # Если last_update без timezone, считаем что это UTC
            last_update_utc = last_update.replace(tzinfo=timezone.utc)
        else:
            last_update_utc = last_update.astimezone(timezone.utc)
        
        time_passed = now_utc - last_update_utc
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
            # Если не требуется принудительное обновление и cookies ещё действительны — просто возвращаем их, не обновляем
            if not force and self.is_cookies_valid():
                logger.info("✅ Cookies актуальны, обновление не требуется")
                return self.cookies_cache or self.storage.load_cookies(self.username)
            
            logger.info(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Обновление cookies для {self.username}")
            
            print_and_log(f"🔄 Обновление cookies (сессии) для {self.username}")
            if not self.steam_client:
                self.steam_client = self._create_steam_client()
            
            if not force:
                print_and_log(f"🔄 Проверяем активность сессии для {self.username}, если она активна, то обновление не требуется")
                is_username_exist_via_trade_url = self.steam_client.check_session_via_trade_url(self.username, self.steam_client._session)
                is_username_exist = self.steam_client.check_session_static(self.username, self.steam_client._session)
                print_and_log(f"🔄 is_username_exist_via_trade_url: {is_username_exist_via_trade_url}")
                print_and_log(f"🔄 is_username_exist: {is_username_exist}")
                if is_username_exist_via_trade_url is True and is_username_exist is True:
                    #обновляем время
                    logger.info(f"🍪 Cookies актуальны после проверки! Обновляем время последнего обновления cookies для {self.username}")
                    self.last_update = datetime.now()
                    self.cookies_cache = self.storage.load_cookies(self.username)
                    self.storage.save_cookies(self.username, self.cookies_cache)
                    return self.cookies_cache

            self.steam_client.login_if_need_to()
            
            # Получаем cookies из сессии
            cookies = session_to_dict(self.steam_client._session)
            if not cookies:
                logger.error("❌ Не удалось получить cookies из сессии")
                return None
            
            logger.info(f"🍪 Получено {len(cookies)} cookies")
            
            # Сохраняем cookies в хранилище
            if self.storage.save_cookies(self.username, cookies):
                print_and_log("✅ Cookies сохранены в хранилище")
                self.cookies_cache = cookies
                self.last_update = datetime.now()
            else:
                raise Exception("Не удалось сохранить cookies в хранилище")
            
            return cookies
            
        except Exception as e:
            log_exception("Cookie update failed.")
            logger.error(f"❌ Ошибка обновления cookies: {e}")
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
            logger.info(f"✅ Cookies актуальны, возвращаем кэш для {self.username}")
            return self.cookies_cache
        
        # Пробуем загрузить из хранилища
        if not self.cookies_cache:
            self.cookies_cache = self.storage.load_cookies(self.username)
        
        # Если cookies все еще актуальны - возвращаем
        if self.cookies_cache and self.is_cookies_valid():
            return self.cookies_cache
        
        # Если нужно автообновление - обновляем
        if auto_update:
            max_age = global_config.get_max_cookie_age_minutes()
            logger.info(f"🔄 Обновление cookies для {self.username} так как auto_update = True и прошло больше {max_age} минут")
            return self.update_cookies()
        
        logger.warning("⚠️ Cookies неактуальны, но автообновление отключено")
        return self.cookies_cache
    
    def get_steam_client(self) -> Optional[SteamClient]:
        """Получение настроенного Steam клиента с сессией из pkl"""
        logger.info("🔍 get_steam_client() вызван")
        
        # Если клиент уже есть и сессия активна - возвращаем его
        if self.steam_client and hasattr(self.steam_client, 'was_login_executed') and self.steam_client.was_login_executed:
            logger.info("✅ Возвращаем существующий активный клиент")
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
                    self.steam_client.was_login_executed = True  # Set flag to indicate login is done
                else:
                    logger.info("⚠️ Сессия неактивна, выполняем вход...")
                    # Выполняем вход
                    if not self._login_and_save_session():
                        logger.error("❌ Не удалось выполнить вход")
                        return None
            except Exception as e:
                log_exception("Session validation failed before returning Steam client.")
                logger.error(f"❌ Ошибка проверки сессии: {e}")
                # Пробуем выполнить вход в случае ошибки
                try:
                    if not self._login_and_save_session():
                        logger.error("❌ Не удалось выполнить вход после ошибки")
                        return None
                except Exception as login_error:
                    log_exception("Critical login flow failure.")
                    logger.error(f"❌ Критическая ошибка входа: {login_error}")
                    return None
        
        # Показываем cookies в возвращаемом клиенте
        if self.steam_client and hasattr(self.steam_client, '_session'):
            client_cookies = [f"{cookie.name}@{cookie.domain}" for cookie in self.steam_client._session.cookies]
            logger.info(f"📋 Cookies в возвращаемом клиенте: {client_cookies}")
        
        return self.steam_client
    
    def clear_cache(self):
        """Очистка кэша cookies"""
        self.cookies_cache = None
        self.last_update = None
        logger.info("🧹 Кэш cookies очищен")


def initialize_cookie_manager(
    username: str,
    password: str,
    mafile_path: str,
    steam_id: str,
    storage: StorageInterface,
    accounts_dir: str = 'accounts_info',
    proxy: Optional[Dict[str, str]] = None,
    request_delay_sec: float = 0
) -> "CookieManager":
    """
    Фабричная функция для создания или получения существующего экземпляра CookieManager.
    """
    # Просто создаем и возвращаем новый экземпляр со всеми параметрами.
    return CookieManager(
        username=username,
        password=password,
        mafile_path=mafile_path,
        steam_id=steam_id,
        storage=storage,
        accounts_dir=accounts_dir,
        proxy=proxy,
        request_delay_sec=request_delay_sec
    ) 
