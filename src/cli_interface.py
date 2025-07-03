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
from typing import List, Optional
from pathlib import Path

# Добавляем корневую папку в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger_setup import logger
from src.cookie_manager import initialize_cookie_manager, get_cookie_manager
from src.trade_confirmation_manager import TradeConfirmationManager
from src.interfaces.storage_interface import FileCookieStorage
from src.proxy_manager import ProxyManager
from src.models import TradeOffer
from src.cli import (
    Messages, DisplayFormatter, ConfigManager,
    MainMenu, TradesMenu, AutoMenu
)
from src.cli.cookie_checker import CookieChecker


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
        self.cookie_manager = None
        self.trade_manager = None
        self.proxy_manager = None
        self.username = None
        self.active_trades_cache = None
        
        # UI компоненты
        self.formatter = DisplayFormatter()
        self.cookie_checker = None  # Будет создан после инициализации
        
        print("🤖 Steam Bot CLI v2.0 (Refactored)")
        print("=" * 50)
    
    def initialize_from_config(self, config_path: str = None) -> bool:
        """Инициализация из конфигурационного файла"""
        try:
            # Используем ConfigManager для загрузки конфигурации
            config_manager = ConfigManager(config_path)
            
            if not config_manager.load_config():
                return False
            
            if not config_manager.validate_config():
                return False
            
            # Получаем данные из конфигурации
            self.username = config_manager.get_username()
            password = config_manager.get_password()
            mafile_path = config_manager.get_mafile_path()
            steam_id = config_manager.get_steam_id()
            
            # Инициализация менеджера прокси
            proxy_list = config_manager.get_proxy_list()
            if proxy_list:
                self.proxy_manager = ProxyManager(proxy_list)
            
            # Папка для данных
            accounts_dir = config_manager.get_accounts_dir()
            self.accounts_dir = accounts_dir  # Сохраняем для использования в настройках
            
            # Инициализация Cookie Manager
            self.cookie_manager = initialize_cookie_manager(
                username=self.username,
                password=password,
                mafile_path=mafile_path,
                steam_id=steam_id,
                storage=FileCookieStorage(accounts_dir),
                accounts_dir=accounts_dir,
                proxy_manager=self.proxy_manager
            )
            
            # Инициализация Trade Manager с cookie_manager для исправления steam_id
            self.trade_manager = TradeConfirmationManager(
                username=self.username,
                mafile_path=mafile_path,
                cookie_manager=self.cookie_manager  # Передаем cookie_manager
            )
            
            # Инициализация Cookie Checker
            self.cookie_checker = CookieChecker(self.cookie_manager, self.formatter)
            
            print(self.formatter.format_success(f"{Messages.INIT_SUCCESS}: {self.username}"))
            return True
            
        except Exception as e:
            print(self.formatter.format_error(Messages.INIT_ERROR, e))
            return False
    
    def update_cookies(self) -> bool:
        """Принудительное обновление cookies"""
        try:
            print(self.formatter.format_section_header("🍪 Принудительное обновление cookies..."))
            print("ℹ️  Обычно cookies обновляются автоматически при необходимости.")
            print("ℹ️  Принудительное обновление полезно при проблемах с доступом.")
            print()
            
            cookies = self.cookie_manager.update_cookies(force=True)
            
            if cookies:
                print(self.formatter.format_cookies_info(cookies))
                return True
            else:
                print(self.formatter.format_error("Не удалось обновить cookies"))
                return False
                
        except Exception as e:
            print(self.formatter.format_error("Ошибка обновления cookies", e))
            return False
    
    def get_guard_code(self) -> bool:
        """Получение Guard кода"""
        try:
            print(self.formatter.format_section_header("🔑 Генерация Guard кода..."))
            print("ℹ️  Код действителен в течение 30 секунд.")
            print("ℹ️  Используйте его для ручного подтверждения трейдов в Steam.")
            print()
            
            # Генерируем Guard код через trade_manager
            guard_code = self.trade_manager.generate_guard_code()
            
            if guard_code:
                print(self.formatter.format_success(Messages.GUARD_CODE_GENERATED.format(code=guard_code)))
                print()
                print("💡 Скопируйте код и вставьте в Steam Mobile Authenticator")
                print("⏰ Код действителен 30 секунд с момента генерации")
                return True
            else:
                print(self.formatter.format_error("Не удалось сгенерировать Guard код"))
                return False
                
        except Exception as e:
            print(self.formatter.format_error("Ошибка генерации Guard кода", e))
            return False
    
    def get_active_trades(self) -> Optional[List[TradeOffer]]:
        """Получение всех незавершенных трейдов (активных + требующих подтверждения)"""
        try:
            print("\n📋 Получение незавершенных трейдов...")
            print("-" * 30)
            
            # Автоматически проверяем и обновляем cookies при необходимости
            if not self.cookie_checker.ensure_valid_cookies():
                return None
            
            trade_offers = self.trade_manager.get_trade_offers(active_only=True)
            
            if not trade_offers:
                print("❌ Не удалось получить трейд офферы")
                return None
            
            # Объединяем все незавершенные трейды (активные + требующие подтверждения)
            all_unfinished_trades = []
            all_unfinished_trades.extend(trade_offers.active_received)
            all_unfinished_trades.extend(trade_offers.active_sent)
            all_unfinished_trades.extend(trade_offers.confirmation_needed_received)
            all_unfinished_trades.extend(trade_offers.confirmation_needed_sent)
            
            if not all_unfinished_trades:
                print("ℹ️ Незавершенных трейдов не найдено")
                print("💡 Все ваши трейды завершены или не требуют дополнительных действий")
                return []
            
            print(f"📊 Найдено {len(all_unfinished_trades)} незавершенных трейдов:")
            print()
            
            # Выводим список трейдов с нумерацией
            for i, trade in enumerate(all_unfinished_trades, 1):
                # Определяем тип и статус трейда
                if trade in trade_offers.active_received:
                    trade_type = "📥 Входящий активный"
                elif trade in trade_offers.active_sent:
                    trade_type = "📤 Исходящий активный"
                elif trade in trade_offers.confirmation_needed_received:
                    trade_type = "📥 Входящий (нужен Guard)"
                elif trade in trade_offers.confirmation_needed_sent:
                    trade_type = "📤 Исходящий (нужен Guard)"
                else:
                    trade_type = "❓ Неизвестный статус"
                
                # Определяем тип трейда
                if trade.items_to_give_count == 0 and trade.items_to_receive_count > 0:
                    trade_info = f"🎁 ПОДАРОК (получаем {trade.items_to_receive_count} предметов)"
                elif trade.items_to_give_count > 0 and trade.items_to_receive_count == 0:
                    trade_info = f"💸 ОТДАЧА (отдаем {trade.items_to_give_count} предметов)"
                else:
                    trade_info = f"🔄 ОБМЕН (отдаем {trade.items_to_give_count}, получаем {trade.items_to_receive_count})"
                
                print(f"  {i:2d}. {trade_type} | ID: {trade.tradeofferid}")
                print(f"      {trade_info}")
                print(f"      Партнер: {trade.accountid_other} | Создан: {trade.time_created}")
                print()
            
            # Кэшируем результат для дальнейшего использования
            self.active_trades_cache = all_unfinished_trades
            
            return all_unfinished_trades
            
        except Exception as e:
            print(f"❌ Ошибка получения незавершенных трейдов: {e}")
            return None
    
    def run(self):
        """Запуск CLI интерфейса"""
        # Инициализация
        if not self.initialize_from_config():
            print("❌ Не удалось инициализировать бота")
            return
        
        # Основной цикл с использованием нового меню
        try:
            main_menu = MainMenu(self)
            main_menu.run()
        except KeyboardInterrupt:
            print(f"\n{Messages.INTERRUPTED}")
        except Exception as e:
            print(f"\n{Messages.CRITICAL_ERROR.format(error=e)}")


def main():
    """Точка входа для рефакторенного CLI"""
    cli = SteamBotCLI()
    cli.run()


if __name__ == "__main__":
    main() 