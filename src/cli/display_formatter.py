#!/usr/bin/env python3
"""
Форматирование вывода для CLI интерфейса
"""

from typing import List, Dict, Any
from datetime import datetime

from .constants import Formatting, Messages
from ..models import TradeOffer


class DisplayFormatter:
    """Класс для форматирования вывода"""
    
    @staticmethod
    def format_header(title: str, username: str = None) -> str:
        """Форматировать заголовок"""
        if username:
            full_title = f"{title} - {username}"
        else:
            full_title = title
        
        return f"\n{Formatting.SEPARATOR}\n{full_title}\n{Formatting.SEPARATOR}"
    
    @staticmethod
    def format_section_header(title: str) -> str:
        """Форматировать заголовок секции"""
        return f"\n{title}\n{Formatting.SHORT_LINE}"
    
    @staticmethod
    def format_trade_type(trade: TradeOffer) -> tuple[str, str]:
        """
        Определить тип и описание трейда
        
        Returns:
            tuple: (тип_эмодзи, описание)
        """
        if trade.items_to_give_count == 0 and trade.items_to_receive_count > 0:
            return Formatting.GIFT, f"ПОДАРОК (получаем {trade.items_to_receive_count} предметов)"
        elif trade.items_to_give_count > 0 and trade.items_to_receive_count == 0:
            return Formatting.GIVE_AWAY, f"ОТДАЧА (отдаем {trade.items_to_give_count} предметов)"
        else:
            return Formatting.EXCHANGE, f"ОБМЕН (отдаем {trade.items_to_give_count}, получаем {trade.items_to_receive_count})"
    
    @staticmethod
    def format_trade_direction(trade: TradeOffer, received_trades: List[TradeOffer]) -> str:
        """Определить направление трейда"""
        return Formatting.INCOMING if trade in received_trades else Formatting.OUTGOING
    
    @staticmethod
    def format_single_trade(trade: TradeOffer, index: int, received_trades: List[TradeOffer] = None) -> str:
        """
        Форматировать один трейд для отображения
        
        Args:
            trade: Трейд для форматирования
            index: Номер трейда (начиная с 1)
            received_trades: Список входящих трейдов для определения направления
        """
        # Определяем направление трейда
        if received_trades is not None:
            direction = DisplayFormatter.format_trade_direction(trade, received_trades)
            direction_text = "Входящий" if direction == Formatting.INCOMING else "Исходящий"
        else:
            direction = Formatting.EXCHANGE
            direction_text = "Обмен"
        
        # Определяем тип трейда
        type_emoji, type_description = DisplayFormatter.format_trade_type(trade)
        
        # Форматируем строку
        result = f"  {index:2d}. {direction} {direction_text} | ID: {trade.tradeofferid}\n"
        result += f"      {type_emoji} {type_description}\n"
        result += f"      Партнер: {trade.accountid_other}"
        
        # Добавляем время создания если есть
        if hasattr(trade, 'time_created') and trade.time_created:
            result += f" | Создан: {trade.time_created}"
        
        return result
    
    @staticmethod
    def format_trades_list(trades: List[TradeOffer], received_trades: List[TradeOffer] = None, 
                          title: str = "Доступные трейды для выбора") -> str:
        """
        Форматировать список трейдов
        
        Args:
            trades: Список трейдов
            received_trades: Список входящих трейдов для определения направления
            title: Заголовок списка
        """
        if not trades:
            return f"\n📋 Список активных трейдов пуст\nℹ️ Сначала получите список трейдов из главного меню (пункт 2)"
        
        result = f"\n📋 {title} ({len(trades)}):\n{Formatting.LINE}\n"
        
        for i, trade in enumerate(trades, 1):
            result += DisplayFormatter.format_single_trade(trade, i, received_trades) + "\n\n"
        
        return result.rstrip()  # Убираем лишние переносы строк в конце
    
    @staticmethod
    def format_stats(stats: Dict[str, int], title: str = "Результат") -> str:
        """Форматировать статистику"""
        result = f"📊 {title}:\n"
        
        for key, value in stats.items():
            # Переводим ключи на русский
            key_translations = {
                'found_free_trades': '🎁 Найдено подарков',
                'accepted_trades': '✅ Принято',
                'confirmed_trades': '🔑 Подтверждено', 
                'found_confirmation_needed': '🔑 Найдено требующих подтверждения',
                'errors': '❌ Ошибок'
            }
            
            translated_key = key_translations.get(key, key)
            result += f"  {translated_key}: {value}\n"
        
        return result.rstrip()
    
    @staticmethod
    def format_cookies_info(cookies: Dict[str, str]) -> str:
        """Форматировать информацию о cookies"""
        from .constants import Config
        
        result = f"{Messages.COOKIES_UPDATED.format(count=len(cookies))}\n"
        
        for cookie_name in Config.IMPORTANT_COOKIES:
            if cookie_name in cookies:
                value = cookies[cookie_name][:15] + "..." if len(cookies[cookie_name]) > 15 else cookies[cookie_name]
                result += f"   📄 {cookie_name}: {value}\n"
        
        return result.rstrip()
    
    @staticmethod
    def format_error(message: str, error: Exception = None) -> str:
        """Форматировать сообщение об ошибке"""
        result = f"{Messages.ERROR} {message}"
        if error:
            result += f": {error}"
        return result
    
    @staticmethod
    def format_success(message: str) -> str:
        """Форматировать сообщение об успехе"""
        return f"{Messages.SUCCESS} {message}"
    
    @staticmethod
    def format_info(message: str) -> str:
        """Форматировать информационное сообщение"""
        return f"{Messages.INFO} {message}"
    
    @staticmethod
    def format_warning(message: str) -> str:
        """Форматировать предупреждение"""
        return f"{Messages.WARNING} {message}" 