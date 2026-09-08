from __future__ import annotations

import os
import json
import re
import bs4
import urllib.parse as urlparse
import decimal
import requests
from typing import Union
import pickle
from contextlib import contextmanager
import yaml

from . import guard
from .confirmation import ConfirmationExecutor
from .exceptions import ApiException, SevenDaysHoldException, TooManyRequests, EResultError
from .login import InvalidCredentials, LoginExecutor
from .market import SteamMarket
from .models import Asset, GameOptions, SteamUrl, TradeOfferState
from .models import STEAM_URL, EResult
from .session_check import check_session_static as is_market_session_alive
from src.utils.delayed_http_adapter import DelayedHTTPAdapter


from .utils import (
    account_id_to_steam_id,
    get_description_key,
    get_key_value_from_url,
    login_required,
    merge_items_with_descriptions_from_inventory,
    merge_items_with_descriptions_from_offer,
    merge_items_with_descriptions_from_offers,
    ping_proxy,
    steam_id_to_account_id,
    text_between,
    texts_between,
    parse_price
)

from src.utils.logger_setup import logger
from src.utils.compare_sessions import compare_sessions_and_log_diff
from src.interfaces.storage_interface import CookieStorageInterface
from src.utils.cookies_and_session import session_to_dict
from src.utils.ip_utils import check_ip


class SteamClient:
    # Константы для Steam API
    STEAM_LOGIN_BASE = 'https://login.steampowered.com'
    STEAM_COMMUNITY = 'https://steamcommunity.com'

    def __init__(
        self,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        steam_guard: str | None = None,
        proxies: dict | None = None,
        steam_id: str | None = None,
        session_path: str | None = None,
        storage: 'CookieStorageInterface' = None,
    ) -> None:
        self._api_key = api_key
        self.steam_id = steam_id
        self.session_path = session_path 
        self.refresh_token = None
        self.storage = storage

        # Инициализируем сессию сначала
        if session_path and os.path.exists(session_path):
            with open(session_path, 'rb') as f:
                self._session, self.refresh_token = pickle.load(f)
        else:
            self._session = requests.Session()

        # Теперь можем устанавливать прокси
        if proxies:
            self.set_proxies(proxies)

        self.steam_guard_string = steam_guard
        if self.steam_guard_string is not None:
            self.steam_guard = guard.load_steam_guard(self.steam_guard_string)
        else:
            self.steam_guard = None

        self.was_login_executed = False
        self.username = username
        self._password = password

        self.market = SteamMarket(self._session, self.steam_id)
        
        # Переопределяем методы сессии для проверки IP если настройка включена
        if self._should_check_ip():
            self._wrap_session_methods()
    
    def _should_check_ip(self) -> bool:
        """Проверяет, нужно ли проверять IP перед запросами"""
        # Local import to avoid circular dependency with src.cli package
        from src.cli.constants import Config

        with open(Config.DEFAULT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            return config_data.get(Config.CHECK_IP_ON_EVERY_STEAM_REQUEST, False)
    
    def _wrap_session_methods(self):
        """Оборачиваем методы сессии для проверки IP перед каждым запросом"""
        original_get = self._session.get
        original_post = self._session.post
        
        def wrapped_get(*args, **kwargs):
            # Проверяем IP перед запросом
            check_ip(original_get)
            return original_get(*args, **kwargs)
            
        def wrapped_post(*args, **kwargs):
            # Проверяем IP перед запросом
            check_ip(original_get)
            return original_post(*args, **kwargs)
        
        self._session.get = wrapped_get
        self._session.post = wrapped_post

    @contextmanager
    def temporary_delay(self, new_delay: float = 0.1):
        """
        Контекстный менеджер для временного изменения задержки через замену адаптеров
        """
        original_adapters = {}
        
        # Сохраняем оригинальные адаптеры и устанавливаем новые
        for prefix in ['http://', 'https://']:
            original_adapter = self._session.get_adapter(prefix)
            original_adapters[prefix] = original_adapter
            
            # Создаем НОВЫЙ адаптер с нужной задержкой
            new_adapter = DelayedHTTPAdapter(delay=new_delay)
            self._session.mount(prefix, new_adapter)
            
            logger.debug(f"Установлен временный адаптер для {prefix} с задержкой {new_delay}")
        
        try:
            yield
        finally:
            # Восстанавливаем оригинальные адаптеры
            for prefix, original_adapter in original_adapters.items():
                self._session.mount(prefix, original_adapter)
                delay = getattr(original_adapter, 'delay', 'неизвестно')
                logger.debug(f"Восстановлен оригинальный адаптер для {prefix} с задержкой {delay}")

    def _try_refresh_session(self) -> bool:
        """Попытка обновить сессию через refresh токен"""
        if not self.refresh_token:
            logger.info(f"❌ Refresh токен не найден для {self.username}")
            return False
            
        try:
            logger.info(f"🔄 Пробуем обновить сессию через refresh токен ({self.refresh_token[:10]}...) для {self.username} [{self.steam_id}]")
            
            # Логируем старые cookies
            old_session = self._session
            logger.info(f"📋 Старые cookies: {self._session.__dict__}")
            
            
            login_executor = LoginExecutor(self.steam_id,
                                           self.username,
                                           self._password,
                                           self.steam_guard['shared_secret'],
                                           self._session)
            
            login_executor.get_web_cookies(self.refresh_token, self.steam_id)

            self._session = login_executor.session

            self.was_login_executed = True

            new_session = self._session
            compare_sessions_and_log_diff(old_session, new_session)

            # Сохраняем сессию
            self.save_session(os.path.dirname(self.session_path), self.username)
            logger.info(f"💾 Сессия сохранена в pkl и в хранилище для {self.username}")
            
            # Логируем новые cookies
            logger.info(f"📋 Новые cookies: {self._session.__dict__}")
            
            logger.info(f"✅ Сессия обновлена через refresh токен для {self.username}")
            
            # Проверяем сессию
            if not self.check_session_static(self.username, self._session):
                logger.info(f"❌ Сессия была обновлена через refresh token, но не прошла проверку {self.username})")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления сессии для {self.username}: {e}")
            return False

    def set_proxies(self, proxies: dict) -> dict:
        if not isinstance(proxies, dict):
            raise TypeError(
                'Proxy must be a dict. Example: '
                r'\{"http": "http://login:password@host:port"\, "https": "http://login:password@host:port"\}',
            )

        if ping_proxy(proxies):
            self._session.proxies.update(proxies)

        return proxies

    def login_if_need_to(self):        
        if self.was_login_executed:
            logger.info(f"✅ Login already executed for {self.username}, skipping check")
            return
        
        if not self.check_session_static(self.username, self._session):
            self.update_session()
        else:
            logger.info(f"✅ Сессия активна для {self.username}")
            self.was_login_executed = True
            self.market._set_login_executed(self.steam_guard, self._get_session_id())

    def update_session(self):
        """
        Логика метода update_session теперь следующая:
        Получение cookies для всех доменов (community, store, help) происходит через refresh_token.
        Если refresh_token отсутствует или невалиден, мы выполняем полный вход в Steam для его получения.
        После этого получаем cookies для всех доменов через refresh_token 
        
        change log:
        * < 2.2.3 
            - мы получал куки частично на этапе входа 
            = два разных метода для получения куков без/c refresh_token

        * > 2.2.4
            - мы получаем refresh_token на этапе входа и сохраняем
            - мы получаем cookies для всех доменов через refresh_token

        """
        
        # Устанавливаем быструю задержку для всех авторизационных запросов
        with self.temporary_delay(1):  # или какое значение вы хотите
            # Сначала пробуем обновить через refresh token
            if self._try_refresh_session():
                self.was_login_executed = True
                self.market._set_login_executed(self.steam_guard, self._get_session_id())
                return
                
            # Если refresh token не сработал, делаем полный вход
            print(f"🔐 Выполняем полный вход для {self.username}...")
            self._session.cookies.clear()
            session, refresh_token = LoginExecutor(self.steam_id, self.username, self._password, self.steam_guard['shared_secret'], self._session).login()
            self.refresh_token = refresh_token
            self._session = session
            print(f"💾 Получен новый refresh токен для {self.username}")
            self.was_login_executed = True
            self.market._set_login_executed(self.steam_guard, self._get_session_id())
            # Сохраняем сессию
            self.save_session(os.path.dirname(self.session_path), self.username)
            logger.info(f"💾 Сессия сохранена в pkl и в хранилище для {self.username}")


    @staticmethod
    def check_session_static(username, _session) -> bool:
        """Return True when market/mylistings accepts the session cookies."""
        return is_market_session_alive(username, _session)

    @login_required
    def save_session(self, path, username):
        with open(os.path.join(path, f'{username}.pkl'), 'wb') as f:
            pickle.dump((self._session, self.refresh_token), f)
        print(f"💾 Сессия и refresh токен сохранены в pkl для {username}")
        
        # Обновляем cookies в БД через implementations
        try:
            cookies_dict = session_to_dict(self._session)
            if self.storage.save_cookies(username, cookies_dict):
                logger.info(f"💾 Cookies обновлены в БД при сохранении сессии для {username}")
            else:
                logger.warning(f"⚠️ Не удалось обновить cookies в БД при сохранении сессии для {username}")
        except Exception as e:
            logger.error(f"❌ Ошибка обновления cookies в БД при сохранении сессии для {username}: {e}")

    @login_required
    def logout(self) -> None:
        url = f'{SteamUrl.STORE_URL}/login/logout/'
        data = {'sessionid': self._get_session_id()}
        self._session.post(url, data=data)

        if self.is_session_alive():
            raise Exception('Logout unsuccessful')

        self.was_login_executed = False

    def __enter__(self):
        self.login_if_need_to(self.username, self._password, self.steam_guard_string)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()

    @login_required
    def is_session_alive(self) -> bool:
        steam_login = self.username
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        }
        main_page_response = self._session.get(SteamUrl.COMMUNITY_URL, headers=headers)
        #print(main_page_response.status_code)
        #print(main_page_response.text)
        return steam_login.lower() in main_page_response.text.lower()

    def api_call(
        self, method: str, interface: str, api_method: str, version: str, params: dict | None = None,
    ) -> requests.Response:
        url = f'{SteamUrl.API_URL}/{interface}/{api_method}/{version}'
        response = self._session.get(url, params=params) if method == 'GET' else self._session.post(url, data=params)

        # Проверяем ошибки только если используем API ключ
        if 'key' in (params or {}):
            if self.is_invalid_api_key(response):
                raise InvalidCredentials('Invalid API key')
        else:
            # Для access_token: только статусы авторизации означают
            # проблемы с credentials, остальные — обычные ошибки API
            if response.status_code in (401, 403):
                raise InvalidCredentials(f"HTTP {response.status_code}: {response.text}")
            if response.status_code != 200:
                raise ApiException(f"HTTP {response.status_code}: {response.text}")

        return response

    @staticmethod
    def is_invalid_api_key(response: requests.Response) -> bool:
        msg = 'Access is denied. Retrying will not help. Please verify your <pre>key=</pre> parameter'
        return msg in response.text

    @login_required
    def get_my_inventory(self, game: GameOptions, merge: bool = True, count: int = 5000) -> dict:
        return self.get_partner_inventory(self.steam_id, game, merge, count)

    @login_required
    def get_partner_inventory(
        self, partner_steam_id: str, game: GameOptions, merge: bool = True, count: int = 5000,
    ) -> dict:
        url = f'{SteamUrl.COMMUNITY_URL}/inventory/{partner_steam_id}/{game.app_id}/{game.context_id}'
        params = {'l': 'english', 'count': count}

        full_response = self._session.get(url, params=params)
        response_dict = full_response.json()
        if full_response.status_code == 429:
            raise TooManyRequests('Too many requests, try again later.')

        if response_dict is None or response_dict.get('success') != 1:
            raise ApiException('Success value should be 1.')

        return merge_items_with_descriptions_from_inventory(response_dict, game) if merge else response_dict

    def _get_session_id(self) -> str:
        return self._session.cookies.get_dict()['sessionid']

    def get_trade_offers_summary(self) -> dict:
        params = {'key': self._api_key}
        return self.api_call('GET', 'IEconService', 'GetTradeOffersSummary', 'v1', params).json()

    def get_trade_offers(self, merge: bool = True) -> dict:
        params = {
            'key': self._api_key,
            'get_sent_offers': 1,
            'get_received_offers': 1,
            'get_descriptions': 1,
            'language': 'english',
            'active_only': 1,
            'historical_only': 0,
            'time_historical_cutoff': '',
        }
        response = self.api_call('GET', 'IEconService', 'GetTradeOffers', 'v1', params).json()
        response = self._filter_non_active_offers(response)

        return merge_items_with_descriptions_from_offers(response) if merge else response

    @staticmethod
    def _filter_non_active_offers(offers_response):
        offers_received = offers_response['response'].get('trade_offers_received', [])
        offers_sent = offers_response['response'].get('trade_offers_sent', [])

        offers_response['response']['trade_offers_received'] = list(
            filter(lambda offer: offer['trade_offer_state'] == TradeOfferState.Active, offers_received),
        )
        offers_response['response']['trade_offers_sent'] = list(
            filter(lambda offer: offer['trade_offer_state'] == TradeOfferState.Active, offers_sent),
        )

        return offers_response

    def get_trade_offer(self, trade_offer_id: str, merge: bool = True) -> dict:
        params = {'key': self._api_key, 'tradeofferid': trade_offer_id, 'language': 'english'}
        response = self.api_call('GET', 'IEconService', 'GetTradeOffer', 'v1', params).json()

        if merge and 'descriptions' in response['response']:
            descriptions = {get_description_key(offer): offer for offer in response['response']['descriptions']}
            offer = response['response']['offer']
            response['response']['offer'] = merge_items_with_descriptions_from_offer(offer, descriptions)

        return response

    def get_trade_history(
        self,
        max_trades: int = 100,
        start_after_time=None,
        start_after_tradeid=None,
        get_descriptions: bool = True,
        navigating_back: bool = True,
        include_failed: bool = True,
        include_total: bool = True,
    ) -> dict:
        params = {
            'key': self._api_key,
            'max_trades': max_trades,
            'start_after_time': start_after_time,
            'start_after_tradeid': start_after_tradeid,
            'get_descriptions': get_descriptions,
            'navigating_back': navigating_back,
            'include_failed': include_failed,
            'include_total': include_total,
        }
        return self.api_call('GET', 'IEconService', 'GetTradeHistory', 'v1', params).json()

    @login_required
    def get_trade_receipt(self, trade_id: str):
        html = self._session.get(f'https://steamcommunity.com/trade/{trade_id}/receipt').content.decode()
        return [json.loads(item) for item in texts_between(html, 'oItem = ', ';\r\n\toItem')]

    @login_required
    def accept_trade_offer_optimized(self, trade_offer_id: str, partner_account_id: str = None) -> dict:
        """
        Оптимизированное принятие трейд оффера в веб-интерфейсе (без дополнительных GET запросов)
        
        Args:
            trade_offer_id: ID трейд оффера
            partner_account_id: Account ID партнера (если известен, иначе будет получен через GET)
            
        Returns:
            Ответ от Steam API
        """
        # Если partner_account_id не передан, используем старый метод
        if not partner_account_id:
            return self.accept_trade_offer(trade_offer_id)
        
        # Конвертируем account_id в steam_id
        partner_steam_id = account_id_to_steam_id(partner_account_id)
        session_id = self._get_session_id()
        accept_url = f'{SteamUrl.COMMUNITY_URL}/tradeoffer/{trade_offer_id}/accept'
        
        # Параметры запроса
        params = {
            'sessionid': session_id,
            'serverid': '1',
            'tradeofferid': trade_offer_id,
            'partner': partner_steam_id,
            'captcha': '',
        }
        
        # Заголовки на основе рабочего curl запроса
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Origin': SteamUrl.COMMUNITY_URL,
            'Referer': self._get_trade_offer_url(trade_offer_id),
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'X-KL-Ajax-Request': 'Ajax_Request',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }

        try:
            response = self._session.post(accept_url, data=params, headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                # Возвращаем словарь с ошибкой
                return {
                    'strError': f'HTTP {response.status_code}: {response.text}',
                    'success': False
                }
        except Exception as e:
            # Возвращаем словарь с ошибкой
            return {
                'strError': f'Request failed: {str(e)}',
                'success': False
            }

    @login_required
    def accept_trade_offer(self, trade_offer_id: str) -> dict:
        """
        Принятие трейд оффера в веб-интерфейсе (без автоматического подтверждения через Guard)
        
        Args:
            trade_offer_id: ID трейд оффера
            
        Returns:
            Ответ от Steam API
        """
        # Убираем ненужную проверку через API - мы уже знаем что трейд активен
        # если он отображается в списке активных трейдов
        
        partner = self._fetch_trade_partner_id(trade_offer_id)
        session_id = self._get_session_id()
        accept_url = f'{SteamUrl.COMMUNITY_URL}/tradeoffer/{trade_offer_id}/accept'
        
        # Параметры запроса на основе рабочего curl
        params = {
            'sessionid': session_id,
            'serverid': '1',  # Убираем кавычки как в curl
            'tradeofferid': trade_offer_id,
            'partner': partner,
            'captcha': '',
        }

        
        # Заголовки на основе рабочего curl запроса
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Origin': SteamUrl.COMMUNITY_URL,
            'Referer': self._get_trade_offer_url(trade_offer_id),
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
            'X-KL-Ajax-Request': 'Ajax_Request',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'sec-ch-ua': '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }

        response = self._session.post(accept_url, data=params, headers=headers).json()
        
        # НЕ автоматически подтверждаем через Guard - возвращаем ответ как есть
        return response

    @login_required
    def accept_trade_offer_with_confirmation(self, trade_offer_id: str) -> dict:
        """
        Принятие трейд оффера в веб-интерфейсе с автоматическим подтверждением через Guard
        (старое поведение для обратной совместимости)
        
        Args:
            trade_offer_id: ID трейд оффера
            
        Returns:
            Ответ от Steam API
        """
        response = self.accept_trade_offer(trade_offer_id)
        
        # Если требуется подтверждение через Guard, делаем это
        if response.get('needs_mobile_confirmation', False):
            confirmation_response = self._confirm_transaction(trade_offer_id)
            response.update(confirmation_response)
        
        return response

    def _fetch_trade_partner_id(self, trade_offer_id: str) -> str:
        url = self._get_trade_offer_url(trade_offer_id)
        offer_response_text = self._session.get(url).text

        if 'You have logged in from a new device. In order to protect the items' in offer_response_text:
            raise SevenDaysHoldException("Account has logged in a new device and can't trade for 7 days")

        return text_between(offer_response_text, "var g_ulTradePartnerSteamID = '", "';")

    def _confirm_transaction(self, trade_offer_id: str) -> dict:
        confirmation_executor = ConfirmationExecutor(
            self.steam_guard['identity_secret'], self.steam_id, self._session,
        )
        
        result = confirmation_executor.send_trade_allow_request(trade_offer_id)
        return result

    @login_required
    def confirm_accepted_trade_offer(self, trade_offer_id: str) -> dict:
        """
        Подтверждение уже принятого трейд оффера через Steam Guard
        
        Args:
            trade_offer_id: ID трейд оффера
            
        Returns:
            Ответ от Steam Guard API
        """
        return self._confirm_transaction(trade_offer_id)

    def decline_trade_offer(self, trade_offer_id: str) -> dict:
        url = f'https://steamcommunity.com/tradeoffer/{trade_offer_id}/decline'
        return self._session.post(url, data={'sessionid': self._get_session_id()}).json()

    def cancel_trade_offer(self, trade_offer_id: str) -> dict:
        url = f'https://steamcommunity.com/tradeoffer/{trade_offer_id}/cancel'
        return self._session.post(url, data={'sessionid': self._get_session_id()}).json()

    @login_required
    def make_offer(
        self, items_from_me: list[Asset], items_from_them: list[Asset], partner_steam_id: str, message: str = '',
    ) -> dict:
        offer = self._create_offer_dict(items_from_me, items_from_them)
        session_id = self._get_session_id()
        url = f'{SteamUrl.COMMUNITY_URL}/tradeoffer/new/send'
        server_id = 1
        params = {
            'sessionid': session_id,
            'serverid': server_id,
            'partner': partner_steam_id,
            'tradeoffermessage': message,
            'json_tradeoffer': json.dumps(offer),
            'captcha': '',
            'trade_offer_create_params': '{}',
        }
        partner_account_id = steam_id_to_account_id(partner_steam_id)
        headers = {
            'Referer': f'{SteamUrl.COMMUNITY_URL}/tradeoffer/new/?partner={partner_account_id}',
            'Origin': SteamUrl.COMMUNITY_URL,
        }

        response = self._session.post(url, data=params, headers=headers).json()
        if response.get('needs_mobile_confirmation'):
            response.update(self._confirm_transaction(response['tradeofferid']))

        return response

    def get_profile(self, steam_id: str) -> dict:
        params = {'steamids': steam_id, 'key': self._api_key}
        response = self.api_call('GET', 'ISteamUser', 'GetPlayerSummaries', 'v0002', params)
        data = response.json()
        return data['response']['players'][0]

    def get_friend_list(self, steam_id: str, relationship_filter: str = 'all') -> dict:
        params = {'key': self._api_key, 'steamid': steam_id, 'relationship': relationship_filter}
        resp = self.api_call('GET', 'ISteamUser', 'GetFriendList', 'v1', params)
        data = resp.json()
        return data['friendslist']['friends']

    @staticmethod
    def _create_offer_dict(items_from_me: list[Asset], items_from_them: list[Asset]) -> dict:
        return {
            'newversion': True,
            'version': 4,
            'me': {'assets': [asset.to_dict() for asset in items_from_me], 'currency': [], 'ready': False},
            'them': {'assets': [asset.to_dict() for asset in items_from_them], 'currency': [], 'ready': False},
        }

    @login_required
    def get_escrow_duration(self, trade_offer_url: str) -> int:
        headers = {
            'Referer': f'{SteamUrl.COMMUNITY_URL}{urlparse.urlparse(trade_offer_url).path}',
            'Origin': SteamUrl.COMMUNITY_URL,
        }
        response = self._session.get(trade_offer_url, headers=headers).text

        my_escrow_duration = int(text_between(response, 'var g_daysMyEscrow = ', ';'))
        their_escrow_duration = int(text_between(response, 'var g_daysTheirEscrow = ', ';'))

        return max(my_escrow_duration, their_escrow_duration)

    @login_required
    def make_offer_with_url(
        self,
        items_from_me: list[Asset],
        items_from_them: list[Asset],
        trade_offer_url: str,
        message: str = '',
        case_sensitive: bool = True,
        confirm_trade: bool = True,
    ) -> dict:
        token = get_key_value_from_url(trade_offer_url, 'token', case_sensitive)
        partner_account_id = get_key_value_from_url(trade_offer_url, 'partner', case_sensitive)
        partner_steam_id = account_id_to_steam_id(partner_account_id)
        offer = self._create_offer_dict(items_from_me, items_from_them)
        session_id = self._get_session_id()
        url = f'{SteamUrl.COMMUNITY_URL}/tradeoffer/new/send'
        server_id = 1
        trade_offer_create_params = {'trade_offer_access_token': token}
        params = {
            'sessionid': session_id,
            'serverid': server_id,
            'partner': partner_steam_id,
            'tradeoffermessage': message,
            'json_tradeoffer': json.dumps(offer),
            'captcha': '',
            'trade_offer_create_params': json.dumps(trade_offer_create_params),
        }

        headers = {
            'Referer': f'{SteamUrl.COMMUNITY_URL}{urlparse.urlparse(trade_offer_url).path}',
            'Origin': SteamUrl.COMMUNITY_URL,
        }

        response = self._session.post(url, data=params, headers=headers).json()
        if confirm_trade and response.get('needs_mobile_confirmation'):
            response.update(self._confirm_transaction(response['tradeofferid']))

        return response

    @staticmethod
    def _get_trade_offer_url(trade_offer_id: str) -> str:
        return f'{SteamUrl.COMMUNITY_URL}/tradeoffer/{trade_offer_id}'

    @login_required
    def get_wallet_balance(self, convert_to_decimal: bool = True) -> Union[str, decimal.Decimal]:
        url = SteamUrl.STORE_URL + '/account/history/'
        response = self._session.get(url)
        response_soup = bs4.BeautifulSoup(response.text, "html.parser")
        balance = response_soup.find(id='header_wallet_balance').string
        if convert_to_decimal:
            return parse_price(balance)
        else:
            return balance
    
    @login_required
    def revoke_api_key(self):
        """Revoke old `Steam Web API` key"""

        data = {
            "sessionid": self._get_session_id(),
            "Revoke": "Revoke My Steam Web API Key",  # whatever
        }
        self._session.post("https://steamcommunity.com/dev/revokekey", data=data, allow_redirects=False)
        self._api_key = None

    @login_required
    def get_my_apikey(self) -> str:
        req = self._session.get('https://steamcommunity.com/dev/apikey')
        data_apikey = re.findall(r"([^\\\n.>\\\t</_=:, $(abcdefghijklmnopqrstuvwxyz )&;-]{32})", fr"{req.text}")
        if len(data_apikey) == 1:
            apikey = data_apikey[0]
            self._api_key = apikey
            return apikey
        raise ApiException("Can't get my steam apikey")



    def register_new_api_key(self, domain: str = 'test') -> str:
        """
        Request registration of a new `Steam Web API` key, confirm, cache it and return.

        :param domain: on which domain api key will be registered
        :return: `Steam Web API` key
        :raises EResultError: for ordinary reasons
        """

        # https://github.com/DoctorMcKay/node-steamcommunity/blob/b58745c8b74963eae808d33e558dbba6840c7053/components/webapi.js#L78

        #self.revoke_api_key()  # revoke old one as website do

        data = {
            "domain": domain,
            "request_id": 0,
            "sessionid": self._get_session_id(),
            "agreeToTerms": "true",  # or boolean True?
        }
        r = self._session.post(STEAM_URL.COMMUNITY / "dev/requestkey", data=data)
        rj: dict[str, str | int] = r.json()
        success = EResult(rj.get("success"))

        if success is EResult.PENDING and rj.get("requires_confirmation"):
            confirmation_executor = ConfirmationExecutor(self.steam_guard['identity_secret'], self.steam_id, self._session)
            confirmation_executor.confirm_api_key_request(rj["request_id"])
            data["request_id"] = rj["request_id"]  # меняем на id подтверждения
            r = self._session.post(STEAM_URL.COMMUNITY / "dev/requestkey", data=data)
            rj: dict[str, str | int] = r.json()
            success = EResult(rj.get("success"))

        if success is not EResult.OK or not rj["api_key"]:
            raise EResultError(rj.get("message", "Failed to register Steam Web API Key"), success, rj)

        self._api_key = rj["api_key"]
        return self._api_key

