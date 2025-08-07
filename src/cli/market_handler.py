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
from src.trade_confirmation_manager import TradeConfirmationManager

class MarketHandler:
    """Обработчик подтверждения market ордеров"""
    
    def __init__(self, trade_manager: TradeConfirmationManager, formatter: DisplayFormatter, cookie_checker):
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
            return self._get_confirmations_via_guard(steam_client)      
        except Exception as e:
            logger.error(f"❌ Ошибка получения market подтверждений: {e}")
            return []
    
    def _get_confirmations_via_guard(self, steam_client) -> List[dict]:
        """Получение подтверждений через прямое обращение к Guard"""
        try:
            from src.steampy.confirmation import ConfirmationExecutor
            from src.utils.confirmation_utils import determine_confirmation_type_from_json, extract_confirmation_info
            
            # Создаем executor для подтверждений
            confirmation_executor = ConfirmationExecutor(
                identity_secret=steam_client.steam_guard['identity_secret'],
                my_steam_id=steam_client.steam_id,
                session=steam_client._session
            )
            
            # Получаем JSON с подтверждениями напрямую
            confirmations_page = confirmation_executor._fetch_confirmations_page()
            confirmations_json = confirmations_page.json()
            
            if not confirmations_json.get('success'):
                logger.error("❌ Не удалось получить подтверждения")
                return []
            
            all_confirmations = confirmations_json.get('conf', [])
            logger.info(f"🔍 Получено {len(all_confirmations)} подтверждений, фильтруем market...")
            
            # Фильтруем market подтверждения по JSON данным
            market_confirmations = []
            for conf_data in all_confirmations:
                try:
                    # Получаем тип подтверждения
                    confirmation_type = determine_confirmation_type_from_json(conf_data)
                    
                    # Проверяем, является ли это market подтверждением
                    if confirmation_type in ['market_listing', 'market_purchase']:
                        # Получаем описание через единую функцию
                        confirmation_info = extract_confirmation_info(conf_data, confirmation_type)
                        description = confirmation_info.get('description', f'Market {confirmation_type}')
                        
                        # Показываем описание пользователю
                        print_and_log(f"🏪 {description}")
                        
                        # Создаем объект Confirmation для совместимости
                        from src.steampy.confirmation import Confirmation
                        conf = Confirmation(
                            data_confid=conf_data['id'],
                            nonce=conf_data['nonce'],
                            creator_id=int(conf_data['creator_id'])
                        )
                        
                        market_confirmations.append({
                            'id': conf_data['id'],
                            'key': conf_data['nonce'],
                            'creator_id': int(conf_data['creator_id']),
                            'type': confirmation_type,
                            'description': description,
                            'confirmation': conf
                        })
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обработки подтверждения {conf_data.get('id', 'unknown')}: {e}")
                    continue
            
            if market_confirmations:
                print_and_log(f"✅ Найдено {len(market_confirmations)} market подтверждений для обработки")
            else:
                print_and_log("ℹ️ Нет market подтверждений")
            return market_confirmations
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения подтверждений через Guard: {e}")
            return []

    
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