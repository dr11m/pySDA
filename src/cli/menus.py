#!/usr/bin/env python3
"""
Конкретные реализации меню
"""

from typing import Optional, List, Dict, Any
from .menu_base import BaseMenu, NavigableMenu, MenuItem
from .constants import MenuChoice, TradeMenuChoice, SettingsMenuChoice, AutoMenuChoice, Messages, Formatting
from .display_formatter import DisplayFormatter
from .trade_handlers import (
    GiftAcceptHandler, 
    TradeConfirmHandler, 
    SpecificTradeHandler,
    TradeCheckHandler
)
from src.models import TradeOffer
from .settings_manager import SettingsManager
from .auto_manager import AutoManager, AutoSettings
from .market_handler import MarketHandler
from src.utils.logger_setup import print_and_log
from pathlib import Path
import json


class MainMenu(BaseMenu):
    """Главное меню приложения"""
    
    def __init__(self, cli_context):
        # Название будет обновляться динамически
        super().__init__("") 
        self.cli = cli_context
    
    def _update_title(self):
        """Обновляет заголовок меню, чтобы показать выбранный аккаунт."""
        if self.cli.selected_account_name:
            self.title = f"{Messages.MAIN_TITLE} - Аккаунт: [{self.cli.selected_account_name}]"
        else:
            self.title = f"{Messages.MAIN_TITLE} - [Аккаунт не выбран]"

    def setup_menu(self):
        """Настроить элементы главного меню"""
        self.items.clear() # Очищаем старые пункты

        self.add_item(MenuItem(
            MenuChoice.SELECT_ACCOUNT.value,
            Messages.SELECT_ACCOUNT,
            self.cli.select_and_initialize_account
        ))

        self.add_item(MenuItem(
            MenuChoice.UPDATE_COOKIES.value,
            Messages.UPDATE_COOKIES,
            self.cli.update_cookies
        ))
        
        self.add_item(MenuItem(
            MenuChoice.MANAGE_TRADES.value,
            Messages.MANAGE_TRADES,
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

    def run(self):
        """Переопределенный цикл для динамического обновления меню."""
        self.running = True
        while self.running:
            self._update_title()
            self.setup_menu()
            self.display_menu()
            choice = self.get_user_choice()
            if not self.handle_choice(choice):
                break
    
    def open_trades_menu(self):
        """Открыть меню управления трейдами"""
        # Получаем все трейды один раз
        print_and_log("🔄 Подготовка к управлению трейдами...")
        all_trades = self.cli.get_all_trades()
        
        if all_trades is None:
            print_and_log("❌ Не удалось получить список трейдов", "ERROR")
            return
        
        # Фильтруем активные трейды для проверки
        active_trades = [t for t in all_trades if t.is_active]
        
        if not active_trades:
            print_and_log("ℹ️  Нет активных трейдов для управления", "INFO")
            input("Нажмите Enter для продолжения...")
            return
        
        # Если есть трейды, открываем меню управления, передавая уже полученные данные
        trades_menu = TradesMenu(self.cli, all_trades)
        trades_menu.run()
    
    def confirm_market_orders(self):
        """Подтвердить все market ордера"""
        market_handler = MarketHandler(
            self.cli.active_account_context.trade_manager,
            self.cli.formatter,
            self.cli.active_account_context.cookie_checker
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


class SettingsMenu(NavigableMenu):
    """Меню настроек"""
    
    def __init__(self, cli_context):
        super().__init__(Messages.SETTINGS_TITLE)
        self.cli = cli_context
        self.settings_manager = SettingsManager()
    
    def setup_menu(self):
        """Настроить элементы меню настроек"""
        self.items.clear()
        
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
        
        self.add_item(MenuItem(
            SettingsMenuChoice.BACK.value,
            Messages.BACK,
            self.go_back
        ))
    
    def add_mafile(self):
        """Добавить mafile"""
        return self.settings_manager.add_mafile()
    
    def get_api_key(self):
        """Получить API ключ"""
        if not self.cli.active_account_context:
            print_and_log("❌ Сначала необходимо выбрать аккаунт (пункт 1 в главном меню)", "ERROR")
            return False
        return self.settings_manager.get_api_key(self.cli.active_account_context)
    
    def exit_app(self):
        """Выйти из приложения"""
        print_and_log(Messages.GOODBYE)
        self.stop()
    
    def handle_choice(self, choice: str) -> bool:
        """
        Обработать выбор пользователя.
        Возвращает False, если нужно выйти из меню.
        """
        item = self.get_item(choice)
        if item and item.enabled:
            try:
                result = item.execute()
                return self.process_action_result(choice, result)
            except Exception as e:
                self.handle_error(e)
                return True # Продолжаем работу после ошибки
        else:
            self.handle_invalid_choice(choice)
            return True # Продолжаем работу при неверном выборе

    def process_action_result(self, choice: str, result) -> bool:
        """Обработать результат действия"""
        if choice == MenuChoice.EXIT.value:
            return False # Останавливаем цикл
            
        return True


class TradesMenu(NavigableMenu):
    """Меню управления трейдами"""
    
    def __init__(self, cli_context, all_trades=None):
        super().__init__(Messages.TRADES_TITLE)
        self.cli = cli_context
        self.all_trades = all_trades  # Предварительно загруженные трейды
        
        self.gift_handler = GiftAcceptHandler(
            cli_context.active_account_context.trade_manager, 
            cli_context.formatter,
            cli_context.active_account_context.cookie_checker
        )
        self.confirm_handler = TradeConfirmHandler(
            cli_context.active_account_context.trade_manager, 
            cli_context.formatter,
            cli_context.active_account_context.cookie_checker
        )
        # Инициализируем с пустым списком, обновим в setup_menu
        self.specific_handler = SpecificTradeHandler(
            cli_context.active_account_context.trade_manager, 
            cli_context.formatter,
            [],
            cli_context.active_account_context.cookie_checker
        )
        self.checker = TradeCheckHandler(
            cli_context.active_account_context.trade_manager, 
            cli_context.formatter,
            cli_context.active_account_context.cookie_checker
        )
    
    def setup_menu(self):
        """Настроить элементы меню трейдов"""
        # Используем предварительно загруженные трейды или загружаем новые
        if self.all_trades is None:
            self.all_trades = self.cli.get_all_trades()
        
        # Проверяем наличие разных типов трейдов
        has_gifts = False
        has_confirmation_needed = False
        has_any_trades = False
        
        if self.all_trades:
            has_any_trades = True
            
            # Показываем информацию о найденных трейдах
            active_received = [t for t in self.all_trades if not t.is_our_offer and t.is_active]
            active_sent = [t for t in self.all_trades if t.is_our_offer and t.is_active]
            confirmation_needed_received = [t for t in self.all_trades if not t.is_our_offer and t.needs_confirmation]
            confirmation_needed_sent = [t for t in self.all_trades if t.is_our_offer and t.needs_confirmation]
            
            print_and_log("📋 Найденные трейды:")
            if active_received:
                print_and_log(f"  📥 Входящие активные: {len(active_received)}")
            if active_sent:
                print_and_log(f"  📤 Исходящие активные: {len(active_sent)}")
            if confirmation_needed_received:
                print_and_log(f"  🔑 Входящие требующие подтверждения: {len(confirmation_needed_received)}")
            if confirmation_needed_sent:
                print_and_log(f"  🔑 Исходящие требующие подтверждения: {len(confirmation_needed_sent)}")
            
            # Проверяем входящие активные трейды на подарки
            for trade in active_received:
                if trade.items_to_give_count == 0 and trade.items_to_receive_count > 0:
                    has_gifts = True
                    break
        
        # Проверяем трейды требующие подтверждения на основе уже полученных данных
        if confirmation_needed_received or confirmation_needed_sent:
            has_confirmation_needed = True
        
        # Если нет активных трейдов вообще, показываем сообщение
        active_trades_count = len(active_received) + len(active_sent)
        if active_trades_count == 0:
            print_and_log("ℹ️ Нет активных трейдов для управления")
            print_and_log("💡 Это может означать:")
            print_and_log("  - Нет активных входящих трейдов")
            print_and_log("  - Нет активных исходящих трейдов") 
            print_and_log("  - Нет трейдов требующих подтверждения")
        else:
            print_and_log(f"✅ Найдено {active_trades_count} активных трейдов для управления")
            
        # Обновляем кэш трейдов в specific_handler
        self.specific_handler.trades_cache = active_received + active_sent
        
        self.add_item(MenuItem(
            TradeMenuChoice.ACCEPT_GIFTS.value,
            Messages.ACCEPT_GIFTS,
            self.accept_gifts,
            enabled=has_gifts
        ))
        
        self.add_item(MenuItem(
            TradeMenuChoice.CONFIRM_ALL.value,
            Messages.CONFIRM_ALL,
            self.confirm_all_trades,
            enabled=has_confirmation_needed
        ))
        
        self.add_item(MenuItem(
            TradeMenuChoice.ACCEPT_SPECIFIC.value,
            Messages.ACCEPT_SPECIFIC,
            self.accept_specific_trade,
            enabled=active_trades_count > 0
        ))
        
        self.add_item(MenuItem(
            TradeMenuChoice.CONFIRM_SPECIFIC.value,
            Messages.CONFIRM_SPECIFIC,
            self.confirm_specific_trade,
            enabled=has_confirmation_needed
        ))
        
        self.add_item(MenuItem(
            TradeMenuChoice.BACK.value,
            Messages.BACK,
            self.go_back
        ))
    
    def accept_gifts(self):
        """Принять все подарки"""
        return self.gift_handler.execute()
    
    def confirm_all_trades(self):
        """Подтвердить все трейды через Guard"""
        # Проверяем наличие трейдов требующих подтверждения на основе уже полученных данных
        confirmation_needed = [t for t in self.all_trades if t.needs_confirmation] if self.all_trades else []
        
        if confirmation_needed:
            return self.confirm_handler.execute()
        else:
            print_and_log(Messages.NO_CONFIRMATION_TRADES)
            print_and_log(Messages.NO_CONFIRMATION_TRADES_HINT)
            return None
    
    def accept_specific_trade(self):
        """Принять конкретный трейд"""
        # Используем уже полученные данные вместо нового запроса
        if not self.specific_handler.trades_cache:
            print_and_log(Messages.NO_TRADES_FROM_MENU, "ERROR")
            return None
        
        trade_num = self.specific_handler.get_trade_number()
        if trade_num:
            return self.specific_handler.accept_specific_trade(trade_num)
        return None
    
    def confirm_specific_trade(self):
        """Подтвердить конкретный трейд через Guard"""
        # Проверяем наличие трейдов требующих подтверждения на основе уже полученных данных
        confirmation_needed = [t for t in self.all_trades if t.needs_confirmation] if self.all_trades else []
        
        if not confirmation_needed:
            print_and_log(Messages.NO_CONFIRMATION_TRADES)
            print_and_log(Messages.NO_CONFIRMATION_TRADES_HINT)
            return None
        
        if not self.all_trades:
            print_and_log(Messages.NO_TRADES_FROM_MENU, "ERROR")
            return None
        
        # Обновляем кэш трейдов в обработчике с трейдами требующими подтверждения
        self.specific_handler.trades_cache = confirmation_needed
        
        trade_num = self.specific_handler.get_trade_number()
        if trade_num:
            return self.specific_handler.confirm_specific_trade(trade_num)
        return None


class AutoMenu(NavigableMenu):
    """Меню автоматизации"""
    
    def __init__(self, cli_context):
        super().__init__(Messages.AUTO_TITLE)
        self.cli = cli_context
        
        # AutoManager будет создан только при необходимости
        self.auto_manager = None
        self.formatter = DisplayFormatter()
    
    def _ensure_auto_manager(self) -> bool:
        """Создает AutoManager если его нет и есть выбранный аккаунт"""
        if self.auto_manager is not None:
            return True
            
        if not self.cli.selected_account_name:
            print_and_log("❌ Сначала необходимо выбрать аккаунт (пункт 1 в главном меню)", "ERROR")
            return False
        
        accounts_dir = getattr(self.cli, 'accounts_dir', 'accounts_info')
        self.auto_manager = AutoManager(
            account_name=self.cli.selected_account_name,
            accounts_dir=accounts_dir
        )
        return True
    
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
        
        self.add_item(MenuItem(
            "3",
            "⚙️  Настроить автоматизацию для другого аккаунта",
            self.configure_other_account_settings
        ))
        
        self.add_item(MenuItem(
            AutoMenuChoice.BACK.value,
            Messages.BACK,
            self.go_back
        ))

    def _get_accounts_with_automation(self) -> List[Dict[str, Any]]:
        """Получить список аккаунтов с активными настройками автоматизации"""
        # Получаем все аккаунты
        try:
            # Попробуем получить список аккаунтов через config_manager
            if hasattr(self.cli, 'config_manager') and hasattr(self.cli.config_manager, 'get_all_account_names'):
                account_names = self.cli.config_manager.get_all_account_names()
            else:
                # Fallback: поиск файлов .maFile в директории
                accounts_dir = Path(getattr(self.cli, 'accounts_dir', 'accounts_info'))
                mafiles = list(accounts_dir.glob('*.maFile'))
                account_names = [f.stem for f in mafiles]
        except Exception:
            # Еще один fallback
            accounts_dir = Path('accounts_info')
            if accounts_dir.exists():
                mafiles = list(accounts_dir.glob('*.maFile'))
                account_names = [f.stem for f in mafiles]
            else:
                account_names = []

        accounts_with_automation = []
        accounts_dir = Path(getattr(self.cli, 'accounts_dir', 'accounts_info'))
        
        for account_name in account_names:
            try:
                # Загружаем настройки для каждого аккаунта
                settings_file = accounts_dir / f"{account_name}_auto_settings.json"
                
                if settings_file.exists():
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Убираем служебные поля
                    settings_data = {k: v for k, v in data.items() if not k.startswith('_')}
                    settings = AutoSettings(**settings_data)
                    
                    # Проверяем есть ли активные настройки
                    has_active_settings = (
                        settings.auto_accept_gifts or 
                        settings.auto_confirm_trades or 
                        settings.auto_confirm_market
                    )
                    
                    if has_active_settings:
                        accounts_with_automation.append({
                            'name': account_name,
                            'settings': settings,
                            'interval': settings.check_interval
                        })
                else:
                    # Если файла настроек нет, аккаунт не участвует в автоматизации
                    continue
                    
            except Exception as e:
                print_and_log(f"⚠️ Ошибка загрузки настроек для {account_name}: {e}", "WARNING")
                continue
        
        return accounts_with_automation

    def _show_automation_preview(self, accounts: List[Dict[str, Any]]) -> bool:
        """Показать экран предпросмотра автоматизации и запросить подтверждение"""
        print_and_log(self.formatter.format_section_header("🚀 Запуск автоподтверждений"))
        print_and_log("")
        
        if not accounts:
            print_and_log("❌ Нет аккаунтов с настроенной автоматизацией!", "ERROR")
            print_and_log("")
            print_and_log("💡 Настройте автоматизацию через пункт '1. Настройки автоматизации'")
            input("Нажмите Enter для продолжения...")
            return False
        
        print_and_log(f"📋 Аккаунты, которые будут работать ({len(accounts)}):")
        print_and_log("─" * 60)
        
        for i, account in enumerate(accounts, 1):
            settings = account['settings']
            print_and_log(f"{i:2}. 🔸 {account['name']}")
            print_and_log(f"     ⏱️  Интервал проверки: {account['interval']} сек")
            
            active_features = []
            if settings.auto_accept_gifts:
                active_features.append("🎁 Принятие подарков")
            if settings.auto_confirm_trades:
                active_features.append("🔑 Подтверждение трейдов")
            if settings.auto_confirm_market:
                active_features.append("🏪 Подтверждение маркета")
            
            print_and_log(f"     🔧 Активные функции: {', '.join(active_features)}")
            print_and_log("")
        
        print_and_log("─" * 60)
        print_and_log("ℹ️  Автоматизация будет работать циклически:")
        print_and_log("   • Каждый аккаунт проверяется по своему интервалу")
        print_and_log("   • Система обрабатывает все настроенные аккаунты")
        print_and_log("   • Процесс блокирует главный поток (меню недоступно)")
        print_and_log("   • Для остановки используйте Ctrl+C")
        print_and_log("")
        
        while True:
            choice = input("🚀 Запустить автоматизацию? (y/N): ").lower().strip()
            if choice in ('y', 'yes', 'да', 'д'):
                return True
            elif choice in ('n', 'no', 'нет', 'н', ''):
                print_and_log("Отменено.")
                return False
            else:
                print_and_log("❌ Введите 'y' для запуска или 'n' для отмены", "ERROR")
    
    def open_auto_settings(self):
        """Открыть настройки автоматизации"""
        if not self._ensure_auto_manager():
            return False
            
        try:
            result = self.auto_manager.show_settings()
            return result
        except Exception as e:
            print_and_log(f"❌ Ошибка в настройках автоматизации: {e}", "ERROR")
            input(Messages.PRESS_ENTER)
            return False
    
    def start_auto_accept(self):
        """Запустить автоматизацию с предварительным показом аккаунтов"""
        try:
            # Получаем аккаунты с настройками автоматизации
            accounts_with_automation = self._get_accounts_with_automation()
            
            # Показываем экран предпросмотра и получаем подтверждение
            if not self._show_automation_preview(accounts_with_automation):
                return True  # Пользователь отменил, возвращаемся в меню
            
            print_and_log("")
            print_and_log("🔄 Запуск автоматизации...")
            print_and_log("🔴 Для остановки нажмите Ctrl+C")
            print_and_log("")
            
            # Всегда запускаем глобальную автоматизацию через MultiAccountAutoManager
            from src.cli.multi_account_auto_manager import MultiAccountAutoManager
            multi_manager = MultiAccountAutoManager(self.cli.config_manager)
            
            # Запускаем блокирующий цикл автоматизации
            multi_manager.start()

            # Этот код выполнится только после остановки цикла (через Ctrl+C)
            print_and_log("\nВозврат в меню...")
            return True
            
        except Exception as e:
            print_and_log(f"❌ Ошибка запуска автоматизации: {e}", "ERROR")
            input(Messages.PRESS_ENTER)
            return False

    def configure_other_account_settings(self):
        """Настроить автоматизацию для другого аккаунта"""
        print_and_log(self.formatter.format_section_header("⚙️ Настройка автоматизации для аккаунта"))
        
        # Получаем список всех аккаунтов
        try:
            if hasattr(self.cli, 'config_manager') and hasattr(self.cli.config_manager, 'get_all_account_names'):
                account_names = self.cli.config_manager.get_all_account_names()
            else:
                # Fallback: поиск файлов .maFile в директории
                accounts_dir = Path(getattr(self.cli, 'accounts_dir', 'accounts_info'))
                mafiles = list(accounts_dir.glob('*.maFile'))
                account_names = [f.stem for f in mafiles]
        except Exception:
            accounts_dir = Path('accounts_info')
            if accounts_dir.exists():
                mafiles = list(accounts_dir.glob('*.maFile'))
                account_names = [f.stem for f in mafiles]
            else:
                account_names = []
        
        if not account_names:
            print_and_log("❌ Не найдено ни одного аккаунта для настройки.", "ERROR")
            input("Нажмите Enter для продолжения...")
            return

        print_and_log("Выберите аккаунт для настройки:")
        for i, name in enumerate(account_names, 1):
            print_and_log(f"  {i}. {name}")
        print_and_log("  0. Назад")
        
        try:
            choice = input("\nВаш выбор: ").strip()
            if choice == "0":
                return
                
            choice_num = int(choice)
            if 1 <= choice_num <= len(account_names):
                selected_account = account_names[choice_num - 1]
                
                # Создаем временный AutoManager для выбранного аккаунта
                temp_auto_manager = AutoManager(account_name=selected_account)
                temp_auto_manager.show_settings()

            else:
                print_and_log("❌ Неверный выбор.", "ERROR")
                input("Нажмите Enter для продолжения...")
        except (ValueError, IndexError):
            print_and_log("❌ Некорректный ввод.", "ERROR")
            input("Нажмите Enter для продолжения...")


 