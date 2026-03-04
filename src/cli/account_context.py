#!/usr/bin/env python3
"""
Контекст Аккаунта и Фабрика для его создания.
"""

from dataclasses import dataclass
from typing import Optional

from src.cookie_manager import CookieManager, initialize_cookie_manager
from src.trade_confirmation_manager import TradeConfirmationManager
from src.cli.cookie_checker import CookieChecker
from src.cli.config_manager import ConfigManager
from src.cli.display_formatter import DisplayFormatter
from src.factories import create_instance_from_config
from src.utils.logger_setup import logger, log_exception

@dataclass
class AccountContext:
    """
    Контейнер для всех сервисов, связанных с одним аккаунтом.
    """
    account_name: str
    username: str
    cookie_manager: CookieManager
    trade_manager: TradeConfirmationManager
    cookie_checker: CookieChecker
    accounts_dir: str
    config_manager: ConfigManager

def build_account_context(config_manager: ConfigManager, account_name: str) -> Optional[AccountContext]:
    """
    Фабрика для создания полного рабочего контекста для одного аккаунта.
    Инкапсулирует логику, которая раньше была в SteamBotCLI.initialize_for_account.
    """
    try:
        logger.info(f"🛠️  Создание контекста для аккаунта: {account_name}")
        
        # Выбираем аккаунт и валидируем его конфигурацию
        if not config_manager.select_account(account_name):
            logger.error(f"Конфигурация для аккаунта '{account_name}' не найдена.")
            return None
        if not config_manager.validate_config():
            logger.error(f"Конфигурация для '{account_name}' не прошла валидацию.")
            return None

        logger.info(f"Получение настроек для аккаунта {account_name}...")
        username = config_manager.get('username')
        password = config_manager.get('password')
        mafile_path = config_manager.get('mafile_path')
        steam_id = config_manager.get('steam_id')
        api_key = config_manager.get('api_key')  # Получаем API ключ из конфига
        accounts_dir = config_manager.get('accounts_dir', 'accounts_info')
        
        logger.info(f"Основные настройки: username={username}, mafile_path={mafile_path}, steam_id={steam_id}")
        
        # Получаем задержку из конфига и переводим в секунды
        delay_ms = config_manager.get('min_request_delay_ms', 0)
        request_delay_sec = delay_ms / 1000.0
        logger.info(f"Задержка запросов: {delay_ms}ms ({request_delay_sec}s)")

        # --- Динамическое создание зависимостей через фабрики ---
        logger.info("Получение конфигурации провайдеров...")
        proxy_provider_config = config_manager.get('proxy_provider')
        logger.info(f"proxy_provider_config: {proxy_provider_config}")
        
        proxy_provider = create_instance_from_config(proxy_provider_config)
        proxy = proxy_provider.get_proxy(account_name)
        logger.info(f"Прокси для аккаунта: {proxy}")
        
        storage_config = config_manager.get('cookie_storage')
        logger.info(f"storage_config: {storage_config}")
        storage_instance = create_instance_from_config(storage_config)

        # --- Инициализация менеджеров ---
        cookie_manager = initialize_cookie_manager(
            username=username,
            password=password,
            mafile_path=mafile_path,
            steam_id=steam_id,
            storage=storage_instance,
            accounts_dir=accounts_dir,
            proxy=proxy,
            request_delay_sec=request_delay_sec
        )
        
        trade_manager = TradeConfirmationManager(
            username=username,
            mafile_path=mafile_path,
            cookie_manager=cookie_manager,
            api_key=api_key  # Передаем API ключ из конфига
        )
        
        formatter = DisplayFormatter()
        cookie_checker = CookieChecker(cookie_manager, formatter)

        logger.success(f"✅ Контекст для '{account_name}' (user: {username}) успешно создан.")
        return AccountContext(
            account_name=account_name,
            username=username,
            cookie_manager=cookie_manager,
            trade_manager=trade_manager,
            cookie_checker=cookie_checker,
            accounts_dir=accounts_dir,
            config_manager=config_manager
        )

    except Exception:
        log_exception(f"Failed to build account context for '{account_name}'.")
        return None 
