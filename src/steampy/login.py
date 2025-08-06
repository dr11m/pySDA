from __future__ import annotations

from base64 import b64encode
from http import HTTPStatus
from typing import TYPE_CHECKING, List, Dict, Any
import secrets
from urllib.parse import urlparse
import time
from datetime import datetime
import requests

from rsa import PublicKey, encrypt

from . import guard
from .exceptions import ApiException, CaptchaRequired, InvalidCredentials
from .models import SteamUrl, TransferResult

from src.utils.logger_setup import logger

if TYPE_CHECKING:
    from requests import Response, Session

class LoginExecutor:
    def __init__(self, steam_id: str, username: str, password: str, shared_secret: str, session: Session) -> None:
        self.steam_id = steam_id
        self.username = username
        self.password = password
        self.one_time_code = ''
        self.shared_secret = shared_secret
        self.session = session
        self.refresh_token = ''

    def _api_call(self, method: str, service: str, endpoint: str, version: str = 'v1', params: dict | None = None) -> Response:
        url = f'{SteamUrl.API_URL}/{service}/{endpoint}/{version}'
        # All requests from the login page use the same 'Referer' and 'Origin' values
        headers = {'Referer': f'{SteamUrl.COMMUNITY_URL}/', 'Origin': SteamUrl.COMMUNITY_URL}
        if method.upper() == 'GET':
            return self.session.get(url, params=params, headers=headers)
        elif method.upper() == 'POST':
            return self.session.post(url, data=params, headers=headers)
        else:
            raise ValueError('Method must be either GET or POST')

    def login(self) -> tuple[Session, str]:
        try:
            login_response = self._send_login_request()
            if not login_response.json()['response']:
                raise ApiException('No response received from Steam API. Please try again later.')
            
            self._check_for_captcha(login_response)
            
            self._update_steam_guard(login_response)

            self.get_web_cookies(self.refresh_token, self.steam_id)

            return self.session, self.refresh_token
        
        except Exception as e:
            print(f"❌ Ошибка в login: {e}")
            print(f"📋 Доступные cookies: {list(self.session.cookies.get_dict().keys())}")
            raise

    def _send_login_request(self) -> Response:
        rsa_params = self._fetch_rsa_params()
        encrypted_password = self._encrypt_password(rsa_params)
        rsa_timestamp = rsa_params['rsa_timestamp']
        request_data = self._prepare_login_request_data(encrypted_password, rsa_timestamp)
        return self._api_call('POST', 'IAuthenticationService', 'BeginAuthSessionViaCredentials', params=request_data)


    def _fetch_rsa_params(self, current_number_of_repetitions: int = 0) -> dict:
        self.session.post(SteamUrl.COMMUNITY_URL)
        request_data = {'account_name': self.username}
        response = self._api_call('GET', 'IAuthenticationService', 'GetPasswordRSAPublicKey', params=request_data)

        if response.status_code == HTTPStatus.OK and 'response' in response.json():
            key_data = response.json()['response']
            # Steam may return an empty 'response' value even if the status is 200
            if 'publickey_mod' in key_data and 'publickey_exp' in key_data and 'timestamp' in key_data:
                rsa_mod = int(key_data['publickey_mod'], 16)
                rsa_exp = int(key_data['publickey_exp'], 16)
                return {'rsa_key': PublicKey(rsa_mod, rsa_exp), 'rsa_timestamp': key_data['timestamp']}

        maximal_number_of_repetitions = 5
        if current_number_of_repetitions < maximal_number_of_repetitions:
            return self._fetch_rsa_params(current_number_of_repetitions + 1)

        raise ApiException(f'Could not obtain rsa-key. Status code: {response.status_code}')

    def _encrypt_password(self, rsa_params: dict) -> bytes:
        return b64encode(encrypt(self.password.encode('utf-8'), rsa_params['rsa_key']))

    def _prepare_login_request_data(self, encrypted_password: bytes, rsa_timestamp: str) -> dict:
        return {
            'persistence': '1',
            'encrypted_password': encrypted_password,
            'account_name': self.username,
            'encryption_timestamp': rsa_timestamp,
        }

    @staticmethod
    def _check_for_captcha(login_response: Response) -> None:
        if login_response.json().get('captcha_needed', False):
            raise CaptchaRequired('Captcha required')

    def _enter_steam_guard_if_necessary(self, login_response: Response) -> Response:
        if login_response.json()['requires_twofactor']:
            self.one_time_code = guard.generate_one_time_code(self.shared_secret)
            return self._send_login_request()
        return login_response

    @staticmethod
    def _assert_valid_credentials(login_response: Response) -> None:
        if not login_response.json()['success']:
            raise InvalidCredentials(login_response.json()['message'])

    def _update_steam_guard(self, login_response: Response) -> None:
        try:
            client_id = login_response.json()['response']['client_id']
            steamid = login_response.json()['response']['steamid']
            request_id = login_response.json()['response']['request_id']
            code_type = 3
            code = guard.generate_one_time_code(self.shared_secret)

            update_data = {'client_id': client_id, 'steamid': steamid, 'code_type': code_type, 'code': code}
            response = self._api_call(
                'POST', 'IAuthenticationService', 'UpdateAuthSessionWithSteamGuardCode', params=update_data,
            )
            if response.status_code == HTTPStatus.OK:
                self._pool_sessions_steam(client_id, request_id)
            else:
                raise Exception('Cannot update Steam guard')
        except Exception as e:
            print(f"❌ Ошибка в _update_steam_guard: {e}")
            raise

    def _pool_sessions_steam(self, client_id: str, request_id: str) -> None:
        try:
            pool_data = {'client_id': client_id, 'request_id': request_id}
            response = self._api_call('POST', 'IAuthenticationService', 'PollAuthSessionStatus', params=pool_data)
            self.refresh_token = response.json()['response']['refresh_token']
        except Exception as e:
            print(f"❌ Ошибка в _pool_sessions_steam: {e}")
            raise

    def get_web_cookies(self, refresh_token: str, steam_id: str) -> List[str]:
        """
        Получение web cookies для Steam сайтов.
        
        Точный аналог getWebCookies() из node-steam-session.
        Оригинальный код: https://github.com/DoctorMcKay/node-steam-session/blob/master/src/LoginSession.ts#L1050-L1150
        
        Выполняет полный цикл аутентификации для получения cookies всех Steam доменов:
        1. Генерирует уникальный session_id (12 байт hex)
        2. Делает запрос к /jwt/finalizelogin для получения transfer_info
        3. Извлекает первичные cookies из ответа finalizelogin  
        4. Обрабатывает все transfer_info URLs для получения domain-specific cookies
        5. Фильтрует и добавляет sessionid cookies для всех доменов
        
        Args:
            refresh_token (str): JWT refresh token для аутентификации в Steam
            steam_id (str): Steam ID пользователя (извлекается из токена)
            
        Returns:
            List[str]: Список cookie-строк в формате "name=value; Domain=domain; Path=/; Secure"
                    Включает steamLoginSecure и sessionid для всех Steam доменов
                    
        Raises:
            Exception: При ошибках HTTP запросов, невалидных ответах Steam или отсутствии cookies
            
        Note:
            Метод работает только с WebBrowser платформой. Для MobileApp/SteamClient 
            используется другая логика через access_token.
        """
        
        # Генерируем sessionId как в оригинале (randomBytes(12).toString('hex'))
        session_id = secrets.token_hex(12)

        # Для WebBrowser платформы - делаем запросы как в оригинале
        finalize_response, json_body = self._make_finalize_request(session_id, refresh_token)
        cookies = self._extract_initial_cookies(finalize_response)
        cookies = self._process_transfer_info(steam_id, json_body, cookies)

        # Заменяем sessionid для каждого домена на сгенерированный.
        self._filter_and_add_session_cookies(session_id)
        
        print(f"✅ Returning {len(cookies)} cookies")
        return cookies

    def _make_finalize_request(self, session_id: str, refresh_token: str) -> tuple:
        """Делает запрос к jwt/finalizelogin"""
        body = {
            'nonce': refresh_token,
            'sessionid': session_id,
            'redir': 'https://steamcommunity.com/login/home/?goto='
        }

        headers = {
            'Origin': 'https://steamcommunity.com',
            'Referer': 'https://steamcommunity.com/',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        finalize_response = self.session.post(
            'https://login.steampowered.com/jwt/finalizelogin',
            data=body,
            headers=headers
        )

        if finalize_response.status_code != 200:
            raise Exception(f'HTTP error {finalize_response.status_code}')

        try:
            json_body = finalize_response.json()
        except:
            raise Exception('Invalid JSON response from finalizelogin')

        if json_body.get('error'):
            raise Exception(f'Steam error: {json_body["error"]}')

        if not json_body.get('transfer_info'):
            raise Exception('Malformed login response - no transfer_info')

        return finalize_response, json_body

    def _extract_initial_cookies(self, finalize_response) -> List[str]:
        """Извлекает cookies из finalize response - ТОЧНО КАК В ОРИГИНАЛЕ"""
        domain = urlparse(finalize_response.url).netloc
        cookies: List[str] = []
        
        set_cookie_headers = finalize_response.headers.get('set-cookie', '')
        if set_cookie_headers:
            for cookie in set_cookie_headers.split(','):
                cookie = cookie.strip()
                if not cookie.lower().find('domain=') >= 0:
                    cookie += f'; Domain={domain}'
                cookies.append(cookie)
        
        return cookies

    def _process_transfer_info(self, steam_id: str, json_body: Dict[str, Any], cookies: List[str]) -> List[str]:
        """Обрабатывает все transfer_info URLs"""
        for transfer in json_body['transfer_info']:
            cookies = self._process_single_transfer(transfer, steam_id, cookies)
        
        return cookies

    def _process_single_transfer(self, transfer: Dict[str, Any], steam_id: str, cookies: List[str]) -> List[str]:
        """Обрабатывает один transfer URL"""
        url = transfer['url']
        params = transfer.get('params', {})
        
        # Добавляем steamID как в оригинале
        transfer_body = {'steamID': steam_id, **params}
        
        # Повторяем до 5 раз как в оригинале
        ATTEMPT_COUNT = 5
        for attempt in range(ATTEMPT_COUNT):
            try:
                result = self.session.post(url, data=transfer_body)
                
                if result.status_code >= 400:
                    raise Exception(f'HTTP error {result.status_code}')

                json_result = result.json()
                logger.info(f"🔍 JSON result: {json_result}")
                if json_result.get('result') and json_result['result'] != TransferResult.OK:
                    raise Exception(f'Steam error result: {json_result["result"]}')
                    # Проверяем срок действия refresh токена
                if 'rtExpiry' in json_result:
                    expiry_timestamp = json_result['rtExpiry']
                    current_timestamp = int(time.time())
                    
                    if expiry_timestamp <= current_timestamp:
                        logger.warning(f"⚠️ Refresh токен истек: {expiry_timestamp}")
                        #TODO обновить refresh токен
                        raise Exception('Refresh token expired')
                    else:
                        # Логируем когда истечет токен
                        expiry_date = datetime.fromtimestamp(expiry_timestamp)
                        logger.info(f"🕒 Refresh токен действителен до: {expiry_date}")

                # Проверяем наличие Set-Cookie заголовков
                set_cookie = result.headers.get('set-cookie', '')
                if not set_cookie:
                    raise Exception('No Set-Cookie header in result')

                if not any('steamLoginSecure=' in c for c in set_cookie.split(',')):
                    raise Exception('No steamLoginSecure cookie in result')

                # Добавляем cookies с правильным доменом
                result_domain = urlparse(result.url).netloc
                for cookie in set_cookie.split(','):
                    cookie = cookie.strip()
                    if not 'domain=' in cookie.lower():
                        cookie += f'; Domain={result_domain}'
                    cookies.append(cookie)

                print(f"✅ Successfully got cookies from {url}")
                break  # Успех - выходим из цикла повторов
                
            except Exception as ex:
                if attempt == ATTEMPT_COUNT - 1:
                    print(f"[ERROR] All {ATTEMPT_COUNT} attempts failed for {url}: {ex}")
                    raise ex
                
                print(f"[DEBUG] Attempt {attempt + 1}/{ATTEMPT_COUNT} failed for {url}: {ex}")

        return cookies

    def _filter_and_add_session_cookies(self, session_id: str) -> None:
        """
        Заменяет sessionid для каждого домена на сгенерированный.
        """
        
        # 1. Собираем все домены и существующие sessionid cookies
        domains = set()
        sessionid_cookies_to_remove = []
        
        for cookie in self.session.cookies:
            if cookie.domain and cookie.domain != 'login.steampowered.com':
                domains.add(cookie.domain)
                
                # Если это sessionid cookie - запоминаем для удаления
                if cookie.name == 'sessionid':
                    sessionid_cookies_to_remove.append((cookie.domain, cookie.path))
        
        print(f"🔍 Домены для обновления sessionid: {domains}")
        
        # 2. Удаляем все существующие sessionid cookies
        for domain, path in sessionid_cookies_to_remove:
            try:
                self.session.cookies.clear(domain=domain, path=path, name='sessionid')
                print(f"🗑️ Удален старый sessionid для {domain} (path={path})")
            except Exception as e:
                print(f"⚠️ Не удалось удалить sessionid для {domain}: {e}")
        
        # 3. Добавляем новый sessionid для каждого домена
        for domain in domains:
            self.session.cookies.set(
                'sessionid', 
                session_id,
                domain=domain,
                path='/',
                secure=True
            )
            print(f"✅ Добавлен новый sessionid для {domain}")
        
        print(f"🎯 Обновлено {len(domains)} доменов с sessionid={session_id[:8]}...")


