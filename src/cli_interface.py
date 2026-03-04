#!/usr/bin/env python3
"""
Рефакторенный CLI Interface - Модульный интерфейс для управления проектом

Архитектура:
- Разделение ответственности между компонентами
- Использование паттерна Command для действий меню
- Dependency Injection для управления зависимостями
- Четкая структура с базовыми классами и конкретными реализациями
"""

import sys
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

# Добавляем корневую папку в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.steampy.guard import generate_one_time_code
from src.cli.constants import MenuChoice, Messages
from src.cli.display_formatter import DisplayFormatter
from src.cli.config_manager import ConfigManager
from src.cli.cookie_checker import CookieChecker
from src.cli.menus import MainMenu, TradesMenu, AutoMenu
from src.cli.menus import SettingsMenu
from src.cli.menu_base import BaseMenu, NavigableMenu, MenuItem
from src.models import TradeOffer
from src.trade_confirmation_manager import TradeConfirmationManager
from src.cli.account_context import AccountContext, build_account_context
from src.cli.trade_handlers import (
    GiftAcceptHandler, SpecificTradeHandler
)
from src.utils.logger_setup import logger, log_exception
from src.cookie_manager import initialize_cookie_manager


class SteamBotCLI:
    """
    Рефакторенный CLI интерфейс для Steam бота
    
    Основные принципы:
    - Single Responsibility: каждый класс отвечает за одну область
    - Dependency Injection: зависимости передаются через конструктор
    - Open/Closed: легко расширяется новыми меню и действиями
    """
    
    def __init__(self):
        # Основные компоненты
        self.active_account_context: Optional[AccountContext] = None
        self.selected_account_name: Optional[str] = None
        
        self.config_manager = ConfigManager()
        
        # UI компоненты
        self.formatter = DisplayFormatter()
        self.active_trades_cache = None
        self.active_trades_cache_time = 0
        self.cookie_checker = None
        
        print("🤖 Steam Bot CLI v2.0 (Refactored)")
        print("=" * 50)
    
    def initialize_for_account(self, account_name: str) -> bool:
        """Инициализация для выбранного аккаунта."""
        # Используем новую фабрику для создания контекста
        context = build_account_context(self.config_manager, account_name)
        
        if context:
            self.active_account_context = context
            self.selected_account_name = account_name
            print(self.formatter.format_success(f"{Messages.INIT_SUCCESS}: {self.active_account_context.username}"))
            return True
        else:
            print(self.formatter.format_error(f"Не удалось инициализировать аккаунт '{account_name}'."))
            self.active_account_context = None
            self.selected_account_name = None
            return False

    def select_and_initialize_account(self) -> bool:
        """Отображает меню выбора аккаунта и инициализирует его."""
        # Загружаем аккаунты из конфигурационного файла
        account_names = self.config_manager.get_all_account_names()
        
        if not account_names:
            print(self.formatter.format_error("Не найдены аккаунты в конфигурационном файле. "
                                              "Добавьте аккаунты в секцию 'accounts' в config.yaml"))
            return False
            
        print(self.formatter.format_section_header("Выберите аккаунт"))
        for i, name in enumerate(account_names, 1):
            display_name = self.config_manager.get_account_display_name(name)
            print(f"  {i}. {display_name}")
        print("  0. Назад")
        
        while True:
            try:
                choice = input("Введите номер: ")
                if choice == "0":
                    return False # Возвращаемся в главное меню без изменений
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(account_names):
                    selected_name = account_names[choice_idx]
                    display_name = self.config_manager.get_account_display_name(selected_name)
                    print(f"Инициализация для аккаунта {display_name}...")
                    return self.initialize_for_account(selected_name)
                else:
                    print("Неверный номер. Попробуйте снова.")
            except ValueError:
                print("Неверный ввод. Введите число.")

    def _is_account_selected(self) -> bool:
        if not self.active_account_context:
            print(self.formatter.format_error("Сначала необходимо выбрать аккаунт (пункт 1)."))
            return False
        return True

    def update_cookies(self) -> bool:
        """Принудительное обновление cookies"""
        if not self._is_account_selected():
            return False
        try:
            print(self.formatter.format_section_header("🍪 Принудительное обновление cookies..."))
            print("ℹ️  Обычно cookies обновляются автоматически при необходимости.")
            print("ℹ️  Принудительное обновление полезно при проблемах с доступом.")
            print()
            
            cookies = self.active_account_context.cookie_manager.update_cookies(force=True)
            
            if cookies:
                print(self.formatter.format_cookies_info(cookies))
                return True
            else:
                print(self.formatter.format_error("Не удалось обновить cookies"))
                return False
                
        except Exception as e:
            log_exception("Cookie update failed.")
            print(self.formatter.format_error("Ошибка обновления cookies (сессии)", e))
            return False
    
    def get_guard_code(self) -> bool:
        """Получение Guard кода"""
        if not self._is_account_selected():
            return False
        try:
            print(self.formatter.format_section_header("🔑 Генерация Guard кода..."))
            print("ℹ️  Код действителен в течение 30 секунд.")
            print("ℹ️  Используйте его для ручного подтверждения трейдов в Steam.")
            print()
            
            # Генерируем Guard код через trade_manager из контекста
            guard_code = self.active_account_context.trade_manager.generate_guard_code()
            
            if guard_code:
                print(self.formatter.format_success(Messages.GUARD_CODE_GENERATED.format(code=guard_code)))
                return True
            else:
                print(self.formatter.format_error("Не удалось сгенерировать Guard код"))
                return False
                
        except Exception as e:
            log_exception("Guard code generation failed.")
            print(self.formatter.format_error(Messages.GUARD_CODE_GENERATION_ERROR, e))
            return False
    
    def get_active_trades(self) -> Optional[List[TradeOffer]]:
        """Получение списка активных обменов"""
        if not self._is_account_selected():
            return None
            
        # Проверяем кэш
        if self.active_trades_cache and (time.time() - self.active_trades_cache_time) < 30:
            return self.active_trades_cache
            
        try:
            # Используем trade_manager из контекста
            trades = self.active_account_context.trade_manager.get_trade_offers(active_only=True)
            
            if trades:
                all_trades = trades.active_received + trades.active_sent
                
                # Кэшируем результат
                self.active_trades_cache = all_trades
                self.active_trades_cache_time = time.time()
                
                return all_trades
            else:
                print("❌ Не удалось получить трейд офферы")
                return None
            
        except Exception as e:
            log_exception("Failed to fetch active trades.")
            print(self.formatter.format_error("Ошибка при получении трейдов: ", e))
            return None
    
    def get_all_trades(self) -> Optional[List[TradeOffer]]:
        """Получение списка всех трейдов (активные + требующие подтверждения)"""
        if not self._is_account_selected():
            return None
            
        try:
            # Используем trade_manager из контекста для получения всех трейдов
            trades = self.active_account_context.trade_manager.get_trade_offers(active_only=False)
            
            if trades:
                # Объединяем все типы трейдов
                all_trades = []
                all_trades.extend(trades.active_received)
                all_trades.extend(trades.active_sent)
                all_trades.extend(trades.confirmation_needed_received)
                all_trades.extend(trades.confirmation_needed_sent)
                
                return all_trades
            else:
                print("❌ Не удалось получить трейд офферы")
                return None
            
        except Exception as e:
            log_exception("Failed to fetch trades list.")
            print(self.formatter.format_error("Ошибка при получении трейдов: ", e))
            return None
    
    def run(self):
        """Запуск CLI интерфейса"""
        if not self.config_manager.load_config():
            print("❌ Не удалось загрузить config.yaml")
            return
        
        # Основной цикл с использованием нового меню
        try:
            main_menu = MainMenu(self)
            main_menu.run()
        except KeyboardInterrupt:
            print(f"\n{Messages.INTERRUPTED}")
        except Exception as e:
            log_exception("Critical CLI runtime error.")
            print(f"\n{Messages.CRITICAL_ERROR.format(error=e)}")


class TradesMenu(NavigableMenu):
    """Меню управления трейдами"""
    
    def __init__(self, cli_context: SteamBotCLI):
        super().__init__(Messages.MANAGE_TRADES_TITLE)
        self.cli = cli_context
        
        # Получаем нужные менеджеры из контекста
        tm = self.cli.active_account_context.trade_manager
        cc = self.cli.active_account_context.cookie_checker
        trades = self.cli.get_active_trades() or []
        
        # Настраиваем обработчики
        self.gift_handler = GiftAcceptHandler(tm, self.cli.formatter, cc)
        self.specific_trade_handler = SpecificTradeHandler(tm, self.cli.formatter, trades, cc)
        self.market_lister = MarketListHandler(tm, cc, self.cli.formatter)

    def _get_trades_and_handle_none(self):
        trades = self.cli.get_active_trades()
        if trades is None or not trades:
            if trades is not None: # Если trades пуст, но не None
                print(self.cli.formatter.format_info("Активных трейдов не найдено."))
            input(Messages.PRESS_ENTER)
            return None, True # Возвращаем True для выхода из меню
        return trades, False

    def setup_menu(self):
        self.items.clear()
        
        trades, should_exit = self._get_trades_and_handle_none()
        if should_exit:
            # Настраиваем меню так, чтобы оно сразу вышло
            self.add_item(MenuItem("0", "Назад", self.exit_menu))
            return

        print(self.cli.formatter.format_trades_list(trades))
        
        self.add_item(MenuItem(MenuChoice.TRADE_ACCEPT_GIFT.value, Messages.ACCEPT_GIFT, self.gift_handler.execute))
        self.add_item(MenuItem(MenuChoice.TRADE_ACCEPT.value, Messages.ACCEPT_TRADE, self.accept_trade))
        self.add_item(MenuItem(MenuChoice.TRADE_DECLINE.value, Messages.DECLINE_TRADE, self.decline_trade))
        self.add_item(MenuItem(MenuChoice.TRADE_LIST_MARKET.value, Messages.LIST_ON_MARKET, lambda: self.market_lister.run(self.specific_trade_handler.trades_cache)))
        self.add_item(MenuItem(MenuChoice.REFRESH_TRADES.value, Messages.REFRESH_LIST, self.refresh_and_rerun))
        self.add_back_item()

    def accept_trade(self):
        trade_num = self.specific_trade_handler.get_trade_number()
        if trade_num:
            self.specific_trade_handler.accept_specific_trade(trade_num)
        self.refresh_and_rerun()

    def decline_trade(self):
        trade_num = self.specific_trade_handler.get_trade_number()
        if trade_num:
            self.specific_trade_handler.decline_specific_trade(trade_num)
        self.refresh_and_rerun()


def run_cli():
    """Основная функция запуска CLI"""
    cli = SteamBotCLI()
    cli.run()


if __name__ == "__main__":
    run_cli()
