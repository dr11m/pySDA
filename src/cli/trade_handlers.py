#!/usr/bin/env python3
"""
Обработчики действий для трейдов
"""

from typing import Dict, List, Optional, Any
from .constants import Messages, Formatting
from .display_formatter import DisplayFormatter


class TradeActionHandler:
    """Базовый обработчик действий с трейдами"""
    
    def __init__(self, trade_manager, display_formatter: DisplayFormatter, cookie_checker=None):
        self.trade_manager = trade_manager
        self.formatter = display_formatter
        self.cookie_checker = cookie_checker
    
    def _print_section_header(self, title: str):
        """Вывести заголовок секции"""
        print(f"\n{title}")
        print(Formatting.SHORT_LINE)
    
    def _print_stats(self, stats: Dict[str, int], title: str = "Результат"):
        """Вывести статистику"""
        stats_display = self.formatter.format_stats(stats, title)
        print(stats_display)


class GiftAcceptHandler(TradeActionHandler):
    """Обработчик принятия подарков"""
    
    def execute(self) -> Dict[str, int]:
        """Принять все подарки"""
        try:
            self._print_section_header("🎁 Принятие подарков...")
            
            # Автоматически проверяем cookies перед действием
            if self.cookie_checker and not self.cookie_checker.ensure_valid_cookies():
                print("❌ Не удалось получить актуальные cookies")
                return {'errors': 1}
            
            stats = self.trade_manager.process_free_trades(
                auto_accept=True,
                auto_confirm=False  # Сначала только принимаем
            )
            
            self._print_stats(stats)
            return stats
            
        except Exception as e:
            print(self.formatter.format_error("Ошибка принятия подарков", e))
            return {'errors': 1}


class TradeConfirmHandler(TradeActionHandler):
    """Обработчик подтверждения трейдов через Guard"""
    
    def execute(self) -> Dict[str, int]:
        """Подтвердить все трейды через Guard"""
        try:
            self._print_section_header("🔑 Подтверждение трейдов через Guard...")
            
            # Автоматически проверяем cookies перед действием
            if self.cookie_checker and not self.cookie_checker.ensure_valid_cookies():
                print("❌ Не удалось получить актуальные cookies")
                return {'errors': 1}
            
            stats = self.trade_manager.process_confirmation_needed_trades(
                auto_confirm=True
            )
            
            self._print_stats(stats)
            return stats
            
        except Exception as e:
            print(self.formatter.format_error("Ошибка подтверждения трейдов", e))
            return {'errors': 1}


class SpecificTradeHandler(TradeActionHandler):
    """Обработчик действий с конкретными трейдами"""
    
    def __init__(self, trade_manager, display_formatter: DisplayFormatter, trades_cache: List, cookie_checker=None):
        super().__init__(trade_manager, display_formatter, cookie_checker)
        self.trades_cache = trades_cache
    
    def display_trades_list(self):
        """Отобразить список трейдов"""
        trades_display = self.formatter.format_trades_list(self.trades_cache)
        print(trades_display)
    
    def get_trade_number(self) -> Optional[int]:
        """Получить номер трейда от пользователя"""
        if not self.trades_cache:
            print("❌ Сначала получите список незавершенных трейдов")
            return None
        
        self.display_trades_list()
        
        try:
            trade_num = int(input(f"Введите номер трейда (1-{len(self.trades_cache)}): "))
            if 1 <= trade_num <= len(self.trades_cache):
                return trade_num
            else:
                print(f"❌ Неверный номер трейда. Доступно: 1-{len(self.trades_cache)}")
                return None
        except ValueError:
            print("❌ Введите корректный номер")
            return None
    
    def accept_specific_trade(self, trade_number: int) -> bool:
        """Принять конкретный трейд"""
        try:
            # Автоматически проверяем cookies перед действием
            if self.cookie_checker and not self.cookie_checker.ensure_valid_cookies():
                print("❌ Не удалось получить актуальные cookies")
                return False
            
            trade = self.trades_cache[trade_number - 1]
            trade_id = trade.tradeofferid
            
            print(f"\n✅ Принятие трейда #{trade_number} (ID: {trade_id})...")
            print(Formatting.SHORT_LINE)
            
            # Шаг 1: Принимаем трейд в веб-интерфейсе
            print("🌐 Принимаем трейд в веб-интерфейсе...")
            if self.trade_manager.accept_trade_offer(trade_id):
                print(f"✅ Трейд {trade_id} успешно принят в веб-интерфейсе")
                
                # Шаг 2: Спрашиваем о подтверждении через Guard
                from .constants import Messages
                confirm = input(f"\n{Messages.CONFIRM_GUARD}").lower().strip()
                if confirm in ['y', 'yes', 'да', 'д']:
                    print("🔑 Подтверждение через Guard...")
                    if self.trade_manager.confirm_accepted_trade_offer(trade_id):
                        print("✅ Трейд успешно подтвержден через Guard")
                    else:
                        print("❌ Не удалось подтвердить трейд через Guard")
                else:
                    print("ℹ️ Трейд принят в веб-интерфейсе, но не подтвержден через Guard")
                
                return True
            else:
                print(f"❌ Не удалось принять трейд {trade_id} в веб-интерфейсе")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка принятия трейда: {e}")
            return False
    
    def confirm_specific_trade(self, trade_number: int) -> bool:
        """Подтвердить конкретный трейд через Guard"""
        try:
            # Автоматически проверяем cookies перед действием
            if self.cookie_checker and not self.cookie_checker.ensure_valid_cookies():
                print("❌ Не удалось получить актуальные cookies")
                return False
            
            trade = self.trades_cache[trade_number - 1]
            trade_id = trade.tradeofferid
            
            print(f"\n🔑 Подтверждение трейда #{trade_number} через Guard (ID: {trade_id})...")
            print(Formatting.SHORT_LINE)
            
            if self.trade_manager.confirm_accepted_trade_offer(trade_id):
                print(f"✅ Трейд {trade_id} успешно подтвержден через Guard")
                return True
            else:
                print(f"❌ Не удалось подтвердить трейд {trade_id} через Guard")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка подтверждения трейда: {e}")
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
            print(f"❌ Ошибка проверки незавершенных трейдов: {e}")
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
            print(f"❌ Ошибка проверки трейдов для Guard: {e}")
            return False 