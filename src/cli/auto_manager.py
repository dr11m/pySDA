#!/usr/bin/env python3
"""
Менеджер автоматизации для CLI интерфейса
"""

import json
import shutil
import os
import time
import threading
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, TYPE_CHECKING, Protocol
from dataclasses import dataclass, asdict

from src.utils.logger_setup import logger, print_and_log
from .constants import Messages, AutoMenuChoice
from .display_formatter import DisplayFormatter
from src.cli.constants import MenuChoice
from src.cli.menu_base import BaseMenu, NavigableMenu, MenuItem
from src.steampy.confirmation import Confirmation

from src.cli.account_context import AccountContext
from src.cli.display_formatter import DisplayFormatter
from src.utils.logger_setup import logger, print_and_log

# Импорты для типизации
if TYPE_CHECKING:
    from src.trade_confirmation_manager import TradeConfirmationManager
    from src.steampy.client import SteamClient
    from src.steampy.confirmation import ConfirmationExecutor, Confirmation
    from ..cli_interface import CLIInterface


class CLIContextProtocol(Protocol):
    """Протокол для типизации CLI контекста"""
    trade_manager: 'TradeConfirmationManager'
    cookie_checker: Any
    username: Optional[str]


@dataclass
class AutoSettings:
    """Настройки автоматизации"""
    check_interval: int = 60
    auto_accept_gifts: bool = False
    auto_confirm_trades: bool = False
    auto_confirm_market: bool = False


@dataclass
class TradeCache:
    """Кэш для трейдов"""
    data: Optional[Dict[str, Any]] = None
    timestamp: float = 0
    ttl: int = 15  # TTL в секундах
    
    def is_valid(self) -> bool:
        """Проверяет валидность кэша"""
        return self.data is not None and (time.time() - self.timestamp) < self.ttl
    
    def get(self) -> Optional[Dict[str, Any]]:
        """Получает данные из кэша если они валидны"""
        return self.data if self.is_valid() else None
    
    def set(self, data: Dict[str, Any]) -> None:
        """Сохраняет данные в кэш"""
        self.data = data
        self.timestamp = time.time()
    
    def clear(self) -> None:
        """Очищает кэш"""
        self.data = None
        self.timestamp = 0



class AutoManager:
    """Управляет автоматизацией и ее настройками."""
    
    def __init__(self, account_name: str, accounts_dir: str = "accounts_info"):
        self.account_name = account_name
        self.accounts_dir = Path(accounts_dir)
        self.formatter = DisplayFormatter()
        self.settings_file = self.accounts_dir / f"{account_name}_auto_settings.json"
        
        # Создаем директорию если её нет
        self.accounts_dir.mkdir(exist_ok=True)
        
        # Загружаем настройки
        self.settings = self._load_settings()
        
        # Флаг для остановки автоматизации
        self._stop_automation = threading.Event()
        self._automation_thread = None
        self._trade_cache = TradeCache()  # Кэш для трейдов
    
    def _load_settings(self) -> AutoSettings:
        """Загрузка настроек из файла"""
        try:
            if self.settings_file.exists():
                print_and_log(f"📂 Загружаем настройки из {self.settings_file}")
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Убираем служебные поля перед созданием настроек
                settings_data = {k: v for k, v in data.items() if not k.startswith('_')}
                
                # Валидация загруженных данных
                settings = AutoSettings(**settings_data)
                print_and_log("✅ Настройки автоматизации загружены")
                return settings
            else:
                print_and_log("📝 Создаем настройки по умолчанию")
                # Создаем настройки по умолчанию
                default_settings = AutoSettings()
                if self._save_settings(default_settings):
                    print_and_log(f"✅ Настройки сохранены в {self.settings_file}")
                return default_settings
        except json.JSONDecodeError as e:
            print_and_log(f"❌ Ошибка формата JSON в файле настроек: {e}")
            print_and_log("🔄 Создаем новые настройки по умолчанию")
            return AutoSettings()
        except Exception as e:
            print_and_log(f"⚠️ Ошибка загрузки настроек автоматизации: {e}")
            print_and_log("🔄 Используем настройки по умолчанию")
            return AutoSettings()
    
    def _save_settings(self, settings: AutoSettings) -> bool:
        """Сохранение настроек в файл"""
        try:
            # Сохраняем настройки с красивым форматированием
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                data = asdict(settings)
                # Добавляем комментарии в JSON (через специальные ключи)
                data['_info'] = {
                    'description': 'Настройки автоматизации Steam Bot',
                    'version': '1.0',
                    'created': str(Path(self.settings_file).stat().st_mtime if self.settings_file.exists() else 'now')
                }
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            print_and_log(f"💾 Настройки сохранены в {self.settings_file}")
            return True
        except Exception as e:
            print_and_log(f"❌ Ошибка сохранения настроек: {e}")
            return False
    
    def show_settings(self) -> bool:
        """Показать и изменить настройки автоматизации"""
        try:
            print_and_log(self.formatter.format_section_header(f"⚙️ Настройки для '{self.account_name}'"))
            print_and_log("ℹ️  Здесь вы можете настроить параметры автоматического принятия")
            print_and_log("")
            
            while True:
                self._display_current_settings()
                print_and_log("")
                print_and_log("Что хотите изменить?")
                print_and_log("1. Периодичность проверки (сек)")
                print_and_log("2. Авто принятие подарков (бесплатных трейдов)")
                print_and_log("3. Авто подтверждение всех трейдов через Guard")
                print_and_log("4. Авто подтверждение market листингов")
                print_and_log("0. Назад")
                print_and_log("-" * 30)
                
                choice = input("Выберите действие: ").strip()
                
                if choice == "0":
                    break
                elif choice == "1":
                    self._change_check_interval()
                elif choice == "2":
                    self._toggle_auto_gifts()
                elif choice == "3":
                    self._toggle_auto_confirm()
                elif choice == "4":
                    self._toggle_auto_market()
                else:
                    print_and_log("❌ Неверный выбор", "ERROR")
                    input("Нажмите Enter для продолжения...")
            
            return True
            
        except Exception as e:
            print_and_log(f"❌ Ошибка в настройках автоматизации: {e}")
            input(Messages.PRESS_ENTER)
            return False
    
    def _display_current_settings(self):
        """Отображение текущих настроек"""
        print_and_log("📋 Текущие настройки:")
        print_and_log(f"  ⏱️  Периодичность проверки: {self.settings.check_interval} сек")
        print_and_log(f"  🎁 Авто принятие подарков: {'✅' if self.settings.auto_accept_gifts else '❌'}")
        print_and_log(f"  🔑 Авто подтверждение трейдов: {'✅' if self.settings.auto_confirm_trades else '❌'}")
        print_and_log(f"  🏪 Авто подтверждение market листингов: {'✅' if self.settings.auto_confirm_market else '❌'}")
    
    def _change_check_interval(self):
        """Изменение периодичности проверки"""
        try:
            print_and_log("")
            print_and_log(f"Текущая периодичность: {self.settings.check_interval} секунд")
            print_and_log("💡 Рекомендуется: 30-300 секунд (слишком частые запросы могут привести к блокировке)")
            
            new_interval = input("Введите новую периодичность (сек): ").strip()
            
            if not new_interval.isdigit():
                print_and_log("❌ Введите число", "ERROR")
                return
            
            interval = int(new_interval)
            if interval < 10:
                print_and_log("❌ Минимальная периодичность: 10 секунд", "ERROR")
                return
            elif interval > 3600:
                print_and_log("❌ Максимальная периодичность: 3600 секунд (1 час)", "ERROR")
                return
            
            self.settings.check_interval = interval
            self._save_settings(self.settings)
            print_and_log(f"✅ Периодичность изменена на {interval} секунд")
            
        except Exception as e:
            print_and_log(f"❌ Ошибка изменения периодичности: {e}")
        
        input("Нажмите Enter для продолжения...")
    
    def _toggle_auto_gifts(self):
        """Переключение авто принятия подарков"""
        self.settings.auto_accept_gifts = not self.settings.auto_accept_gifts
        self._save_settings(self.settings)
        status_emoji = "✅" if self.settings.auto_accept_gifts else "❌"
        status_text = "включено" if self.settings.auto_accept_gifts else "выключено"
        print_and_log(f"{status_emoji} Авто принятие подарков {status_text}")
        print_and_log("ℹ️ Подарки = трейды где мы ничего не отдаем, но что-то получаем")
        input("Нажмите Enter для продолжения...")
    
    def _toggle_auto_confirm(self):
        """Переключение авто подтверждения трейдов"""
        self.settings.auto_confirm_trades = not self.settings.auto_confirm_trades
        self._save_settings(self.settings)
        status_emoji = "✅" if self.settings.auto_confirm_trades else "❌"
        status_text = "включено" if self.settings.auto_confirm_trades else "выключено"
        print_and_log(f"{status_emoji} Авто подтверждение трейдов {status_text}")
        print_and_log("ℹ️ Подтверждает ВСЕ трейды требующие подтверждения:")
        print_and_log("  📥 Входящие трейды (принятые, но не подтвержденные)")
        print_and_log("  📤 Исходящие трейды (отправленные, но не подтвержденные)")
        input("Нажмите Enter для продолжения...")
    
    def _toggle_auto_market(self):
        """Переключение авто подтверждения market листингов"""
        self.settings.auto_confirm_market = not self.settings.auto_confirm_market
        self._save_settings(self.settings)
        status_emoji = "✅" if self.settings.auto_confirm_market else "❌"
        status_text = "включено" if self.settings.auto_confirm_market else "выключено"
        print_and_log(f"{status_emoji} Авто подтверждение market листингов {status_text}")
        print_and_log("ℹ️ Подтверждает buy/sell ордера на торговой площадке")
        input("Нажмите Enter для продолжения...")
    
    def run_settings_menu(self):
        """Запускает меню настроек автоматизации."""
        # settings_menu = SettingsMenu(self.settings, self.formatter, "Настройки автоматического принятия") # This line was removed
        # settings_menu.run() # This line was removed
        # self._save_settings() # This line was removed
        print_and_log("Настройки автоматизации пока не реализованы в этом меню.")
        input(Messages.PRESS_ENTER)

    def start_auto_accept(self, context: AccountContext):
        """
        Запускает цикл автоматизации. Теперь просто выполняет задачи один раз.
        Бесконечный цикл теперь находится в MultiAccountAutoManager.
        """
        print_and_log(f"[{self.account_name}] Запуск проверки...")
        self._execute_automation_tasks(context, self.settings)
        print_and_log(f"[{self.account_name}] Проверка завершена.")

    def _execute_automation_tasks(self, context: AccountContext, settings: AutoSettings):
        """Выполняет все задачи автоматизации для указанного контекста и настроек."""
        try:
            print_and_log(f"[{context.account_name}] 🔍 Проверка cookies...")
            if not context.cookie_checker.ensure_valid_cookies(show_info=False):
                print_and_log(f"[{context.account_name}] ⚠️ Cookies невалидны. Пропуск итерации.")
                return

            print_and_log(f"[{context.account_name}] ✅ Cookies валидны, выполняем задачи...")

            # Получаем все трейды один раз для всех операций
            print_and_log(f"[{context.account_name}] 🔍 Получение трейдов...")
            trade_offers = context.trade_manager.get_trade_offers(active_only=False)
            if not trade_offers:
                print_and_log(f"[{context.account_name}] ℹ️ Нет трейдов для обработки")
                return

            # Кэшируем трейды для использования в методах
            self._trade_cache.set(trade_offers.__dict__)
            
            if settings.auto_accept_gifts:
                print_and_log(f"[{context.account_name}] 🎁 Проверка подарков...")
                self._process_free_trades_from_cache(context, trade_offers)

            if settings.auto_confirm_trades:
                print_and_log(f"[{context.account_name}] 🔑 Проверка трейдов...")
                print_and_log(f"[{context.account_name}] ℹ️ Обрабатываются только trade подтверждения")
                self._process_trade_confirmations_from_cache(context, trade_offers)

            if settings.auto_confirm_market:
                print_and_log(f"[{context.account_name}] 🏪 Проверка маркета...")
                print_and_log(f"[{context.account_name}] ℹ️ Обрабатываются только market подтверждения")
                self._process_market_confirmations(context)
        
        except Exception as e:
            print_and_log(f"[{context.account_name}] ❌ Ошибка во время выполнения задач автоматизации: {e}")
        finally:
            # Очищаем кэш после завершения
            self._trade_cache.clear()

    def _process_free_trades_from_cache(self, context: AccountContext, trade_offers):
        """Обработка бесплатных трейдов (подарков) из кэшированных данных"""
        try:
            active_received = trade_offers.active_received
            if not active_received:
                print_and_log(f"[{context.account_name}] ℹ️ Нет входящих активных 🎁 подарков")
                return

            print_and_log(f"[{context.account_name}] 🎁 Найдено {len(active_received)} входящих трейдов")
            
            for trade in active_received:
                # Проверяем, является ли трейд подарком (мы ничего не отдаем, но что-то получаем)
                if trade.items_to_give_count == 0 and trade.items_to_receive_count > 0:
                    print_and_log(f"[{context.account_name}] 🎁 Принимаем подарок (ID: {trade.tradeofferid})")
                    
                    # Принимаем трейд в веб-интерфейсе (оптимизированно)
                    partner_account_id = str(trade.accountid_other)
                    if context.trade_manager.accept_trade_offer(trade.tradeofferid, partner_account_id):
                        print_and_log(f"[{context.account_name}] ✅ Подарок принят в веб-интерфейсе")
                        # Для подарков НЕ требуется подтверждение через Guard
                        print_and_log(f"[{context.account_name}] ℹ️ Подтверждение через Guard не требуется для подарков")
                    else:
                        print_and_log(f"[{context.account_name}] ❌ Ошибка принятия подарка")
                else:
                    print_and_log(f"[{context.account_name}] ℹ️ Трейд {trade.tradeofferid} не является подарком (отдаем: {trade.items_to_give_count}, получаем: {trade.items_to_receive_count})")

        except Exception as e:
            print_and_log(f"[{context.account_name}] ❌ Ошибка обработки подарков: {e}")

    def _process_trade_confirmations_from_cache(self, context: AccountContext, trade_offers):
        """Обработка подтверждений трейдов из кэшированных данных"""
        try:
            print_and_log(f"[{context.account_name}] 🔑 Проверка трейдов требующих подтверждения...")
            
            # Получаем трейды требующие подтверждения из кэшированных данных
            confirmation_needed_received = trade_offers.confirmation_needed_received or []
            confirmation_needed_sent = trade_offers.confirmation_needed_sent or []
            
            total_confirmations = len(confirmation_needed_received) + len(confirmation_needed_sent)
            
            if total_confirmations == 0:
                print_and_log(f"[{context.account_name}] ℹ️ Нет трейдов требующих подтверждения")
                return
            
            print_and_log(f"[{context.account_name}] 🔑 Найдено {total_confirmations} трейдов требующих подтверждения")
            print_and_log(f"[{context.account_name}]   📥 Входящие: {len(confirmation_needed_received)}")
            print_and_log(f"[{context.account_name}]   📤 Исходящие: {len(confirmation_needed_sent)}")
            
            confirmed_count = 0
            error_count = 0
            
            # Обрабатываем все трейды требующие подтверждения
            all_trades_to_confirm = confirmation_needed_received + confirmation_needed_sent
            
            for trade in all_trades_to_confirm:
                try:
                    trade_type = "входящий" if trade in confirmation_needed_received else "исходящий"
                    
                    # Дополнительная проверка состояния трейда
                    print_and_log(f"[{context.account_name}] 🔑 Подтверждаем {trade_type} трейд {trade.tradeofferid}")
                    print_and_log(f"[{context.account_name}]    Состояние: {trade.state_name}, Confirmation method: {trade.confirmation_method}, Trade ID: {trade.tradeid}")
                    
                    if context.trade_manager.confirm_accepted_trade_offer(trade.tradeofferid):
                        print_and_log(f"[{context.account_name}] ✅ Трейд {trade.tradeofferid} подтвержден")
                        confirmed_count += 1
                    else:
                        print_and_log(f"[{context.account_name}] ❌ Не удалось подтвердить трейд {trade.tradeofferid}")
                        error_count += 1
                        
                except Exception as e:
                    error_msg = str(e)
                    if "ConfirmationExpected" in error_msg:
                        print_and_log(f"[{context.account_name}] ⚠️ Трейд {trade.tradeofferid} уже не требует подтверждения (возможно, уже завершен)")
                    else:
                        print_and_log(f"[{context.account_name}] ❌ Ошибка подтверждения трейда {trade.tradeofferid}: {e}")
                    error_count += 1
            
            # Итоговая статистика
            print_and_log(f"[{context.account_name}] 📊 Итого: подтверждено {confirmed_count}, ошибок {error_count}")

        except Exception as e:
            print_and_log(f"[{context.account_name}] ❌ Ошибка обработки подтверждений трейдов: {e}")

    def _process_free_trades(self, context: AccountContext):
        """Обработка бесплатных трейдов (подарков) - DEPRECATED, используйте _process_free_trades_from_cache"""
        try:
            trade_offers = context.trade_manager.get_trade_offers(active_only=True)
            if not trade_offers:
                print_and_log(f"[{context.account_name}] ℹ️ Нет активных трейдов для проверки")
                return

            active_received = trade_offers.active_received
            if not active_received:
                print_and_log(f"[{context.account_name}] ℹ️ Нет входящих активных трейдов")
                return

            print_and_log(f"[{context.account_name}] 🎁 Найдено {len(active_received)} входящих трейдов")
            
            for trade in active_received:
                # Проверяем, является ли трейд подарком (мы ничего не отдаем, но что-то получаем)
                if trade.items_to_give_count == 0 and trade.items_to_receive_count > 0:
                    print_and_log(f"[{context.account_name}] 🎁 Принимаем подарок (ID: {trade.tradeofferid})")
                    
                    # Принимаем трейд в веб-интерфейсе
                    if context.trade_manager.accept_trade_offer(trade.tradeofferid):
                        print_and_log(f"[{context.account_name}] ✅ Подарок принят в веб-интерфейсе")
                        
                        # Если включено авто-подтверждение, сразу подтверждаем через Guard
                        if self.settings.auto_confirm_trades:
                            print_and_log(f"[{context.account_name}] 🔑 Подтверждаем через Guard...")
                            if context.trade_manager.confirm_accepted_trade_offer(trade.tradeofferid):
                                print_and_log(f"[{context.account_name}] ✅ Подарок подтвержден через Guard")
                            else:
                                print_and_log(f"[{context.account_name}] ⚠️ Не удалось подтвердить через Guard")
                    else:
                        print_and_log(f"[{context.account_name}] ❌ Ошибка принятия подарка")
                else:
                    print_and_log(f"[{context.account_name}] ℹ️ Трейд {trade.tradeofferid} не является подарком (отдаем: {trade.items_to_give_count}, получаем: {trade.items_to_receive_count})")

        except Exception as e:
            print_and_log(f"[{context.account_name}] ❌ Ошибка обработки подарков: {e}")

    def _process_trade_confirmations(self, context: AccountContext):
        """Обработка подтверждений трейдов (входящие и исходящие) - DEPRECATED, используйте _process_trade_confirmations_from_cache"""
        try:
            print_and_log(f"[{context.account_name}] 🔑 Проверка трейдов требующих подтверждения...")
            
            # Используем новый метод который обрабатывает и входящие и исходящие трейды
            stats = context.trade_manager.process_confirmation_needed_trades(auto_confirm=True)
            
            if stats['found_confirmation_needed'] > 0:
                print_and_log(f"[{context.account_name}] ✅ Обработано {stats['confirmed_trades']} трейдов из {stats['found_confirmation_needed']}")
                if stats['errors'] > 0:
                    print_and_log(f"[{context.account_name}] ⚠️ Ошибок: {stats['errors']}")
            else:
                print_and_log(f"[{context.account_name}] ℹ️ Нет трейдов требующих подтверждения")

        except Exception as e:
            print_and_log(f"[{context.account_name}] ❌ Ошибка обработки подтверждений трейдов: {e}")

    def _process_market_confirmations(self, context: AccountContext):
        """Обработка подтверждений маркета"""
        try:
            from src.cli.market_handler import MarketHandler
            
            market_handler = MarketHandler(
                context.trade_manager,
                self.formatter,
                context.cookie_checker
            )
            
            print_and_log(f"[{context.account_name}] 🏪 Проверка подтверждений маркета...")
            print_and_log(f"[{context.account_name}] ℹ️ Фильтруются только market подтверждения (листинги и покупки)")
            result = market_handler.confirm_all_market_orders()
            
            if result:
                print_and_log(f"[{context.account_name}] ✅ Подтверждения маркета обработаны")
            else:
                print_and_log(f"[{context.account_name}] ℹ️ Нет подтверждений маркета или ошибка обработки")

        except Exception as e:
            print_and_log(f"[{context.account_name}] ❌ Ошибка обработки подтверждений маркета: {e}")
    
    def _wait_or_stop(self, seconds: int) -> bool:
        """
        Ждет указанное количество секунд или до получения сигнала остановки
        
        Returns:
            True если получен сигнал остановки, False если время истекло
        """
        return self._stop_automation.wait(seconds)
    
    def get_settings(self) -> AutoSettings:
        """Получение текущих настроек"""
        return self.settings