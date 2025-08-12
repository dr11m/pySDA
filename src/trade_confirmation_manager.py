#!/usr/bin/env python3
"""
Trade Confirmation Manager - Модуль для работы с трейдами и подтверждениями
"""

import re
import time
import traceback
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any, Union
from urllib.parse import unquote

from src.utils.logger_setup import logger, print_and_log
from src.steampy.client import SteamClient
from src.steampy.guard import generate_one_time_code, generate_confirmation_key, load_steam_guard
from src.models import TradeOffersResponse, TradeOffer, TradeOfferState, SteamApiResponse
from src.cookie_manager import CookieManager
from src.steampy.confirmation import Confirmation, ConfirmationExecutor
from src.steampy.models import ConfirmationType


class TradeConfirmationManager:
    """Менеджер для работы с трейдами и подтверждениями"""
    
    def __init__(self, username: str, mafile_path: str, cookie_manager: CookieManager, api_key: Optional[str] = None):
        self.username = username
        self.mafile_path = mafile_path
        self.cookie_manager = cookie_manager
        self._steam_client: Optional[SteamClient] = None
        self._api_key = api_key
        
        # Загружаем данные Steam Guard
        try:
            self.steam_guard_data = load_steam_guard(mafile_path)
            logger.info(f"✅ Steam Guard данные загружены для {username}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки Steam Guard данных: {e}")
            raise
        
        logger.info(f"🔄 Trade Confirmation Manager инициализирован для {username}")
    
    def _get_steam_client(self) -> SteamClient:
        """Получает или создает экземпляр SteamClient."""
        # Всегда получаем свежий клиент из CookieManager
        self._steam_client = self.cookie_manager.get_steam_client()
        if not self._steam_client:
            raise Exception("Не удалось получить настроенный Steam клиент из CookieManager.")

        return self._steam_client
    
    def generate_guard_code(self) -> str:
        """Генерация кода мобильного аутентификатора"""
        try:
            shared_secret = self.steam_guard_data.get('shared_secret')
            if not shared_secret:
                raise ValueError("shared_secret не найден в Steam Guard данных")
            
            code = generate_one_time_code(shared_secret)
            return code
        except Exception as e:
            logger.error(f"❌ Ошибка генерации Guard кода: {e}")
            raise
    
    def get_trade_offers(self, active_only: bool = True, use_webtoken: bool = True) -> Optional[TradeOffersResponse]:
        """Получение трейд офферов"""
        try:
            steam_client = self._get_steam_client()
            
            logger.info("🔍 Получаем трейд офферы...")
            
            # Получаем API ключ только если не используем webtoken
            if not use_webtoken:
                # Приоритет: 1) API ключ из конфига, 2) существующий в клиенте, 3) получение автоматически
                if self._api_key:
                    # API ключ из конфига имеет высший приоритет
                    logger.info(f"🔑 Используем API ключ из конфига: {self._api_key[:10]}...")
                    steam_client._api_key = self._api_key
                elif steam_client._api_key:
                    # Если нет ключа в конфиге, но есть в клиенте - используем его
                    logger.info(f"🔑 Используем существующий API ключ: {steam_client._api_key[:10]}...")
                else:
                    # Если нет ключа нигде - получаем автоматически
                    logger.info("🔑 Получаем API ключ автоматически...")
                    
                    try:
                        # Пробуем получить через веб-интерфейс (самый надежный способ)
                        api_key = self._get_api_key_from_web(steam_client)
                        if api_key:
                            steam_client._api_key = api_key
                            logger.info(f"API ключ получен: {api_key[:10]}...")
                        else:
                            logger.error("Не удалось получить API ключ")
                            return None
                    except Exception as e:
                        logger.error(f"Ошибка получения API ключа: {e}")
                        return None
            else:
                logger.info("🔑 Используем access_token из cookies (webtoken)")
            
            # Получаем access_token если нужен
            access_token = None
            if use_webtoken:
                access_token = self._get_access_token(steam_client)
                if not access_token:
                    logger.error("❌ Не удалось получить access_token")
                    use_webtoken = False
            
            # Подготавливаем параметры
            params = {}
            if use_webtoken:
                params['access_token'] = access_token
            else:
                params['key'] = steam_client._api_key
            
            params.update({
                'get_sent_offers': 1,
                'get_received_offers': 1,
                'get_descriptions': 1,
                'language': 'english',
                'active_only': 1 if active_only else 0,
                'historical_only': 0,
                'time_historical_cutoff': ''
            })
            
            # Делаем запрос к API
            api_response = steam_client.api_call('GET', 'IEconService', 'GetTradeOffers', 'v1', params)
            response_data = api_response.json()
            

            
            # Парсим ответ напрямую как TradeOffersResponse
            trade_offers = TradeOffersResponse(**response_data.get('response', {}))
            
            logger.info(f"✅ Получено трейд офферов:")
            logger.info(f"  - Входящие всего: {len(trade_offers.trade_offers_received)}")
            logger.info(f"  - Входящие активные: {len(trade_offers.active_received)}")
            logger.info(f"  - Входящие требующие подтверждения: {len(trade_offers.confirmation_needed_received)}")
            logger.info(f"  - Исходящие всего: {len(trade_offers.trade_offers_sent)}")
            logger.info(f"  - Исходящие активные: {len(trade_offers.active_sent)}")
            logger.info(f"  - Исходящие требующие подтверждения: {len(trade_offers.confirmation_needed_sent)}")
            
            return trade_offers
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения трейд офферов: {e}")
            logger.debug(traceback.format_exc())
            return None
    
    def _get_api_key_from_web(self, steam_client: SteamClient) -> Optional[str]:
        """Получение API ключа через веб-интерфейс Steam (рабочий метод)"""
        try:
            logger.info("Получаем API ключ через веб-интерфейс...")
            
            # Steam клиент уже загружен с сессией из pkl файла
            # Делаем запрос к странице API ключа
            req = steam_client._session.get('https://steamcommunity.com/dev/apikey')
            
            if req.status_code != 200:
                logger.error(f"Ошибка запроса к странице API ключа: {req.status_code}")
                return None
            
            # Проверяем, что мы не попали на страницу входа
            if 'Sign In' in req.text and 'login' in req.url.lower():
                logger.error("Перенаправление на страницу входа. Проверьте cookies.")
                return None
            
            # Используем рабочий регекс из оригинального кода
            data_apikey = re.findall(r"([^\\\n.>\\\t</_=:, $(abcdefghijklmnopqrstuvwxyz )&;-]{32})", fr"{req.text}")
            
            logger.info(f"Найдено потенциальных ключей: {len(data_apikey)}")
            if data_apikey:
                logger.info(f"Найденные ключи: {data_apikey}")
            
            if len(data_apikey) == 1:
                apikey = data_apikey[0]
                steam_client._api_key = apikey
                logger.info(f"API ключ найден: {apikey[:10]}...")
                return apikey
            elif len(data_apikey) > 1:
                # Если найдено несколько ключей, берем первый
                apikey = data_apikey[0]
                steam_client._api_key = apikey
                logger.info(f"Найдено {len(data_apikey)} ключей, используем первый: {apikey[:10]}...")
                return apikey
            else:
                # API ключ не найден, возможно нужно создать
                logger.info("API ключ не найден, проверяем нужно ли его создать...")
                
                if 'You must have a validated email address' in req.text:
                    logger.error("Для получения API ключа нужно подтвердить email")
                    return None
                elif 'Register for a Steam Web API Key' in req.text:
                    logger.info("API ключ не создан, пробуем создать...")
                    return self._create_api_key(steam_client)
                else:
                    logger.warning("Не удалось найти API ключ на странице")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка получения API ключа через веб: {e}")
            return None
    
    def _create_api_key(self, steam_client: SteamClient) -> Optional[str]:
        """Создание нового API ключа"""
        try:
            logger.info("Создаем новый API ключ...")
            
            # Сначала получаем форму
            response = steam_client._session.get('https://steamcommunity.com/dev/apikey')
            
            # Извлекаем sessionid для CSRF защиты
            sessionid_pattern = r'g_sessionID = "([^"]+)"'
            sessionid_match = re.search(sessionid_pattern, response.text)
            
            if not sessionid_match:
                logger.error("Не удалось найти sessionid для создания API ключа")
                return None
            
            sessionid = sessionid_match.group(1)
            
            # Отправляем POST запрос для создания ключа
            create_data = {
                'domain': 'test',  # Домен можно любой
                'agreeToTerms': 'agreed',
                'sessionid': sessionid,
                'Submit': 'Register'
            }
            
            create_response = steam_client._session.post(
                'https://steamcommunity.com/dev/registerkey',
                data=create_data
            )
            
            if create_response.status_code == 200:
                # Проверяем результат
                if 'successful' in create_response.text.lower():
                    logger.info("API ключ успешно создан, получаем его...")
                    # Снова запрашиваем страницу чтобы получить ключ
                    time.sleep(1)
                    return self._get_api_key_from_web(steam_client)
                else:
                    logger.error("Не удалось создать API ключ")
                    return None
            else:
                logger.error(f"Ошибка создания API ключа: {create_response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка создания API ключа: {e}")
            return None

    def _get_access_token(self, steam_client: SteamClient) -> Optional[str]:
        """Извлечение access_token из cookies"""
        try:
            jar = steam_client._session.cookies
            steam_login_secure_cookie = None
            
            # Показываем все доступные cookies для отладки
            available_cookies = [f"{cookie.name}@{cookie.domain}" for cookie in jar]
            logger.info(f"📋 Все доступные cookies в trade_confirmation_manager: {available_cookies}")
            
            # Показываем детальную информацию о каждом cookie
            logger.info("🔍 Детальная информация о cookies:")
            for cookie in jar:
                logger.info(f"  {cookie.name}@{cookie.domain} = {cookie.value[:50]}... (secure: {cookie.secure}, expires: {cookie.expires})")
            
            # Ищем steamLoginSecure в любом домене для отладки
            steam_login_secure_found = False
            for cookie in jar:
                if cookie.name == 'steamLoginSecure':
                    steam_login_secure_found = True
                    logger.info(f"🔍 Найден steamLoginSecure в домене: {cookie.domain} (но ищем только в steamcommunity.com)")
            
            # Ищем steamLoginSecure только в steamcommunity.com
            for cookie in jar:
                if cookie.name == 'steamLoginSecure' and cookie.domain == 'steamcommunity.com':
                    steam_login_secure_cookie = cookie.value
                    logger.info(f"✅ Найден steamLoginSecure в домене: {cookie.domain}")
                    break
            
            if not steam_login_secure_cookie:
                logger.warning("❌ Cookie 'steamLoginSecure' не найден в домене steamcommunity.com")
                if steam_login_secure_found:
                    logger.warning("⚠️ Но steamLoginSecure найден в других доменах!")
                return None
            
            decoded_cookie_value = unquote(steam_login_secure_cookie)
            access_token_parts = decoded_cookie_value.split('||')
            
            if len(access_token_parts) < 2:
                logger.error("❌ Не удалось извлечь access_token из cookie")
                return None
            
            access_token = access_token_parts[1]
            logger.info(f"✅ Access token извлечен: {access_token[:15]}...")
            return access_token
            
        except Exception as e:
            logger.error(f"❌ Ошибка извлечения access_token: {e}")
            return None
    
    def get_confirmations(self) -> List[Dict[str, Any]]:
        """Получение списка подтверждений"""
        try:
            steam_client = self._get_steam_client()
            
            logger.info("🔍 Получаем подтверждения мобильного аутентификатора...")
            
            # Проверяем наличие steam_guard для работы с подтверждениями
            if not hasattr(steam_client, 'steam_guard') or not steam_client.steam_guard:
                logger.warning("⚠️ Steam Guard не настроен, невозможно получить подтверждения")
                return []
            
            # Создаем ConfirmationExecutor для работы с подтверждениями
            from .steampy.confirmation import ConfirmationExecutor
            
            confirmation_executor = ConfirmationExecutor(
                identity_secret=steam_client.steam_guard['identity_secret'],
                my_steam_id=steam_client.steam_id,
                session=steam_client._session
            )
            
            # Получаем подтверждения через ConfirmationExecutor
            confirmations = confirmation_executor._get_confirmations()
            
            if confirmations:
                logger.info(f"✅ Найдено {len(confirmations)} подтверждений")
                
                # Преобразуем в формат словарей для совместимости
                confirmations_data = []
                for i, conf in enumerate(confirmations, 1):
                    conf_data = {
                        'id': conf.data_confid,
                        'nonce': conf.nonce,
                        'creator_id': conf.creator_id,
                        'type': 'unknown'  # Тип будет определен позже при необходимости
                    }
                    confirmations_data.append(conf_data)
                    
                    logger.info(f"  {i}. ID: {conf.data_confid}, Creator ID: {conf.creator_id}")
                
                return confirmations_data
            else:
                logger.info("ℹ️ Подтверждений не найдено")
                print_and_log("ℹ️ Подтверждений не найдено")
                return []
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения подтверждений: {e}")
            logger.debug(traceback.format_exc())
            return []
    
    def get_guard_confirmations(self) -> List[Dict[str, Any]]:
        """Получение ВСЕХ подтверждений Guard с детальной информацией"""
        try:
            steam_client = self._get_steam_client()
            
            logger.info("🔐 Получаем все подтверждения Guard...")
            
            # Проверяем наличие steam_guard для работы с подтверждениями
            if not hasattr(steam_client, 'steam_guard') or not steam_client.steam_guard:
                logger.warning("⚠️ Steam Guard не настроен, невозможно получить подтверждения")
                return []
            
            # Создаем ConfirmationExecutor для работы с подтверждениями
            from .steampy.confirmation import ConfirmationExecutor
            from src.utils.confirmation_utils import determine_confirmation_type_from_json, extract_confirmation_info
            
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
            
            if not all_confirmations:
                logger.info("ℹ️ Подтверждений Guard не найдено")
                return []
            
            logger.info(f"✅ Найдено {len(all_confirmations)} подтверждений Guard")
            
            # Получаем детальную информацию для каждого подтверждения
            detailed_confirmations = []
            for i, conf_data in enumerate(all_confirmations, 1):
                try:
                    # Определяем тип подтверждения по JSON данным
                    confirmation_type = determine_confirmation_type_from_json(conf_data)
                    
                    # Извлекаем дополнительную информацию через единую функцию
                    confirmation_info = extract_confirmation_info(conf_data, confirmation_type)
                    
                    # Создаем объект Confirmation для совместимости
                    conf = Confirmation(
                        data_confid=conf_data['id'],
                        nonce=conf_data['nonce'],
                        creator_id=int(conf_data['creator_id'])
                    )
                    
                    detailed_conf = {
                        'id': conf_data['id'],
                        'nonce': conf_data['nonce'],
                        'creator_id': int(conf_data['creator_id']),
                        'type': confirmation_type,
                        'description': confirmation_info.get('description', f'Подтверждение #{conf_data["id"]}'),
                        'confirmation_info': confirmation_info,  # Сохраняем дополнительную информацию
                        'confirmation': conf  # Сохраняем оригинальный объект для подтверждения
                    }
                    
                    detailed_confirmations.append(detailed_conf)
                    
                    logger.info(f"  {i}. {confirmation_type} - {detailed_conf['description']} (ID: {conf_data['id']})")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обработки подтверждения {conf_data.get('id', 'unknown')}: {e}")
                    # Добавляем базовую информацию даже при ошибке
                    detailed_conf = {
                        'id': conf_data.get('id', 'unknown'),
                        'nonce': conf_data.get('nonce', ''),
                        'creator_id': int(conf_data.get('creator_id', 0)),
                        'type': 'unknown',
                        'description': f'Подтверждение #{conf_data.get("id", "unknown")}',
                        'confirmation_info': {},
                        'confirmation': None
                    }
                    detailed_confirmations.append(detailed_conf)
            
            return detailed_confirmations
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения подтверждений Guard: {e}")
            logger.debug(traceback.format_exc())
            return []
    
    def _determine_confirmation_type(self, details_html: str) -> str:
        """Определение типа подтверждения по HTML содержимому"""
        from src.utils.confirmation_utils import determine_confirmation_type
        return determine_confirmation_type(details_html)
    
    def _extract_confirmation_info(self, details_html: str, confirmation_type: str) -> Dict[str, Any]:
        """Извлечение дополнительной информации из HTML подтверждения"""
        from src.utils.confirmation_utils import extract_confirmation_info
        return extract_confirmation_info(details_html, confirmation_type)
    
    def confirm_guard_confirmation(self, confirmation_obj) -> bool:
        """Подтверждение конкретного подтверждения Guard"""
        try:
            steam_client = self._get_steam_client()
            
            logger.info(f"🔑 Подтверждаем подтверждение Guard: {confirmation_obj.data_confid}")
            
            # Создаем ConfirmationExecutor
            from .steampy.confirmation import ConfirmationExecutor
            
            confirmation_executor = ConfirmationExecutor(
                identity_secret=steam_client.steam_guard['identity_secret'],
                my_steam_id=steam_client.steam_id,
                session=steam_client._session
            )
            
            # Подтверждаем через executor используя переданный объект
            response = confirmation_executor._send_confirmation(confirmation_obj)
            
            if response and response.get('success'):
                logger.info(f"✅ Подтверждение {confirmation_obj.data_confid} успешно обработано")
                return True
            else:
                error_message = response.get('error', 'Unknown error') if response else 'No response'
                logger.error(f"❌ Ошибка подтверждения {confirmation_obj.data_confid}: {error_message}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка подтверждения Guard: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    def accept_trade_offer(self, trade_offer_id: str, partner_account_id: str = None) -> bool:
        """Принятие трейд оффера через steampy клиент (только веб-принятие, без Guard)"""
        try:
            steam_client = self._get_steam_client()
            
            logger.info(f"Принимаем трейд оффер в веб-интерфейсе: {trade_offer_id}")
            
            # Используем оптимизированный метод если у нас есть partner_account_id
            if partner_account_id:
                result = steam_client.accept_trade_offer_optimized(trade_offer_id, partner_account_id)
            else:
                result = steam_client.accept_trade_offer(trade_offer_id)
            
            if result is None:
                logger.error(f"Трейд оффер {trade_offer_id}: Получен пустой ответ от Steam")
                return False
            elif result.get('tradeid'):
                logger.info(f"Трейд оффер {trade_offer_id} успешно принят в веб-интерфейсе (Trade ID: {result['tradeid']})")
                return True
            elif result.get('needs_mobile_confirmation'):
                logger.info(f"Трейд оффер {trade_offer_id} принят в веб-интерфейсе, требует подтверждения через Guard")
                return True
            elif result.get('strError'):
                logger.error(f"Ошибка Steam при принятии в веб-интерфейсе: {result['strError']}")
                return False
            else:
                logger.warning(f"Неожиданный ответ при принятии в веб-интерфейсе: {result}")
                # Даже если ответ неожиданный, считаем что трейд принят если нет явной ошибки
                return True
            
        except Exception as e:
            logger.error(f"Ошибка принятия трейд оффера {trade_offer_id} в веб-интерфейсе: {e}")
            logger.debug(traceback.format_exc())
            return False

    def accept_trade_offer_with_confirmation(self, trade_offer_id: str) -> bool:
        """Принятие трейд оффера через steampy клиент с автоматическим подтверждением через Guard"""
        try:
            steam_client = self._get_steam_client()
            
            logger.info(f"Принимаем трейд оффер с автоподтверждением: {trade_offer_id}")
            
            # Используем метод steampy с автоматическим подтверждением
            result = steam_client.accept_trade_offer_with_confirmation(trade_offer_id)
            
            if result.get('tradeid'):
                logger.info(f"Трейд оффер {trade_offer_id} успешно принят и подтвержден (Trade ID: {result['tradeid']})")
                return True
            elif result.get('strError'):
                logger.error(f"Ошибка Steam: {result['strError']}")
                return False
            else:
                logger.warning(f"Неожиданный ответ: {result}")
                return True
            
        except Exception as e:
            logger.error(f"Ошибка принятия трейд оффера {trade_offer_id} с подтверждением: {e}")
            logger.debug(traceback.format_exc())
            return False

    def confirm_accepted_trade_offer(self, trade_offer_id: str) -> bool:
        """Подтверждение уже принятого трейд оффера через Steam Guard"""
        try:
            steam_client = self._get_steam_client()
            
            logger.info(f"🔑 Подтверждаем уже принятый трейд оффер через Guard: {trade_offer_id}")
            
            # Используем новый метод steampy для подтверждения уже принятого трейда
            result = steam_client.confirm_accepted_trade_offer(trade_offer_id)
            
            if result and not result.get('strError'):
                logger.info(f"✅ Трейд оффер {trade_offer_id} успешно подтвержден через Guard")
                return True
            else:
                error_msg = result.get('strError', 'Неизвестная ошибка') if result else 'Пустой ответ'
                logger.error(f"❌ Не удалось подтвердить трейд оффер {trade_offer_id} через Guard: {error_msg}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка подтверждения трейда {trade_offer_id} через Guard: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    def decline_trade_offer(self, trade_offer_id: str) -> bool:
        """Отклонение трейд оффера"""
        try:
            steam_client = self._get_steam_client()
            
            logger.info(f"❌ Отклоняем трейд оффер: {trade_offer_id}")
            
            # Используем метод steampy для отклонения трейда
            result = steam_client.decline_trade_offer(trade_offer_id)
            
            if result:
                logger.info(f"✅ Трейд оффер {trade_offer_id} успешно отклонен")
            else:
                logger.error(f"❌ Не удалось отклонить трейд оффер {trade_offer_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка отклонения трейд оффера {trade_offer_id}: {e}")
            logger.debug(traceback.format_exc())
            return False
    
    def process_free_trades(self, auto_accept: bool = True, auto_confirm: bool = True) -> Dict[str, int]:
        """
        Обработка бесплатных входящих трейдов (подарков)
        
        Args:
            auto_accept: Автоматически принимать бесплатные трейды
            auto_confirm: Автоматически подтверждать принятые трейды
            
        Returns:
            Dict с количеством обработанных трейдов
        """
        stats = {
            'found_free_trades': 0,
            'accepted_trades': 0,
            'confirmed_trades': 0,
            'errors': 0
        }
        
        try:
            logger.info("🎁 Ищем бесплатные трейды (подарки)...")
            
            # Получаем активные трейды
            trade_offers = self.get_trade_offers(active_only=True)
            if not trade_offers:
                logger.info("ℹ️ Трейд офферы не получены")
                return stats
            
            # Ищем бесплатные входящие трейды
            free_trades = []
            for offer in trade_offers.active_received:
                # Бесплатный трейд = мы ничего не отдаем, но что-то получаем
                if offer.items_to_give_count == 0 and offer.items_to_receive_count > 0:
                    free_trades.append(offer)
                    logger.info(f"🎁 Найден бесплатный трейд: {offer.tradeofferid} (получаем {offer.items_to_receive_count} предметов)")
            
            stats['found_free_trades'] = len(free_trades)
            
            if not free_trades:
                logger.info("ℹ️ Бесплатных трейдов не найдено")
                print_and_log("ℹ️ Бесплатных трейдов не найдено")
                return stats
            
            logger.info(f"🎁 Найдено {len(free_trades)} бесплатных трейдов")
            
            # Обрабатываем каждый бесплатный трейд
            for offer in free_trades:
                try:
                    if auto_accept:
                        # Шаг 1: Принимаем трейд в веб-интерфейсе (оптимизированно)
                        logger.info(f"🌐 Принимаем в веб-интерфейсе: {offer.tradeofferid}")
                        # Используем partner_account_id для оптимизации (убираем лишние GET запросы)
                        partner_account_id = str(offer.accountid_other)
                        if self.accept_trade_offer(offer.tradeofferid, partner_account_id):
                            stats['accepted_trades'] += 1
                            logger.info(f"✅ Принят в веб-интерфейсе бесплатный трейд: {offer.tradeofferid}")
                            
                            # Ждем немного перед подтверждением
                            time.sleep(2)
                            
                            if auto_confirm:
                                # Шаг 2: Подтверждаем уже принятый трейд через Guard
                                logger.info(f"🔑 Подтверждаем через Guard: {offer.tradeofferid}")
                                if self.confirm_accepted_trade_offer(offer.tradeofferid):
                                    stats['confirmed_trades'] += 1
                                    logger.info(f"🔑 Подтвержден через Guard бесплатный трейд: {offer.tradeofferid}")
                                else:
                                    logger.warning(f"⚠️ Не удалось подтвердить через Guard трейд: {offer.tradeofferid}")
                                    stats['errors'] += 1
                            else:
                                logger.info(f"ℹ️ Трейд {offer.tradeofferid} принят в веб-интерфейсе, но auto_confirm отключен")
                        else:
                            logger.error(f"❌ Не удалось принять в веб-интерфейсе бесплатный трейд: {offer.tradeofferid}")
                            stats['errors'] += 1
                    else:
                        logger.info(f"ℹ️ Бесплатный трейд найден, но auto_accept отключен: {offer.tradeofferid}")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки трейда {offer.tradeofferid}: {e}")
                    stats['errors'] += 1
            
            # Итоговая статистика
            logger.info(f"📊 Статистика обработки бесплатных трейдов:")
            logger.info(f"  - Найдено: {stats['found_free_trades']}")
            logger.info(f"  - Принято: {stats['accepted_trades']}")
            logger.info(f"  - Подтверждено: {stats['confirmed_trades']}")
            logger.info(f"  - Ошибок: {stats['errors']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки бесплатных трейдов: {e}")
            logger.debug(traceback.format_exc())
            stats['errors'] += 1
            return stats
    
    def process_confirmation_needed_trades(self, auto_confirm: bool = True) -> Dict[str, int]:
        """
        Обработка трейдов, требующих подтверждения (уже принятых в вебе)
        
        Args:
            auto_confirm: Автоматически подтверждать трейды
            
        Returns:
            Dict с количеством обработанных трейдов
        """
        stats = {
            'found_confirmation_needed': 0,
            'confirmed_trades': 0,
            'errors': 0
        }
        
        try:
            logger.info("🔑 Ищем трейды, требующие подтверждения...")
            
            # Получаем все трейды
            trade_offers = self.get_trade_offers(active_only=False)
            if not trade_offers:
                logger.info("ℹ️ Трейд офферы не получены")
                return stats
            
            # Ищем трейды, требующие подтверждения
            confirmation_needed_trades = []
            confirmation_needed_trades.extend(trade_offers.confirmation_needed_received)
            confirmation_needed_trades.extend(trade_offers.confirmation_needed_sent)
            
            stats['found_confirmation_needed'] = len(confirmation_needed_trades)
            
            if not confirmation_needed_trades:
                logger.info("ℹ️ Трейдов, требующих подтверждения, не найдено")
                print_and_log("ℹ️ Трейдов, требующих подтверждения, не найдено")
                return stats
            
            logger.info(f"🔑 Найдено {len(confirmation_needed_trades)} трейдов, требующих подтверждения")
            
            # Обрабатываем каждый трейд
            for offer in confirmation_needed_trades:
                try:
                    logger.info(f"🔑 Обрабатываем трейд: {offer.tradeofferid} (состояние: {offer.state_name})")
                    
                    if auto_confirm:
                        # Подтверждаем трейд через Guard
                        if self.confirm_accepted_trade_offer(offer.tradeofferid):
                            stats['confirmed_trades'] += 1
                            logger.info(f"✅ Подтвержден трейд: {offer.tradeofferid}")
                        else:
                            logger.warning(f"⚠️ Не удалось подтвердить трейд: {offer.tradeofferid}")
                            stats['errors'] += 1
                            
                        # Небольшая пауза между подтверждениями
                        time.sleep(1)
                    else:
                        logger.info(f"ℹ️ Трейд требует подтверждения, но auto_confirm отключен: {offer.tradeofferid}")
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки трейда {offer.tradeofferid}: {e}")
                    stats['errors'] += 1
            
            # Итоговая статистика
            logger.info(f"📊 Статистика подтверждения трейдов:")
            logger.info(f"  - Найдено требующих подтверждения: {stats['found_confirmation_needed']}")
            logger.info(f"  - Подтверждено: {stats['confirmed_trades']}")
            logger.info(f"  - Ошибок: {stats['errors']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки трейдов, требующих подтверждения: {e}")
            logger.debug(traceback.format_exc())
            stats['errors'] += 1
            return stats 