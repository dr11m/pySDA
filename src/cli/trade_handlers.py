#!/usr/bin/env python3
"""
Обработчики действий для трейдов
"""

from typing import Dict, List, Optional, Any
from .constants import Messages, Formatting
from .display_formatter import DisplayFormatter
from src.utils.logger_setup import print_and_log


class TradeActionHandler:
    """Базовый обработчик действий с трейдами"""
    
    def __init__(self, trade_manager, display_formatter: DisplayFormatter, cookie_checker=None):
        self.trade_manager = trade_manager
        self.formatter = display_formatter
        self.cookie_checker = cookie_checker
    
    def _print_section_header(self, title: str):
        """Вывести заголовок секции"""
        print_and_log(f"\n{title}")
        print_and_log(Formatting.SHORT_LINE)
    
    def _print_stats(self, stats: Dict[str, int], title: str = "Результат"):
        """Вывести статистику"""
        stats_display = self.formatter.format_stats(stats, title)
        print_and_log(stats_display)


class GiftAcceptHandler(TradeActionHandler):
    """Обработчик принятия подарков"""
    
    def execute(self) -> Dict[str, int]:
        """Принять все подарки"""
        try:
            self._print_section_header("🎁 Принятие подарков...")
            
            # Автоматически проверяем cookies перед действием
            if self.cookie_checker and not self.cookie_checker.ensure_valid_cookies():
                print_and_log("❌ Не удалось получить актуальные cookies", "ERROR")
                return {'errors': 1}
            
            stats = self.trade_manager.process_free_trades(
                auto_accept=True,
                auto_confirm=False  # Сначала только принимаем
            )
            
            self._print_stats(stats)
            return stats
            
        except Exception as e:
            print_and_log(self.formatter.format_error("Ошибка принятия подарков", e), "ERROR")
            return {'errors': 1}


class TradeConfirmHandler(TradeActionHandler):
    """Обработчик подтверждения трейдов через Guard"""
    
    def execute(self) -> Dict[str, int]:
        """Подтвердить все трейды через Guard"""
        try:
            self._print_section_header("🔑 Подтверждение трейдов через Guard...")
            
            # Автоматически проверяем cookies перед действием
            if self.cookie_checker and not self.cookie_checker.ensure_valid_cookies():
                print_and_log("❌ Не удалось получить актуальные cookies", "ERROR")
                return {'errors': 1}
            
            stats = self.trade_manager.process_confirmation_needed_trades(
                auto_confirm=True
            )
            
            self._print_stats(stats)
            return stats
            
        except Exception as e:
            print_and_log(self.formatter.format_error("Ошибка подтверждения трейдов", e), "ERROR")
            return {'errors': 1}


class SpecificTradeHandler(TradeActionHandler):
    """Обработчик действий с конкретными трейдами"""
    
    def __init__(self, trade_manager, display_formatter: DisplayFormatter, trades_cache: List, cookie_checker=None):
        super().__init__(trade_manager, display_formatter, cookie_checker)
        self.trades_cache = trades_cache
    
    def display_trades_list(self):
        """Отобразить список трейдов"""
        trades_display = self.formatter.format_trades_list(self.trades_cache)
        print_and_log(trades_display)
    
    def get_trade_number(self) -> Optional[int]:
        """Получить номер трейда от пользователя"""
        if not self.trades_cache:
            print_and_log("❌ Сначала получите список незавершенных трейдов", "ERROR")
            return None
        
        self.display_trades_list()
        
        try:
            trade_num = int(input(f"Введите номер трейда (1-{len(self.trades_cache)}): "))
            if 1 <= trade_num <= len(self.trades_cache):
                return trade_num
            else:
                print_and_log(f"❌ Неверный номер трейда. Доступно: 1-{len(self.trades_cache)}", "ERROR")
                return None
        except ValueError:
            print_and_log("❌ Введите корректный номер", "ERROR")
            return None
    
    def accept_specific_trade(self, trade_number: int) -> bool:
        """Принять конкретный трейд"""
        try:
            # Автоматически проверяем cookies перед действием
            if self.cookie_checker and not self.cookie_checker.ensure_valid_cookies():
                print_and_log("❌ Не удалось получить актуальные cookies", "ERROR")
                return False
            
            trade = self.trades_cache[trade_number - 1]
            trade_id = trade.tradeofferid
            
            print_and_log(f"\n✅ Принятие трейда #{trade_number} (ID: {trade_id})...")
            print_and_log(Formatting.SHORT_LINE)
            
            # Шаг 1: Принимаем трейд в веб-интерфейсе
            print_and_log("🌐 Принимаем трейд в веб-интерфейсе...")
            if self.trade_manager.accept_trade_offer(trade_id):
                print_and_log(f"✅ Трейд {trade_id} успешно принят в веб-интерфейсе")
                
                # Шаг 2: Спрашиваем о подтверждении через Guard
                from .constants import Messages
                confirm = input(f"\n{Messages.CONFIRM_GUARD}").lower().strip()
                if confirm in ['y', 'yes', 'да', 'д']:
                    print_and_log("🔑 Подтверждение через Guard...")
                    if self.trade_manager.confirm_accepted_trade_offer(trade_id):
                        print_and_log("✅ Трейд успешно подтвержден через Guard")
                    else:
                        print_and_log("❌ Не удалось подтвердить трейд через Guard", "ERROR")
                else:
                    print_and_log("ℹ️ Трейд принят в веб-интерфейсе, но не подтвержден через Guard")
                
                return True
            else:
                print_and_log(f"❌ Не удалось принять трейд {trade_id} в веб-интерфейсе", "ERROR")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка принятия трейда: {e}", "ERROR")
            return False
    
    def decline_specific_trade(self, trade_number: int) -> bool:
        """Отклонить конкретный трейд"""
        try:
            # Автоматически проверяем cookies перед действием
            if self.cookie_checker and not self.cookie_checker.ensure_valid_cookies():
                print_and_log("❌ Не удалось получить актуальные cookies", "ERROR")
                return False
            
            trade = self.trades_cache[trade_number - 1]
            trade_id = trade.tradeofferid
            
            print_and_log(f"\n❌ Отклонение трейда #{trade_number} (ID: {trade_id})...")
            
            if self.trade_manager.decline_trade_offer(trade_id):
                print_and_log(f"✅ Трейд {trade_id} успешно отклонен.")
                return True
            else:
                print_and_log(f"❌ Не удалось отклонить трейд {trade_id}.", "ERROR")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка отклонения трейда: {e}", "ERROR")
            return False
    
    def confirm_specific_trade(self, trade_number: int) -> bool:
        """Подтвердить конкретный трейд через Guard"""
        try:
            # Автоматически проверяем cookies перед действием
            if self.cookie_checker and not self.cookie_checker.ensure_valid_cookies():
                print_and_log("❌ Не удалось получить актуальные cookies", "ERROR")
                return False
            
            trade = self.trades_cache[trade_number - 1]
            trade_id = trade.tradeofferid
            
            print_and_log(f"\n🔑 Подтверждение трейда #{trade_number} через Guard (ID: {trade_id})...")
            print_and_log(Formatting.SHORT_LINE)
            
            if self.trade_manager.confirm_accepted_trade_offer(trade_id):
                print_and_log(f"✅ Трейд {trade_id} успешно подтвержден через Guard")
                return True
            else:
                print_and_log(f"❌ Не удалось подтвердить трейд {trade_id} через Guard", "ERROR")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка подтверждения трейда: {e}", "ERROR")
            return False


class TradeCheckHandler(TradeActionHandler):
    """Обработчик проверки трейдов"""
    
    def has_any_unfinished_trades(self) -> bool:
        """Проверка наличия любых незавершенных трейдов"""
        try:
            trade_offers = self.trade_manager.get_trade_offers(active_only=False)
            if not trade_offers:
                return False
            
            # Проверяем все типы незавершенных трейдов
            unfinished_trades = []
            unfinished_trades.extend(trade_offers.active_received)
            unfinished_trades.extend(trade_offers.active_sent)
            unfinished_trades.extend(trade_offers.confirmation_needed_received)
            unfinished_trades.extend(trade_offers.confirmation_needed_sent)
            
            return len(unfinished_trades) > 0
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки незавершенных трейдов: {e}", "ERROR")
            return False
    
    def has_guard_confirmation_needed_trades(self) -> bool:
        """Проверка наличия трейдов, требующих Guard подтверждения"""
        try:
            trade_offers = self.trade_manager.get_trade_offers(active_only=False)
            if not trade_offers:
                return False
            
            # Проверяем трейды, требующие Guard подтверждения
            guard_needed_trades = []
            guard_needed_trades.extend(trade_offers.confirmation_needed_received)
            guard_needed_trades.extend(trade_offers.confirmation_needed_sent)
            
            return len(guard_needed_trades) > 0
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки трейдов для Guard: {e}", "ERROR")
            return False


class MarketListHandler(SpecificTradeHandler):
    """Обработчик выставления предметов из трейда на торговую площадку"""

    def run(self, trades: List) -> bool:
        self.trades_cache = trades
        trade_num = self.get_trade_number()
        if not trade_num:
            return False

        trade = self.trades_cache[trade_num - 1]
        items_to_receive = trade.items_to_receive

        if not items_to_receive:
            print_and_log(self.formatter.format_error("В этом трейде вы ничего не получаете."), "ERROR")
            return False

        print_and_log("\n📦 Предметы, которые вы получите в этом трейде:")
        for i, item in enumerate(items_to_receive, 1):
            print_and_log(f"  {i}. {item.get('market_hash_name', 'Неизвестный предмет')}")

        try:
            item_num = int(input(f"\nВведите номер предмета для выставления на ТП (1-{len(items_to_receive)}): "))
            if not (1 <= item_num <= len(items_to_receive)):
                print_and_log(self.formatter.format_error("Неверный номер предмета."), "ERROR")
                return False

            selected_item = items_to_receive[item_num - 1]
            price_str = input(f"Введите цену для '{selected_item['market_hash_name']}' (например, 150.50): ")
            price = int(float(price_str) * 100) # В копейках/центах

            # Здесь должен быть вызов метода trade_manager для выставления на ТП
            # self.trade_manager.list_item_on_market(item_id, price)
            print_and_log(f"\n[ЗАГЛУШКА] Предмет '{selected_item['market_hash_name']}' выставлен на ТП по цене {price / 100:.2f}")
            print_and_log("Вам потребуется подтвердить выставление в мобильном приложении.")
            return True

        except ValueError:
            print_and_log(self.formatter.format_error("Некорректный ввод."), "ERROR")
            return False
        except Exception as e:
            print_and_log(self.formatter.format_error("Ошибка при выставлении на ТП:", e), "ERROR")
            return False 