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

from src.utils.logger_setup import logger
from .constants import Messages, AutoMenuChoice
from .display_formatter import DisplayFormatter

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
    # Периодичность проверки в секундах
    check_interval: int = 60
    
    # Принимать ли автоматически подарочные трейды (где нам дают что-то бесплатно)
    auto_accept_gifts: bool = False
    
    # Подтверждать ли автоматически все принятые трейды через Guard (входящие и исходящие)
    auto_confirm_trades: bool = False
    
    # Подтверждать ли автоматически market листинги (buy/sell ордера)
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
    """Менеджер автоматизации"""
    
    def __init__(self, accounts_dir: str = "accounts_info"):
        self.accounts_dir = Path(accounts_dir)
        self.formatter = DisplayFormatter()
        self.settings_file = self.accounts_dir / "auto_settings.json"
        
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
                print(f"📂 Загружаем настройки из {self.settings_file}")
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Убираем служебные поля перед созданием настроек
                settings_data = {k: v for k, v in data.items() if not k.startswith('_')}
                
                # Валидация загруженных данных
                settings = AutoSettings(**settings_data)
                print("✅ Настройки автоматизации загружены")
                return settings
            else:
                print("📝 Создаем настройки по умолчанию")
                # Создаем настройки по умолчанию
                default_settings = AutoSettings()
                if self._save_settings(default_settings):
                    print(f"✅ Настройки сохранены в {self.settings_file}")
                return default_settings
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка формата JSON в файле настроек: {e}")
            print("🔄 Создаем новые настройки по умолчанию")
            return AutoSettings()
        except Exception as e:
            print(f"⚠️ Ошибка загрузки настроек автоматизации: {e}")
            print("🔄 Используем настройки по умолчанию")
            return AutoSettings()
    
    def _save_settings(self, settings: AutoSettings) -> bool:
        """Сохранение настроек в файл"""
        try:
            # Создаем резервную копию если файл существует
            if self.settings_file.exists():
                backup_file = self.settings_file.with_suffix('.json.backup')
                shutil.copy2(self.settings_file, backup_file)
            
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
            
            print(f"💾 Настройки сохранены в {self.settings_file}")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения настроек: {e}")
            return False
    
    def show_settings(self) -> bool:
        """Показать и изменить настройки автоматизации"""
        try:
            print(self.formatter.format_section_header("⚙️ Настройки автоматизации"))
            print("ℹ️  Здесь вы можете настроить параметры автоматического принятия")
            print()
            
            while True:
                self._display_current_settings()
                print()
                print("Что хотите изменить?")
                print("1. Периодичность проверки (сек)")
                print("2. Авто принятие подарков (бесплатных трейдов)")
                print("3. Авто подтверждение всех трейдов через Guard")
                print("4. Авто подтверждение market ордеров")
                print("0. Назад")
                print("-" * 30)
                
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
                    print("❌ Неверный выбор")
                    input("Нажмите Enter для продолжения...")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка в настройках автоматизации: {e}")
            input(Messages.PRESS_ENTER)
            return False
    
    def _display_current_settings(self):
        """Отображение текущих настроек"""
        print("📋 Текущие настройки:")
        print(f"  ⏱️  Периодичность проверки: {self.settings.check_interval} сек")
        print(f"  🎁 Авто принятие подарков: {'✅' if self.settings.auto_accept_gifts else '❌'}")
        print(f"  🔑 Авто подтверждение трейдов: {'✅' if self.settings.auto_confirm_trades else '❌'}")
        print(f"  🏪 Авто подтверждение market: {'✅' if self.settings.auto_confirm_market else '❌'}")
    
    def _change_check_interval(self):
        """Изменение периодичности проверки"""
        try:
            print()
            print(f"Текущая периодичность: {self.settings.check_interval} секунд")
            print("💡 Рекомендуется: 30-300 секунд (слишком частые запросы могут привести к блокировке)")
            
            new_interval = input("Введите новую периодичность (сек): ").strip()
            
            if not new_interval.isdigit():
                print("❌ Введите число")
                return
            
            interval = int(new_interval)
            if interval < 10:
                print("❌ Минимальная периодичность: 10 секунд")
                return
            elif interval > 3600:
                print("❌ Максимальная периодичность: 3600 секунд (1 час)")
                return
            
            self.settings.check_interval = interval
            self._save_settings(self.settings)
            print(f"✅ Периодичность изменена на {interval} секунд")
            
        except Exception as e:
            print(f"❌ Ошибка изменения периодичности: {e}")
        
        input("Нажмите Enter для продолжения...")
    
    def _toggle_auto_gifts(self):
        """Переключение авто принятия подарков"""
        self.settings.auto_accept_gifts = not self.settings.auto_accept_gifts
        self._save_settings(self.settings)
        status_emoji = "✅" if self.settings.auto_accept_gifts else "❌"
        status_text = "включено" if self.settings.auto_accept_gifts else "выключено"
        print(f"{status_emoji} Авто принятие подарков {status_text}")
        print("ℹ️ Подарки = трейды где мы ничего не отдаем, но что-то получаем")
        input("Нажмите Enter для продолжения...")
    
    def _toggle_auto_confirm(self):
        """Переключение авто подтверждения трейдов"""
        self.settings.auto_confirm_trades = not self.settings.auto_confirm_trades
        self._save_settings(self.settings)
        status_emoji = "✅" if self.settings.auto_confirm_trades else "❌"
        status_text = "включено" if self.settings.auto_confirm_trades else "выключено"
        print(f"{status_emoji} Авто подтверждение трейдов {status_text}")
        print("ℹ️ Подтверждает ВСЕ принятые трейды (входящие и исходящие) через Guard")
        input("Нажмите Enter для продолжения...")
    
    def _toggle_auto_market(self):
        """Переключение авто подтверждения market ордеров"""
        self.settings.auto_confirm_market = not self.settings.auto_confirm_market
        self._save_settings(self.settings)
        status_emoji = "✅" if self.settings.auto_confirm_market else "❌"
        status_text = "включено" if self.settings.auto_confirm_market else "выключено"
        print(f"{status_emoji} Авто подтверждение market ордеров {status_text}")
        print("ℹ️ Подтверждает buy/sell ордера на торговой площадке")
        input("Нажмите Enter для продолжения...")
    
    def start_auto_accept(self, cli_context: CLIContextProtocol) -> bool:
        """Запуск автоматизации"""
        try:
            print(self.formatter.format_section_header("▶️ Запуск автоматизации"))
            print("🤖 Автоматическое принятие трейдов и подтверждений")
            print()
            
            # Показываем текущие настройки
            self._display_current_settings()
            print()
            
            # Проверяем что хотя бы одна опция включена
            if not any([self.settings.auto_accept_gifts, self.settings.auto_confirm_trades, self.settings.auto_confirm_market]):
                print("⚠️ Все опции автоматизации выключены!")
                print("💡 Включите хотя бы одну опцию в настройках автоматизации")
                input(Messages.PRESS_ENTER)
                return False
            
            # Проверяем что все необходимые компоненты доступны
            if not cli_context.trade_manager:
                print("❌ Trade Manager не инициализирован")
                input(Messages.PRESS_ENTER)
                return False
            
            if not cli_context.cookie_checker:
                print("❌ Cookie Checker не инициализирован")
                input(Messages.PRESS_ENTER)
                return False
            
            print("🔥 Действия которые будут выполняться автоматически:")
            if self.settings.auto_accept_gifts:
                print("  ✅ Принятие бесплатных трейдов (подарков)")
            if self.settings.auto_confirm_trades:
                print("  ✅ Подтверждение ВСЕХ принятых трейдов через Guard")
            if self.settings.auto_confirm_market:
                print("  ✅ Подтверждение market ордеров (buy/sell)")
            print()
            
            # Запрашиваем подтверждение
            confirm = input("🚀 Запустить автоматизацию? (y/N): ").lower().strip()
            if confirm not in ['y', 'yes', 'да', 'д']:
                print("🛑 Автоматизация отменена")
                input(Messages.PRESS_ENTER)
                return False
            
            # Запускаем автоматизацию в отдельном потоке
            print("🚀 Запуск автоматизации...")
            print("⏹️  Для остановки нажмите Ctrl+C или любую клавишу")
            print("=" * 60)
            
            self._stop_automation.clear()
            self._automation_thread = threading.Thread(
                target=self._automation_loop,
                args=(cli_context,),
                daemon=True,
                name="AutoAcceptThread"
            )
            self._automation_thread.start()
            
            # Ждем остановки
            try:
                input("\n🔴 Нажмите Enter для остановки автоматизации...")
            except KeyboardInterrupt:
                print("\n🛑 Получен сигнал остановки")
            
            # Останавливаем автоматизацию
            self._stop_automation.set()
            print("⏸️  Остановка автоматизации...")
            
            if self._automation_thread and self._automation_thread.is_alive():
                self._automation_thread.join(timeout=5)
            
            print("🛑 Автоматизация остановлена")
            input(Messages.PRESS_ENTER)
            return True
            
        except Exception as e:
            print(f"❌ Ошибка запуска автоматизации: {e}")
            logger.error(f"Ошибка автоматизации: {e}", exc_info=True)
            input(Messages.PRESS_ENTER)
            return False
    
    def _automation_loop(self, cli_context: CLIContextProtocol) -> None:
        """Основной цикл автоматизации"""
        logger.info("🤖 Запуск цикла автоматизации")
        
        cycle_count = 0
        
        while not self._stop_automation.is_set():
            try:
                cycle_count += 1
                current_time = time.strftime("%H:%M:%S")
                
                print(f"\n🔄 Цикл #{cycle_count} - {current_time}")
                print("-" * 40)
                
                # Проверяем cookies (тихо)
                if not self._check_cookies_quietly(cli_context):
                    self._wait_or_stop(10)  # Ждем 10 секунд перед повтором
                    continue
                
                # Выполняем все автоматические действия
                total_actions = self._execute_automation_tasks(cli_context)
                
                # Выводим итоги цикла
                self._print_cycle_summary(cycle_count, total_actions)
                
                # Ждем до следующего цикла
                wait_time = self.settings.check_interval
                if total_actions > 0:
                    print(f"⏰ Следующая проверка через {wait_time} секунд...")
                else:
                    print(f"⏰ Следующая проверка через {wait_time} секунд (все спокойно)")
                
                if self._wait_or_stop(wait_time):
                    break
                
            except Exception as e:
                self._handle_automation_error(e)
                if self._wait_or_stop(30):  # Ждем 30 сек при ошибке
                    break
        
        logger.info("🛑 Цикл автоматизации остановлен")
    
    def _check_cookies_quietly(self, cli_context: CLIContextProtocol) -> bool:
        """Проверка и обновление cookies (тихо, без лишних логов)"""
        try:
            # Временно отключаем логирование cookie_checker
            # Логирование уже настроено через loguru в logger_setup.py
            
            try:
                result = cli_context.cookie_checker.ensure_valid_cookies()
                if not result:
                    print("⚠️ Не удалось обновить cookies, пропускаем цикл")
                return result
            finally:
                cookie_logger.setLevel(original_level)
                
        except Exception as e:
            print(f"❌ Ошибка проверки cookies: {e}")
            return False
    
    def _execute_automation_tasks(self, cli_context: CLIContextProtocol) -> int:
        """Выполнение всех задач автоматизации"""
        total_actions = 0
        
        try:
            # Настраиваем кэширование перед выполнением задач
            self._setup_trade_caching(cli_context)
            
            # 1. Принятие бесплатных трейдов
            if self.settings.auto_accept_gifts:
                actions = self._process_free_trades(cli_context)
                total_actions += actions
            
            # 2. Подтверждение всех принятых трейдов через Guard
            if self.settings.auto_confirm_trades:
                actions = self._process_trade_confirmations(cli_context)
                total_actions += actions
            
            # 3. Подтверждение market ордеров
            if self.settings.auto_confirm_market:
                actions = self._process_market_confirmations(cli_context)
                total_actions += actions
            
        finally:
            # Всегда восстанавливаем оригинальные методы
            self._restore_trade_caching(cli_context)
        
        return total_actions
    
    def _get_cached_trades(self, cli_context: CLIContextProtocol) -> Optional[Dict[str, Any]]:
        """Получает трейды из кэша или делает новый запрос"""
        # Проверяем кэш
        cached_data = self._trade_cache.get()
        if cached_data is not None:
            logger.debug("📦 Используем кэшированные трейды")
            return cached_data
        
        # Кэш устарел, делаем новый запрос
        logger.debug("🔄 Получаем свежие трейды (кэш устарел)")
        try:
            # Используем существующий метод из trade_manager
            trade_offers = cli_context.trade_manager.get_trade_offers(active_only=False)
            if trade_offers:
                # Сохраняем в кэш
                self._trade_cache.set(trade_offers)
                return trade_offers
        except Exception as e:
            logger.error(f"Ошибка получения трейдов: {e}")
        
        return None

    def _setup_trade_caching(self, cli_context: CLIContextProtocol) -> None:
        """Настраивает кэширование трейдов для trade_manager"""
        # Сохраняем оригинальный метод
        self._original_get_trade_offers = cli_context.trade_manager.get_trade_offers
        
        # Создаем кэшированную версию
        def cached_get_trade_offers(active_only: bool = True, use_webtoken: bool = True):
            # Если кэш валиден, возвращаем из кэша
            cached_data = self._trade_cache.get()
            if cached_data is not None:
                logger.debug("📦 Используем кэшированные трейды")
                return cached_data
            
            # Кэш устарел, делаем новый запрос
            logger.debug("🔄 Получаем свежие трейды (кэш устарел)")
            result = self._original_get_trade_offers(active_only, use_webtoken)
            if result:
                # Сохраняем в кэш
                self._trade_cache.set(result)
            return result
        
        # Заменяем метод на кэшированную версию
        cli_context.trade_manager.get_trade_offers = cached_get_trade_offers

    def _restore_trade_caching(self, cli_context: CLIContextProtocol) -> None:
        """Восстанавливает оригинальный метод get_trade_offers"""
        if hasattr(self, '_original_get_trade_offers'):
            cli_context.trade_manager.get_trade_offers = self._original_get_trade_offers

    def _process_free_trades(self, cli_context: CLIContextProtocol) -> int:
        """Обработка бесплатных трейдов"""
        print("🎁 Проверка бесплатных трейдов...")
        
        try:
            # Логирование уже настроено через loguru в logger_setup.py
            # Используем оригинальный метод с кэшированием
            stats = cli_context.trade_manager.process_free_trades(
                auto_accept=True,
                auto_confirm=self.settings.auto_confirm_trades
            )
            
            if stats:
                found = stats.get('found_free_trades', 0)
                accepted = stats.get('accepted_trades', 0)
                confirmed = stats.get('confirmed_trades', 0)
                errors = stats.get('errors', 0)
                
                if found > 0:
                    print(f"  📊 Найдено: {found}, принято: {accepted}, подтверждено: {confirmed}")
                    if errors > 0:
                        print(f"  ⚠️ Ошибок: {errors}")
                    return accepted + confirmed
                else:
                    print("  ℹ️ Бесплатных трейдов не найдено")
                    return 0
            
            return 0
            
        except Exception as e:
            print(f"  ❌ Ошибка обработки бесплатных трейдов: {e}")
            logger.error(f"Ошибка обработки бесплатных трейдов: {e}", exc_info=True)
            return 0
    
    def _process_trade_confirmations(self, cli_context: CLIContextProtocol) -> int:
        """Обработка подтверждений трейдов"""
        print("🔑 Проверка трейдов, требующих подтверждения...")
        
        try:
            # Логирование уже настроено через loguru в logger_setup.py
            # Используем оригинальный метод с кэшированием
            stats = cli_context.trade_manager.process_confirmation_needed_trades(
                auto_confirm=True
            )
            
            if stats:
                found = stats.get('found_confirmation_needed', 0)
                confirmed = stats.get('confirmed_trades', 0)
                errors = stats.get('errors', 0)
                
                if found > 0:
                    print(f"  📊 Найдено требующих подтверждения: {found}, подтверждено: {confirmed}")
                    if errors > 0:
                        print(f"  ⚠️ Ошибок: {errors}")
                    return confirmed
                else:
                    print("  ℹ️ Трейдов, требующих подтверждения, не найдено")
                    return 0
            
            return 0
            
        except Exception as e:
            print(f"  ❌ Ошибка подтверждения трейдов: {e}")
            logger.error(f"Ошибка подтверждения трейдов: {e}", exc_info=True)
            return 0
    
    def _process_market_confirmations(self, cli_context: CLIContextProtocol) -> int:
        """Обработка подтверждений market ордеров"""
        print("🏪 Проверка market ордеров...")
        
        try:
            # Получаем Steam клиента
            steam_client = cli_context.trade_manager.get_steam_client()
            if not steam_client:
                print("  ❌ Не удалось получить Steam клиента")
                return 0
            
            # Получаем market подтверждения
            market_confirmations = self._get_market_confirmations(steam_client)
            
            if not market_confirmations:
                print("  ℹ️ Market подтверждений не найдено")
                return 0
            
            print(f"  📊 Найдено market подтверждений: {len(market_confirmations)}")
            
            confirmed_count = 0
            for i, conf in enumerate(market_confirmations, 1):
                description = conf.get('description', 'Market ордер')
                item_name = conf.get('item_name', 'Неизвестный предмет')
                price = conf.get('price', '')
                
                print(f"  🔄 [{i}/{len(market_confirmations)}] Подтверждаем: {description}")
                
                if self._confirm_market_order(steam_client, conf):
                    confirmed_count += 1
                    print(f"  ✅ Подтверждено: {description}")
                    
                    # Логируем детали в файл для отладки
                    logger.info(f"Market подтверждение: предмет='{item_name}', цена='{price}', описание='{description}'")
                else:
                    print(f"  ❌ Не удалось подтвердить: {description}")
                
                # Пауза между подтверждениями
                if i < len(market_confirmations):  # Не ждем после последнего
                    time.sleep(2)
            
            if confirmed_count > 0:
                print(f"  📈 Итого подтверждено market ордеров: {confirmed_count}/{len(market_confirmations)}")
            
            return confirmed_count
            
        except Exception as e:
            print(f"  ❌ Ошибка обработки market подтверждений: {e}")
            logger.error(f"Ошибка обработки market подтверждений: {e}", exc_info=True)
            return 0
    
    def _print_cycle_summary(self, cycle_count: int, total_actions: int) -> None:
        """Вывод итогов цикла"""
        if total_actions > 0:
            print(f"✅ Цикл #{cycle_count} завершен: выполнено {total_actions} действий")
        else:
            print(f"ℹ️ Цикл #{cycle_count} завершен: новых действий не требуется")
    
    def _handle_automation_error(self, error: Exception) -> None:
        """Обработка ошибок автоматизации"""
        print(f"❌ Ошибка в цикле автоматизации: {error}")
        logger.error(f"Ошибка в цикле автоматизации: {error}", exc_info=True)
    
    def _get_market_confirmations(self, steam_client: 'SteamClient') -> List[Dict[str, Any]]:
        """Получение market подтверждений (адаптировано из market_handler.py)"""
        try:
            from src.steampy.confirmation import ConfirmationExecutor
            
            # Создаем executor для подтверждений
            confirmation_executor: 'ConfirmationExecutor' = ConfirmationExecutor(
                identity_secret=steam_client.steam_guard['identity_secret'],
                my_steam_id=steam_client.steam_id,
                session=steam_client._session
            )
            
            # Получаем все подтверждения
            confirmations: List['Confirmation'] = confirmation_executor._get_confirmations()
            
            # Фильтруем market подтверждения
            market_confirmations: List[Dict[str, Any]] = []
            for conf in confirmations:
                try:
                    # Получаем детали подтверждения для определения типа
                    details_html: str = confirmation_executor._fetch_confirmation_details_page(conf)
                    
                    # Проверяем, является ли это market листингом
                    if self._is_market_confirmation_by_details(details_html):
                        # Извлекаем информацию о листинге
                        listing_info: Dict[str, str] = self._extract_listing_info(details_html)
                        
                        market_confirmations.append({
                            'id': conf.data_confid,
                            'key': conf.nonce,
                            'creator_id': conf.creator_id,
                            'description': listing_info.get('description', f'Market Listing #{conf.creator_id}'),
                            'item_name': listing_info.get('item_name', 'Unknown Item'),
                            'price': listing_info.get('price', 'Unknown Price'),
                            'confirmation': conf
                        })
                        
                except Exception as e:
                    logger.warning(f"Ошибка получения деталей подтверждения {conf.data_confid}: {e}")
                    continue
            
            return market_confirmations
            
        except Exception as e:
            logger.error(f"Ошибка получения market подтверждений: {e}")
            return []
    
    def _is_market_confirmation_by_details(self, details_html: str) -> bool:
        """Определить, является ли подтверждение market листингом по HTML деталям"""
        try:
            # Ищем признаки market листинга в HTML
            market_indicators: List[str] = [
                'market_listing_price',
                'market_listing_item_name', 
                'market_listing_action',
                'confiteminfo',
                'market_listing_table_header',
                'sell on the community market',
                'market listing',
                'steam community market'
            ]
            
            details_lower: str = details_html.lower()
            
            for indicator in market_indicators:
                if indicator in details_lower:
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Ошибка анализа деталей подтверждения: {e}")
            return False
    
    def _extract_listing_info(self, details_html: str) -> Dict[str, str]:
        """Извлечь информацию о листинге из HTML деталей"""
        try:
            info: Dict[str, str] = {}
            
            # Предварительная очистка HTML - убираем стили и комментарии (но сохраняем JSON)
            clean_html = re.sub(r'<style[^>]*>.*?</style>', '', details_html, flags=re.DOTALL | re.IGNORECASE)
            clean_html = re.sub(r'<!--.*?-->', '', clean_html, flags=re.DOTALL)
            
            # Извлечение названия предмета из JSON данных
            item_name = None
            
            # Паттерны для поиска названия предмета (начинаем с JSON данных)
            item_patterns = [
                # JSON данные из BuildHover - самые точные
                r'"market_name":\s*"([^"]+)"',
                r'"name":\s*"([^"]+)"',
                r'"market_hash_name":\s*"([^"]+)"',
                
                # HTML элементы с ID
                r'id="confiteminfo_item_name"[^>]*>([^<]+)<',
                r'class="hover_item_name"[^>]*>([^<]+)<',
                
                # Steam market специфичные паттерны
                r'market_listing_item_name[^>]*>([^<]+)</[^>]*>',
                r'item_name[^>]*>([^<]+)</[^>]*>',
                r'item[_-]?name[^>]*>([^<]+)</[^>]*>',
                
                # Поиск в div-ах с классами связанными с предметами
                r'<div[^>]*class="[^"]*(?:item|name|title)[^"]*"[^>]*>([^<]{5,100})</div>',
                r'<span[^>]*class="[^"]*(?:item|name|title)[^"]*"[^>]*>([^<]{5,100})</span>',
                
                # Ищем текст после "You want to sell"
                r'You want to sell[^>]*>([^<]{5,100})</',
                r'You want to sell[^<]*([A-Za-z][^<>{]{10,100})(?:You receive|for)',
                
                # Общие паттерны для продажи
                r'sell\s+([A-Za-z][^<>\n]{10,80}?)\s+(?:for|You receive)',
                r'selling\s+([A-Za-z][^<>\n]{10,80}?)\s+(?:for|You receive)',
                
                # Последний шанс - ищем любой осмысленный текст
                r'>([A-Za-z][A-Za-z0-9\s\-\|\(\)]{15,80})</',
            ]
            
            for pattern in item_patterns:
                matches = re.finditer(pattern, clean_html, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    candidate = match.group(1).strip()
                    
                    # Очищаем от остатков HTML и лишних символов
                    candidate = re.sub(r'<[^>]+>', '', candidate)
                    candidate = re.sub(r'&[a-zA-Z]+;', ' ', candidate)  # HTML entities
                    candidate = re.sub(r'\\u[0-9a-fA-F]{4}', lambda m: chr(int(m.group(0)[2:], 16)), candidate)  # Unicode escape
                    candidate = re.sub(r'\\/', '/', candidate)  # Escaped slashes
                    candidate = re.sub(r'\s+', ' ', candidate).strip()
                    
                    # Убираем служебные слова и символы
                    candidate = re.sub(r'^(div|span|class|id|style|script|you|want|sell|receive|for|market|listing)\s*', '', candidate, flags=re.IGNORECASE)
                    candidate = candidate.strip()
                    
                    # Проверяем что это похоже на название предмета
                    if (len(candidate) >= 5 and 
                        not candidate.isdigit() and 
                        not re.match(r'^[\d\s\.,]+$', candidate) and  # не только цифры и знаки
                        not candidate.lower() in ['you', 'want', 'sell', 'receive', 'for', 'market', 'listing', 'div', 'span', 'class'] and
                        re.search(r'[a-zA-Z]', candidate) and  # должны быть буквы
                        len(candidate.split()) <= 15):  # разумное количество слов
                        
                        item_name = candidate
                        break
                
                if item_name:
                    break
            
            if item_name:
                info['item_name'] = item_name
            
            # Извлечение цены
            price = None
            
            price_patterns = [
                # Специфичные паттерны для Steam - ищем цены с валютами
                r'You receive[^>]*>([^<]*[0-9]+[^<]*(?:руб|₽|\$|€|USD|RUB|EUR|pуб)[^<]*)</[^>]*>',
                r'You receive[^<]*([0-9]+[,.\s]*[0-9]*\s*(?:руб|₽|\$|€|USD|RUB|EUR|pуб))',
                
                # Поиск в специальных классах
                r'market_listing_price[^>]*>([^<]*[0-9]+[^<]*)</[^>]*>',
                r'price[^>]*>([^<]*[0-9]+[^<]*)</[^>]*>',
                
                # JSON паттерны
                r'"price":\s*"([^"]*[0-9]+[^"]*)"',
                r'"amount":\s*"([^"]*[0-9]+[^"]*)"',
                
                # Общие паттерны для цен
                r'([0-9]+[,.\s]*[0-9]*\s*(?:руб|₽|\$|€|USD|RUB|EUR|pуб))',
                r'([0-9]{1,6}[,.]?[0-9]{0,2}\s*(?:руб|₽|\$|€))',
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, clean_html, re.IGNORECASE)
                if match:
                    candidate = match.group(1).strip()
                    # Очищаем от HTML тегов
                    candidate = re.sub(r'<[^>]+>', '', candidate)
                    candidate = re.sub(r'&[a-zA-Z]+;', ' ', candidate)  # HTML entities
                    candidate = re.sub(r'\s+', ' ', candidate).strip()
                    
                    # Проверяем что это похоже на цену
                    if re.search(r'\d', candidate) and len(candidate) <= 50:
                        price = candidate
                        break
            
            if price:
                info['price'] = price
            
            # Формируем компактное описание
            item_name_final = info.get('item_name', 'Неизвестный предмет')
            price_final = info.get('price', '')
            
            if price_final and item_name_final != 'Неизвестный предмет':
                info['description'] = f"{item_name_final} → {price_final}"
            elif item_name_final != 'Неизвестный предмет':
                info['description'] = f"Market: {item_name_final}"
            elif price_final:
                info['description'] = f"Market ордер → {price_final}"
            else:
                info['description'] = "Market ордер"
            
            return info
            
        except Exception as e:
            logger.warning(f"Ошибка извлечения информации о листинге: {e}")
            return {'description': 'Market ордер', 'item_name': 'Неизвестный предмет'}
    
    def _confirm_market_order(self, steam_client: 'SteamClient', confirmation_data: Dict[str, Any]) -> bool:
        """Подтвердить отдельный market ордер"""
        try:
            from src.steampy.confirmation import ConfirmationExecutor
            
            # Создаем executor для подтверждений
            confirmation_executor: 'ConfirmationExecutor' = ConfirmationExecutor(
                identity_secret=steam_client.steam_guard['identity_secret'],
                my_steam_id=steam_client.steam_id,
                session=steam_client._session
            )
            
            # Получаем объект подтверждения
            confirmation: 'Confirmation' = confirmation_data['confirmation']
            
            # Подтверждаем через executor
            response: Dict[str, Any] = confirmation_executor._send_confirmation(confirmation)
            
            # Проверяем результат
            if response and response.get('success'):
                return True
            else:
                error_message: str = response.get('error', 'Unknown error') if response else 'No response'
                logger.warning(f"Ошибка подтверждения market ордера: {error_message}")
                return False
                
        except Exception as e:
            logger.error(f"Исключение при подтверждении market ордера: {e}")
            return False
    
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