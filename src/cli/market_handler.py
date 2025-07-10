#!/usr/bin/env python3
"""
Обработчик market ордеров для CLI интерфейса
"""

import re
from typing import List, Optional

from bs4 import BeautifulSoup

from src.utils.logger_setup import logger, print_and_log
from .constants import Messages
from .display_formatter import DisplayFormatter


class MarketHandler:
    """Обработчик подтверждения market ордеров"""
    
    def __init__(self, trade_manager, formatter: DisplayFormatter, cookie_checker):
        self.trade_manager = trade_manager
        self.formatter = formatter
        self.cookie_checker = cookie_checker
    
    def confirm_all_market_orders(self) -> bool:
        """Подтвердить все market ордера через Guard"""
        try:
            logger.info("🏪 Подтверждение market ордеров")
            logger.info("ℹ️  Поиск market ордеров, требующих подтверждения через Guard")
            
            # Проверяем cookies
            if not self.cookie_checker.ensure_valid_cookies():
                logger.error("❌ Не удалось получить действительные cookies")
                return False
            
            # Получаем Steam клиента
            steam_client = self.trade_manager._get_steam_client()
            if not steam_client:
                logger.error("❌ Не удалось получить Steam клиента")
                return False
            
            # Получаем все подтверждения
            confirmations = self._get_market_confirmations(steam_client)
            
            if not confirmations:
                print_and_log(Messages.NO_MARKET_CONFIRMATIONS)
                return True
            
            logger.info(f"Найдено {len(confirmations)} market подтверждений")
            
            # Подтверждаем каждый ордер
            confirmed_count = 0
            for i, confirmation in enumerate(confirmations, 1):
                try:
                    print_and_log(f"🔄 Подтверждение ордера {i}/{len(confirmations)}...")
                    
                    if self._confirm_market_order(steam_client, confirmation):
                        confirmed_count += 1
                        print_and_log("✅ Ордер подтвержден")
                    else:
                        print_and_log("❌ Ошибка подтверждения ордера", "ERROR")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка: {e}")
                    continue
            
            if confirmed_count > 0:
                print_and_log(f"✅ Подтверждено {confirmed_count} market ордеров", "SUCCESS")
                if confirmed_count < len(confirmations):
                    failed_count = len(confirmations) - confirmed_count
                    print_and_log(f"⚠️ Не удалось подтвердить {failed_count} ордеров", "WARNING")
            else:
                print_and_log("❌ Не удалось подтвердить ни одного market ордера", "ERROR")
            
            return confirmed_count > 0
            
        except Exception as e:
            print_and_log(f"❌ Ошибка подтверждения market ордеров: {e}", "ERROR")
            return False
    
    def _get_market_confirmations(self, steam_client) -> List[dict]:
        """Получить все market подтверждения"""
        try:
            # Проверяем, есть ли метод для получения подтверждений
            if hasattr(steam_client, 'get_confirmations'):
                confirmations = steam_client.get_confirmations()
                
                # Фильтруем только market подтверждения
                market_confirmations = []
                for conf in confirmations:
                    if self._is_market_confirmation(conf):
                        market_confirmations.append(conf)
                
                return market_confirmations
            
            # Альтернативный способ через прямой доступ к Guard
            elif hasattr(steam_client, 'steam_guard'):
                return self._get_confirmations_via_guard(steam_client)
            
            else:
                logger.error("❌ Методы получения подтверждений недоступны")
                return []
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения market подтверждений: {e}")
            return []
    
    def _get_confirmations_via_guard(self, steam_client) -> List[dict]:
        """Получение подтверждений через прямое обращение к Guard"""
        try:
            from src.steampy.confirmation import ConfirmationExecutor
            
            # Создаем executor для подтверждений
            confirmation_executor = ConfirmationExecutor(
                identity_secret=steam_client.steam_guard['identity_secret'],
                my_steam_id=steam_client.steam_id,
                session=steam_client._session
            )
            
            # Получаем все подтверждения
            confirmations = confirmation_executor._get_confirmations()
            
            # Фильтруем market подтверждения
            market_confirmations = []
            for conf in confirmations:
                # Получаем детали подтверждения для определения типа
                try:
                    details_html = confirmation_executor._fetch_confirmation_details_page(conf)
                    
                    # Проверяем, является ли это market листингом
                    if self._is_market_confirmation_by_details(details_html):
                        # Извлекаем информацию о листинге
                        listing_info = self._extract_listing_info(details_html)
                        
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
                    logger.warning(f"⚠️ Ошибка получения деталей подтверждения {conf.data_confid}: {e}")
                    continue
            
            return market_confirmations
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения подтверждений через Guard: {e}")
            return []
    
    def _is_market_confirmation_by_details(self, details_html: str) -> bool:
        """Определить, является ли подтверждение market листингом по HTML деталям"""
        try:
            soup = BeautifulSoup(details_html, 'html.parser')
            
            # Ищем признаки market листинга в HTML
            # Market листинги содержат специфические элементы
            market_indicators = [
                'market_listing_price',
                'market_listing_item_name',
                'market_listing_action',
                'confiteminfo',
                'market_listing_table_header'
            ]
            
            for indicator in market_indicators:
                if indicator in details_html.lower():
                    return True
            
            # Проверяем по классам CSS
            market_classes = soup.find_all(class_=lambda x: x and 'market' in x.lower())
            if market_classes:
                return True
            
            # Проверяем по тексту
            text_content = soup.get_text().lower()
            market_keywords = ['sell on the community market', 'market listing', 'steam community market']
            
            for keyword in market_keywords:
                if keyword in text_content:
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка анализа деталей подтверждения: {e}")
            return False
    
    def _extract_listing_info(self, details_html: str) -> dict:
        """Извлечь информацию о листинге из HTML деталей"""
        try:
            soup = BeautifulSoup(details_html, 'html.parser')
            info = {}
            
            # Извлекаем название предмета - ищем в разных местах
            item_name = None
            
            # Поиск по различным селекторам
            selectors = [
                '.market_listing_item_name',
                '.market_listing_item_name_link',
                '.item_market_name',
                '.economy_item_hoverable'
            ]
            
            for selector in selectors:
                elem = soup.select_one(selector)
                if elem:
                    item_name = elem.get_text().strip()
                    break
            
            # Если не нашли по селекторам, ищем по тексту
            if not item_name:
                text = soup.get_text()
                # Ищем паттерн между определенными словами
                match = re.search(r'You want to sell.*?(\w+.*?)(?:You receive|for)', text, re.DOTALL)
                if match:
                    item_name = match.group(1).strip()
            
            if item_name:
                info['item_name'] = item_name
            
            # Извлекаем цену - ищем "You receive"
            price_match = re.search(r'You receive\s*([0-9,.\s]+[а-яё]+)', details_html, re.IGNORECASE)
            if price_match:
                info['price'] = price_match.group(1).strip()
            
            # Формируем компактное описание
            item_name = info.get('item_name', 'Неизвестный предмет')
            price = info.get('price', '')
            
            if price:
                info['description'] = f"{item_name} → {price}"
            else:
                info['description'] = f"Market Listing: {item_name}"
            
            return info
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка извлечения информации о листинге: {e}")
            return {'description': 'Market Listing', 'item_name': 'Неизвестный предмет'}
    
    def _is_market_confirmation(self, confirmation) -> bool:
        """Проверить, является ли подтверждение market ордером (упрощенная версия)"""
        # Эта функция используется как fallback, основная логика в _is_market_confirmation_by_details
        return True
    
    def _display_confirmations(self, confirmations: List[dict]):
        """Отобразить список подтверждений"""
        logger.info("📋 Найденные market ордера:")
        for i, conf in enumerate(confirmations, 1):
            conf_id = conf.get('id', 'N/A')
            description = conf.get('description', 'Market Order')
            
            # Компактный формат
            logger.info(f"  {i:2d}. {description} (ID: {conf_id})")
        logger.info("")
    
    def _confirm_market_order(self, steam_client, confirmation_data: dict) -> bool:
        """Подтвердить отдельный market ордер"""
        try:
            from src.steampy.confirmation import ConfirmationExecutor
            
            # Создаем executor для подтверждений
            confirmation_executor = ConfirmationExecutor(
                identity_secret=steam_client.steam_guard['identity_secret'],
                my_steam_id=steam_client.steam_id,
                session=steam_client._session
            )
            
            # Получаем объект подтверждения
            confirmation = confirmation_data['confirmation']
            
            # Подтверждаем через executor
            response = confirmation_executor._send_confirmation(confirmation)
            
            # Проверяем результат
            if response and response.get('success'):
                return True
            else:
                error_message = response.get('error', 'Unknown error') if response else 'No response'
                logger.error(f"❌ Ошибка подтверждения: {error_message}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Исключение при подтверждении: {e}")
            return False 