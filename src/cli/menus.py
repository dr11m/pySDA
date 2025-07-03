#!/usr/bin/env python3
"""
Конкретные реализации меню
"""

from typing import Optional, List
from .menu_base import BaseMenu, NavigableMenu, MenuItem
from .constants import MenuChoice, TradeMenuChoice, SettingsMenuChoice, AutoMenuChoice, Messages, Formatting
from .trade_handlers import (
    GiftAcceptHandler, 
    TradeConfirmHandler, 
    SpecificTradeHandler,
    TradeCheckHandler
)
from .settings_manager import SettingsManager
from .auto_manager import AutoManager
from .market_handler import MarketHandler


class MainMenu(BaseMenu):
    """Главное меню приложения"""
    
    def __init__(self, cli_context):
        super().__init__(f"{Messages.MAIN_TITLE} - {cli_context.username or 'НЕ ИНИЦИАЛИЗИРОВАН'}")
        self.cli = cli_context
    
    def setup_menu(self):
        """Настроить элементы главного меню"""
        self.add_item(MenuItem(
            MenuChoice.UPDATE_COOKIES.value,
            Messages.UPDATE_COOKIES,
            self.cli.update_cookies
        ))
        
        self.add_item(MenuItem(
            MenuChoice.MANAGE_TRADES.value,
            "📋 Управление трейдами (получить + управлять)",
            self.open_trades_menu
        ))
        
        self.add_item(MenuItem(
            MenuChoice.CONFIRM_MARKET.value,
            Messages.CONFIRM_MARKET,
            self.confirm_market_orders
        ))
        
        self.add_item(MenuItem(
            MenuChoice.GET_GUARD_CODE.value,
            Messages.GET_GUARD_CODE,
            self.cli.get_guard_code
        ))
        
        self.add_item(MenuItem(
            MenuChoice.SETTINGS.value,
            Messages.SETTINGS,
            self.open_settings_menu
        ))
        
        self.add_item(MenuItem(
            MenuChoice.AUTO_ACCEPT.value,
            Messages.AUTO_ACCEPT,
            self.open_auto_menu
        ))
        
        self.add_item(MenuItem(
            MenuChoice.EXIT.value,
            Messages.EXIT,
            self.exit_app
        ))
    
    def open_trades_menu(self):
        """Открыть меню управления трейдами"""
        # Сначала получаем актуальный список трейдов
        print("🔄 Подготовка к управлению трейдами...")
        trades = self.cli.get_active_trades()
        
        if trades is None:
            print("❌ Не удалось получить список трейдов")
            return
        
        if not trades:
            return
        
        # Если есть трейды, открываем меню управления
        trades_menu = TradesMenu(self.cli)
        trades_menu.run()
    
    def confirm_market_orders(self):
        """Подтвердить все market ордера"""
        market_handler = MarketHandler(
            self.cli.trade_manager,
            self.cli.formatter,
            self.cli.cookie_checker
        )
        return market_handler.confirm_all_market_orders()
    
    def open_settings_menu(self):
        """Открыть меню настроек"""
        settings_menu = SettingsMenu(self.cli)
        settings_menu.run()
    
    def open_auto_menu(self):
        """Открыть меню автоматизации"""
        auto_menu = AutoMenu(self.cli)
        auto_menu.run()
    
    def exit_app(self):
        """Выйти из приложения"""
        print(Messages.GOODBYE)
        self.stop()
    
    def process_action_result(self, choice: str, result) -> bool:
        """Обработать результат действия"""
        if choice == MenuChoice.EXIT.value:
            return False
        return True


class TradesMenu(NavigableMenu):
    """Меню управления трейдами"""
    
    def __init__(self, cli_context):
        super().__init__(Messages.TRADES_TITLE)
        self.cli = cli_context
        self.gift_handler = GiftAcceptHandler(
            cli_context.trade_manager, 
            cli_context.formatter,
            cli_context.cookie_checker
        )
        self.confirm_handler = TradeConfirmHandler(
            cli_context.trade_manager, 
            cli_context.formatter,
            cli_context.cookie_checker
        )
        self.specific_handler = SpecificTradeHandler(
            cli_context.trade_manager, 
            cli_context.formatter,
            cli_context.active_trades_cache or [],
            cli_context.cookie_checker
        )
        self.checker = TradeCheckHandler(
            cli_context.trade_manager, 
            cli_context.formatter,
            cli_context.cookie_checker
        )
    
    def setup_menu(self):
        """Настроить элементы меню трейдов"""
        self.add_item(MenuItem(
            TradeMenuChoice.ACCEPT_GIFTS.value,
            Messages.ACCEPT_GIFTS,
            self.accept_gifts
        ))
        
        self.add_item(MenuItem(
            TradeMenuChoice.CONFIRM_ALL.value,
            "🔑 Подтвердить все через Guard (включая исходящие)",
            self.confirm_all_trades,
            enabled=True  # Проверка доступности будет в самом методе
        ))
        
        self.add_item(MenuItem(
            TradeMenuChoice.ACCEPT_SPECIFIC.value,
            Messages.ACCEPT_SPECIFIC,
            self.accept_specific_trade
        ))
        
        self.add_item(MenuItem(
            TradeMenuChoice.CONFIRM_SPECIFIC.value,
            Messages.CONFIRM_SPECIFIC,
            self.confirm_specific_trade,
            enabled=True  # Проверка доступности будет в самом методе
        ))
    
    def accept_gifts(self):
        """Принять все подарки"""
        return self.gift_handler.execute()
    
    def confirm_all_trades(self):
        """Подтвердить все трейды через Guard"""
        if self.checker.has_guard_confirmation_needed_trades():
            return self.confirm_handler.execute()
        else:
            print(Messages.NO_CONFIRMATION_TRADES)
            print(Messages.NO_CONFIRMATION_TRADES_HINT)
            return None
    
    def accept_specific_trade(self):
        """Принять конкретный трейд"""
        if not self.cli.active_trades_cache:
            print(Messages.NO_TRADES_FROM_MENU)
            return None
        
        trade_num = self.specific_handler.get_trade_number()
        if trade_num:
            return self.specific_handler.accept_specific_trade(trade_num)
        return None
    
    def confirm_specific_trade(self):
        """Подтвердить конкретный трейд через Guard"""
        if not self.checker.has_guard_confirmation_needed_trades():
            print(Messages.NO_CONFIRMATION_TRADES)
            print(Messages.NO_CONFIRMATION_TRADES_HINT)
            return None
        
        if not self.cli.active_trades_cache:
            print(Messages.NO_TRADES_FROM_MENU)
            return None
        
        trade_num = self.specific_handler.get_trade_number()
        if trade_num:
            return self.specific_handler.confirm_specific_trade(trade_num)
        return None


class SettingsMenu(NavigableMenu):
    """Меню настроек"""
    
    def __init__(self, cli_context):
        super().__init__(Messages.SETTINGS_TITLE)
        self.cli = cli_context
        self.settings_manager = SettingsManager(
            accounts_dir=getattr(cli_context, 'accounts_dir', 'accounts_info')
        )
    
    def setup_menu(self):
        """Настроить элементы меню настроек"""
        self.add_item(MenuItem(
            SettingsMenuChoice.ADD_MAFILE.value,
            Messages.ADD_MAFILE,
            self.add_mafile
        ))
        
        self.add_item(MenuItem(
            SettingsMenuChoice.GET_API_KEY.value,
            Messages.GET_API_KEY,
            self.get_api_key
        ))
    
    def add_mafile(self):
        """Добавить mafile"""
        try:
            result = self.settings_manager.add_mafile()
            if result:
                print()
                input(Messages.PRESS_ENTER)
            return result
        except Exception as e:
            print(f"❌ Ошибка при добавлении mafile: {e}")
            input(Messages.PRESS_ENTER)
            return False 

    def get_api_key(self):
        """Получить API ключ"""
        try:
            result = self.settings_manager.get_api_key(self.cli)
            return result
        except Exception as e:
            print(f"❌ Ошибка при получении API ключа: {e}")
            input(Messages.PRESS_ENTER)
            return False 


class AutoMenu(NavigableMenu):
    """Меню автоматизации"""
    
    def __init__(self, cli_context):
        super().__init__(Messages.AUTO_TITLE)
        self.cli = cli_context
        self.auto_manager = AutoManager(
            accounts_dir=getattr(cli_context, 'accounts_dir', 'accounts_info')
        )
    
    def setup_menu(self):
        """Настроить элементы меню автоматизации"""
        self.add_item(MenuItem(
            AutoMenuChoice.AUTO_SETTINGS.value,
            Messages.AUTO_SETTINGS,
            self.open_auto_settings
        ))
        
        self.add_item(MenuItem(
            AutoMenuChoice.START_AUTO.value,
            Messages.START_AUTO_ACCEPT,
            self.start_auto_accept
        ))
    
    def open_auto_settings(self):
        """Открыть настройки автоматизации"""
        try:
            result = self.auto_manager.show_settings()
            return result
        except Exception as e:
            print(f"❌ Ошибка в настройках автоматизации: {e}")
            input(Messages.PRESS_ENTER)
            return False
    
    def start_auto_accept(self):
        """Запустить автоматизацию"""
        try:
            result = self.auto_manager.start_auto_accept(self.cli)
            return result
        except Exception as e:
            print(f"❌ Ошибка запуска автоматизации: {e}")
            input(Messages.PRESS_ENTER)
            return False 