#  основан на https://github.com/sometastycake/steam-password-change/blob/master/steampassword/chpassword.py
#!/usr/bin/env python3
"""
Менеджер паролей для CLI интерфейса
"""
import base64
import time
import urllib.parse
import json
import re
from typing import Optional, Dict, Any, Union
from .constants import Messages
from .display_formatter import DisplayFormatter
from src.utils.logger_setup import print_and_log
from src.utils.cookies_and_session import session_to_dict, extract_cookies_for_domain
from src.cli.account_context import AccountContext
from src.steampy.client import SteamClient
from src.steampy.confirmation import ConfirmationExecutor


class PasswordManager:
    """
    Менеджер для работы с паролями Steam аккаунтов
    основан на https://github.com/sometastycake/steam-password-change/blob/master/steampassword/chpassword.py
    """
    
    def __init__(self) -> None:
        self.formatter: DisplayFormatter = DisplayFormatter()
    
    def change_password(self, account_context: AccountContext) -> bool:
        """
        Смена пароля Steam аккаунта
        
        Args:
            account_context: Контекст аккаунта
            
        Returns:
            bool: True если пароль успешно изменен
        """
        try:
            print_and_log(self.formatter.format_section_header("🔒 Смена пароля"))
            print_and_log("⚠️  ВНИМАНИЕ: Смена пароля может затронуть работу бота!")
            print_and_log("💡 Убедитесь, что у вас есть доступ к мобильному приложению Steam Guard")
            print_and_log("")
            
            # Создаем экземпляр PasswordChanger
            password_changer: PasswordChanger = PasswordChanger(account_context)
            
            # Запускаем процесс смены пароля
            return password_changer.execute()
            
        except Exception as e:
            print_and_log(f"❌ Ошибка смены пароля: {e}", "ERROR")
            input("Нажмите Enter для продолжения...")
            return False
    
    def validate_password_strength(self, password: str) -> Dict[str, Union[bool, int, list]]:
        """
        Проверка надежности пароля
        
        Args:
            password: Пароль для проверки
            
        Returns:
            Dict с результатами проверки
        """
        result: Dict[str, Union[bool, int, list]] = {
            'is_valid': True,
            'score': 0,
            'issues': []
        }
        
        # Минимальная длина
        if len(password) < 8:
            result['issues'].append("Пароль должен содержать минимум 8 символов")
            result['is_valid'] = False
        
        # Проверка наличия букв
        if not any(c.isalpha() for c in password):
            result['issues'].append("Пароль должен содержать буквы")
            result['is_valid'] = False
        
        # Проверка наличия цифр
        if not any(c.isdigit() for c in password):
            result['issues'].append("Пароль должен содержать цифры")
            result['is_valid'] = False
        
        # Подсчет очков надежности
        if len(password) >= 12:
            result['score'] += 2
        elif len(password) >= 8:
            result['score'] += 1
            
        if any(c.isupper() for c in password):
            result['score'] += 1
            
        if any(c.islower() for c in password):
            result['score'] += 1
            
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            result['score'] += 2
            
        return result


class PasswordChanger:
    """
    Класс для смены пароля Steam аккаунта
    Основан на https://github.com/sometastycake/steam-password-change
    """
    
    BROWSER = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
        '537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    )
    
    def __init__(self, account_context: AccountContext) -> None:
        """
        Инициализация с контекстом аккаунта
        
        Args:
            account_context: Контекст аккаунта с настроенными прокси и сессией
        """
        self.account_context: AccountContext = account_context
        self.formatter: DisplayFormatter = DisplayFormatter()
        self.username: str = account_context.account_name
        self.steam_client: Optional[SteamClient] = None
        
        # Параметры для восстановления (эквивалент PasswordChangeParams)
        self.recovery_params: Dict[str, str] = {}
        
    def execute(self) -> bool:
        """
        Выполнение процесса смены пароля
        
        Returns:
            bool: True если пароль успешно изменен
        """
        try:
            print_and_log(f"🔒 Начинаем смену пароля для аккаунта: {self.username}")
            print_and_log("")
            
            # Получаем Steam клиент
            self.steam_client = self.account_context.cookie_manager.get_steam_client()
            if not self.steam_client:
                print_and_log("❌ Не удалось получить Steam клиент", "ERROR")
                return False
            
            # Шаг 1: Проверка активности сессии
            if not self._verify_current_password(""):
                print_and_log("❌ Сессия неактивна, необходимо войти в аккаунт", "ERROR")
                return False
            
            # Шаг 1.5: Проверка наличия Steam Guard данных
            if not self._verify_steam_guard_data():
                print_and_log("❌ Отсутствуют данные Steam Guard", "ERROR")
                return False
            
            # Шаг 2: Получение нового пароля
            new_password: Optional[str] = self._get_new_password()
            if not new_password:
                return False
            
            # Шаг 3: Подтверждение смены
            if not self._confirm_password_change():
                return False
            
            # Шаг 4: Полный процесс смены пароля (как в оригинальном репозитории)
            if self._change_password_full_process(new_password):
                # Обновление конфигурации
                if self._update_configuration(new_password):
                    print_and_log("✅ Пароль успешно изменен и сохранен в конфигурации!")
                    print_and_log("💡 Не забудьте сохранить новый пароль в config.yaml!")
                    return True
                else:
                    print_and_log("❌ Ошибка при сохранении пароля в конфигурации!")
                    return False
            else:
                print_and_log("❌ Не удалось изменить пароль")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка в процессе смены пароля: {e}", "ERROR")
            return False
    
    def _change_password_full_process(self, new_password: str) -> bool:
        """
        Полный процесс смены пароля на основе оригинального репозитория
        """
        try:
            print_and_log("🔄 Начинаем полный процесс смены пароля...")
            
            # Получаем Steam ID из конфигурации
            account_config = self.account_context.config_manager.accounts_settings.get(self.username, {})
            steam_id = account_config.get('steam_id', '')
            if not steam_id:
                print_and_log("❌ Не удалось получить steam_id из конфигурации")
                return False
            
            # Шаг 1: Получение параметров смены пароля (аналог _receive_password_change_params)
            print_and_log("🔄 Получение параметров смены пароля...")
            if not self._initialize_recovery(steam_id):
                return False
            
            # Шаг 2: Переход к вводу кода (аналог HelpWithLoginInfoEnterCode)
            print_and_log("🔄 Переход к вводу кода...")
            if not self._goto_enter_code():
                return False
            
            # Шаг 3: Отправка запроса на восстановление (аналог AjaxSendAccountRecoveryCode)
            print_and_log("🔄 Отправка запроса на восстановление...")
            if not self._send_recovery_request():
                return False
            
            # Шаг 4: Поллинг подтверждения (аналог AjaxPollAccountRecoveryConfirmation)
            print_and_log("📱 Ожидание подтверждения в мобильном приложении...")
            if not self._poll_confirmation():
                return False
            
            # Шаг 5: Верификация кода восстановления (аналог AjaxVerifyAccountRecoveryCode)
            print_and_log("🔄 Верификация кода восстановления...")
            if not self._verify_recovery_code():
                return False
            
            # Шаг 6: Получение следующего шага (аналог AjaxAccountRecoveryGetNextStep)
            print_and_log("🔄 Получение следующего шага...")
            if not self._get_next_step():
                return False
            
            # Шаг 7: Верификация старого пароля (аналог AjaxAccountRecoveryVerifyPassword)
            print_and_log("🔄 Верификация старого пароля...")
            if not self._verify_old_password():
                return False
            
            # Шаг 8: Установка нового пароля (аналог AjaxAccountRecoveryChangePassword)
            print_and_log("🔐 Установка нового пароля...")
            if not self._set_new_password(new_password):
                return False
            
            print_and_log("✅ Пароль успешно изменен!")
            return True
            
        except Exception as e:
            print_and_log(f"❌ Ошибка в процессе смены пароля: {e}", "ERROR")
            return False
    
    def _check_help_authorization_detailed(self) -> bool:
        """Детальная проверка авторизации на help.steampowered.com"""
        try:
            print_and_log("🔍 Детальная проверка авторизации на help.steampowered.com...")
            
            # Проверяем cookies для help домена
            help_cookies = {}
            for cookie in self.steam_client._session.cookies:
                if 'help.steampowered.com' in cookie.domain or cookie.domain == '.steampowered.com':
                    help_cookies[cookie.name] = cookie.value
            
            print_and_log(f"🔍 Cookies для help домена: {list(help_cookies.keys())}")
            
            important_cookies = ['steamLoginSecure', 'sessionid']
            for cookie_name in important_cookies:
                if cookie_name in help_cookies:
                    value = help_cookies[cookie_name]
                    print_and_log(f"✅ {cookie_name}: {value[:20]}..." if len(value) > 20 else f"✅ {cookie_name}: {value}")
                else:
                    print_and_log(f"❌ {cookie_name}: НЕ НАЙДЕН для help домена")
            
             # Тестируем доступ к защищенной странице help
            test_urls = [
                 "https://help.steampowered.com/en",
                 "https://help.steampowered.com/wizard/",
                 "https://help.steampowered.com/wizard/HelpChangePassword"
             ]
            
            for test_url in test_urls:
                print_and_log(f"🔍 Тестируем: {test_url}")
                response = self.steam_client._session.get(test_url, allow_redirects=False)
                print_and_log(f"  Статус: {response.status_code}")

                # ГЛАВНАЯ ВАЛИДАЦИЯ: проверяем наличие ника в тексте ответа
                if self.account_context.account_name.lower() in response.text.lower():
                    print_and_log(f"✅ {self.account_context.account_name} найден в тексте - АВТОРИЗОВАН")
                else:
                    print_and_log(f"❌ {self.account_context.account_name} не найден в тексте - НЕ АВТОРИЗОВАН")

                if response.status_code == 302:
                    location = response.headers.get('Location', 'Не указано')
                    print_and_log(f"  Редирект на: {location}")
                    if '/login' in location:
                        print_and_log(f"  ❌ Требуется авторизация для {test_url}")

                elif response.status_code == 200:
                    print_and_log(f"  ✅ Доступ к {test_url} разрешен")
                else:
                    print_and_log(f"  ⚠️  Неожиданный статус для {test_url}")
            
            # Проверяем, можем ли мы получить страницу смены пароля без редиректа
            response = self.steam_client._session.get(
                "https://help.steampowered.com/wizard/HelpChangePassword",
                allow_redirects=True
            )
            
            print_and_log(f"🔍 Финальная проверка HelpChangePassword:")
            print_and_log(f"  Статус: {response.status_code}")
            print_and_log(f"  URL: {response.url}")
            
            # ГЛАВНАЯ ВАЛИДАЦИЯ для финальной проверки
            if self.account_context.account_name.lower() in response.text.lower():
                print_and_log(f"✅ {self.account_context.account_name} найден в финальном ответе - АВТОРИЗОВАН")
                return True
            else:
                print_and_log(f"❌ {self.account_context.account_name} НЕ найден в финальном ответе - НЕ АВТОРИЗОВАН")
                return False

                1
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки авторизации: {e}", "ERROR")
            return False

    def _fix_help_authorization(self) -> bool:
        """Исправление авторизации для help.steampowered.com"""
        try:
            print_and_log("🔧 Попытка исправить авторизацию на help.steampowered.com...")
            
            # Сначала убедимся, что мы авторизованы на store.steampowered.com
            print_and_log("🔍 Проверяем авторизацию на store.steampowered.com...")
            store_response = self.steam_client._session.get(
                "https://store.steampowered.com/account/",
                allow_redirects=False
            )
            
            if store_response.status_code == 302 and '/login' in store_response.headers.get('Location', ''):
                print_and_log("❌ Не авторизованы на store.steampowered.com")
                return False
            
            if self.account_context.account_name.lower() in store_response.text.lower():
                print_and_log(f"✅ {self.account_context.account_name} найден в тексте - АВТОРИЗОВАН")
            else:
                print_and_log(f"❌ {self.account_context.account_name} НЕ найден в тексте - НЕ АВТОРИЗОВАН")
                return False
            
            print_and_log("✅ Авторизованы на store.steampowered.com")
            
            # Извлекаем куки с домена steamcommunity.com
            print_and_log("🔍 Извлекаем куки с домена steamcommunity.com...")
            cookies_dict = session_to_dict(self.steam_client._session)
            steamcommunity_cookies = extract_cookies_for_domain(cookies_dict['cookies'], 'steamcommunity.com')
            
            print_and_log(f"🔍 Найдено {len(steamcommunity_cookies)} куки для store.steampowered.com")
            if steamcommunity_cookies:
                print_and_log(f"🔍 Куки: {list(steamcommunity_cookies.keys())}")
            
            # Теперь попробуем получить доступ к help через правильный редирект с куки
            print_and_log("🔍 Попытка доступа к help через правильный редирект с куки...")
            
            # Используем URL, который должен перенаправить нас на help с правильной авторизацией
            redirect_url = "https://help.steampowered.com/wizard/HelpChangePassword?redir=store/account/"
            redirect_response = self.steam_client._session.get(
                redirect_url,
                allow_redirects=True,
                cookies=steamcommunity_cookies
            )
            
            print_and_log(f"🔍 Редирект статус: {redirect_response.status_code}")
            print_and_log(f"🔍 Финальный URL: {redirect_response.url}")
            
            # Если редирект привел нас на help домен, проверяем авторизацию
            if 'help.steampowered.com' in redirect_response.url:
                print_and_log("✅ Успешно перенаправлены на help.steampowered.com")
                
                # ГЛАВНАЯ ВАЛИДАЦИЯ: проверяем наличие ника в тексте ответа
                if self.account_context.account_name.lower() in redirect_response.text.lower():
                    print_and_log(f"✅ {self.account_context.account_name} найден в тексте - АВТОРИЗОВАН")
                    return True
                else:
                    print_and_log(f"❌ {self.account_context.account_name} НЕ найден в тексте - НЕ АВТОРИЗОВАН")
                    return False
            else:
                print_and_log("❌ Не удалось получить доступ к help домену")
                return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка исправления авторизации: {e}", "ERROR")
            return False
    
    def _initialize_recovery(self, steam_id: str) -> bool:
        """
        Инициализация процесса восстановления с исправлением авторизации
        Аналог _receive_password_change_params из оригинального кода
        """
        try:
            print_and_log(f"🔍 Начинаем инициализацию для Steam ID: {steam_id}")
                        
            # Извлекаем куки с домена steamcommunity.com для запроса
            print_and_log("🔍 Извлекаем куки с домена steamcommunity.com для запроса...")
            cookies_dict = session_to_dict(self.steam_client._session)
            steamcommunity_cookies = extract_cookies_for_domain(cookies_dict['cookies'], 'steamcommunity.com')
            
            print_and_log(f"🔍 Найдено {len(steamcommunity_cookies)} куки для steamcommunity.com")
            if steamcommunity_cookies:
                print_and_log(f"🔍 Куки: {list(steamcommunity_cookies.keys())}")
            
    
            print_and_log("🔍 Отправляем запрос с куки от steamcommunity.com...")
            
            cookies = {
                'steamCountry': steamcommunity_cookies['steamCountry'],
                'sessionid': steamcommunity_cookies['sessionid'],
                #'cookieSettings': '%7B%22version%22%3A1%2C%22preference_state%22%3A1%2C%22content_customization%22%3Anull%2C%22valve_analytics%22%3Anull%2C%22third_party_analytics%22%3Anull%2C%22third_party_content%22%3Anull%2C%22utm_enabled%22%3Atrue%7D',
                #'timezoneOffset': '10800,0',
                'steamLoginSecure': steamcommunity_cookies['steamLoginSecure'],
                #'steamAccountRecoveryRedir': 'https%3A%2F%2Fstore.steampowered.com%2Faccount%2F',
            }

            headers = {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Connection': 'keep-alive',
                    'Referer': 'https://store.steampowered.com/',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-site',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
                    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
            }
            
            response = self.steam_client._session.get(
                "https://help.steampowered.com/wizard/HelpChangePassword?redir=store/account/",
                cookies=cookies,
                headers=headers,
                allow_redirects=True
            )
            
            print_and_log(f"🔍 Статус ответа: {response.status_code}")
            print_and_log(f"🔍 URL ответа: {response.url}")
            print_and_log(f"🔍 История редиректов: {len(response.history)} редиректов")
            
            # Проверяем, не перенаправило ли снова на логин
            if '/login' in response.url:
                print_and_log("❌ Steam снова перенаправил на страницу входа")
                print_and_log("💡 Возможные причины:")
                print_and_log("  • Сессия истекла")
                print_and_log("  • Нет авторизации для операций восстановления")
                print_and_log("  • Требуется повторный вход в аккаунт")
                return False
            
            # Проверяем редиректы (как в оригинальном коде)
            if response.history:
                print_and_log("✅ Обнаружен редирект, извлекаем параметры из URL...")
                
                final_url = response.url
                parsed_url = urllib.parse.urlparse(final_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                
                print_and_log(f"🔍 Финальный URL: {final_url}")
                print_and_log(f"🔍 Query параметры: {query_params}")
                
                # Извлекаем параметры по образцу PasswordChangeParams
                try:
                    self.recovery_params = {
                        's': query_params.get('s', [None])[0],
                        'account': query_params.get('account', [None])[0],
                        'reset': query_params.get('reset', [None])[0],
                        'issueid': query_params.get('issueid', [None])[0],
                        'lost': query_params.get('lost', ['0'])[0]
                    }
                    
                    print_and_log(f"🔍 Извлеченные параметры: {self.recovery_params}")
                    
                    # Проверяем, что все обязательные параметры есть
                    if all(v is not None for k, v in self.recovery_params.items() if k != 'lost'):
                        session_id = self.recovery_params['s']
                        print_and_log(f"✅ Процесс восстановления инициализирован. Session ID: {session_id}")
                        return True
                    else:
                        print_and_log("❌ Не все обязательные параметры найдены в редиректе")
                        return False
                        
                except Exception as e:
                    print_and_log(f"❌ Ошибка извлечения параметров из редиректа: {e}")
                    return False
            
            # Если редиректа не было, проверяем HTML на ошибки (как в оригинальном коде)
            html_content = response.text
            print_and_log("🔍 Редиректа не было, анализируем HTML...")
            
            # Ищем ошибки в HTML (аналог page.cssselect('#error_description'))
            error_patterns = [
                r'<div[^>]*id=["\']error_description["\'][^>]*>([^<]+)</div>',
                r'<div[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)</div>',
            ]
            
            for pattern in error_patterns:
                error_match = re.search(pattern, html_content, re.IGNORECASE)
                if error_match:
                    error_text = error_match.group(1).strip()
                    print_and_log(f"❌ Найдена ошибка Steam: {error_text}")
                    return False
            
            print_and_log("❌ Не удалось получить параметры смены пароля")
            print_and_log(f"🔍 Первые 500 символов HTML: {html_content[:500]}")
            return False
            
        except Exception as e:
            print_and_log(f"❌ Исключение в _initialize_recovery: {type(e).__name__}: {str(e)}", "ERROR")
            import traceback
            print_and_log(f"🔍 Трассировка: {traceback.format_exc()}", "ERROR")
            return False
    
    def _goto_enter_code(self) -> bool:
        """Переход к странице ввода кода с использованием извлеченных параметров"""
        try:
            print_and_log("🔍 Переход к странице ввода кода...")
            
            # Используем все параметры, полученные при инициализации
            url = "https://help.steampowered.com/en/wizard/HelpWithLoginInfoEnterCode"
            params = {
                's': self.recovery_params['s'],
                'account': self.recovery_params['account'],
                'reset': self.recovery_params['reset'],
                'lost': self.recovery_params['lost'],
                'issueid': self.recovery_params['issueid'],
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                'gamepad': '0'
            }
            
            print_and_log(f"🔍 URL: {url}")
            print_and_log(f"🔍 Параметры: {params}")
            
            headers = {
                'Accept': '*/*',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Connection': 'keep-alive',
                'Referer': f"https://help.steampowered.com/en/wizard/HelpWithLoginInfoEnterCode?s={self.recovery_params['s']}&account={self.recovery_params['account']}&reset={self.recovery_params['reset']}&lost={self.recovery_params['lost']}&issueid={self.recovery_params['issueid']}",
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': self.BROWSER,
                'X-Requested-With': 'XMLHttpRequest',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            }
            
            response = self.steam_client._session.get(url, params=params, headers=headers)
            
            print_and_log(f"🔍 Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                print_and_log(f"🔍 Длина содержимого: {len(content)}")
                print_and_log(f"🔍 Первые 300 символов: {content[:300]}")
                
                if "error" in content.lower() or "ошибка" in content.lower():
                    print_and_log("❌ Обнаружена ошибка в ответе")
                    return False
                
                print_and_log("✅ Переход к вводу кода выполнен успешно")
                return True
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка перехода к вводу кода: {e}", "ERROR")
            return False
    
    def _send_recovery_request(self) -> bool:
        """Отправка запроса на восстановление"""
        try:
            url = "https://help.steampowered.com/en/wizard/AjaxSendAccountRecoveryCode"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                'gamepad': '0',
                's': self.recovery_params['s'],
                'method': '8',  # Мобильное подтверждение
                'link': '',
                'n': '1'
            }
            
            headers = {
                'Accept': '*/*',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Connection': 'keep-alive',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://help.steampowered.com',
                'Referer': f"https://help.steampowered.com/en/wizard/HelpWithLoginInfoEnterCode?s={self.recovery_params['s']}&account={self.recovery_params['account']}&reset={self.recovery_params['reset']}&lost={self.recovery_params['lost']}&issueid={self.recovery_params['issueid']}",
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': self.BROWSER,
                'X-Requested-With': 'XMLHttpRequest',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            }
            
            response = self.steam_client._session.post(url, data=data, headers=headers)
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get('success'):
                        print_and_log("✅ Запрос на восстановление отправлен")
                        return True
                    else:
                        print_and_log(f"❌ Ошибка отправки запроса: {result.get('errorMsg', 'Unknown error')}")
                        return False
                except:
                    print_and_log("✅ Запрос отправлен (ответ не в JSON)")
                    return True
            
            print_and_log(f"❌ HTTP ошибка: {response.status_code}")
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка отправки запроса: {e}", "ERROR")
            return False
    
    def _poll_confirmation(self) -> bool:
        """Поллинг подтверждения"""
        try:
            url = "https://help.steampowered.com/en/wizard/AjaxPollAccountRecoveryConfirmation"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                'gamepad': '0',
                's': self.recovery_params['s'],
                'reset': self.recovery_params['reset'],
                'lost': self.recovery_params['lost'],
                'method': '8',
                'issueid': self.recovery_params['issueid']
            }
            
            headers = {
                'Accept': '*/*',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                'Connection': 'keep-alive',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://help.steampowered.com',
                'Referer': f"https://help.steampowered.com/en/wizard/HelpWithLoginInfoEnterCode?s={self.recovery_params['s']}&account={self.recovery_params['account']}&reset={self.recovery_params['reset']}&lost={self.recovery_params['lost']}&issueid={self.recovery_params['issueid']}",
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': self.BROWSER,
                'X-Requested-With': 'XMLHttpRequest',
                'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            }
            
            max_attempts = 60  # 60 попыток * 3 секунды = 3 минуты
            for attempt in range(max_attempts):
                print_and_log(f"⏳ Попытка {attempt + 1}/{max_attempts}")
                
                response = self.steam_client._session.post(url, data=data, headers=headers)
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        if not result.get('errorMsg'):
                            print_and_log("✅ Подтверждение получено!")
                            return True
                        elif 'ожидание' in result.get('errorMsg', '').lower():
                            time.sleep(3)
                            continue
                        else:
                            print_and_log(f"❌ Ошибка подтверждения: {result.get('errorMsg')}")
                            return False
                    except:
                        print_and_log("✅ Получен ответ (проверяем как успех)")
                        return True
                
                time.sleep(3)
            
            print_and_log("❌ Подтверждение не получено в течение 3 минут")
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка поллинга: {e}", "ERROR")
            return False
    
    def _verify_recovery_code(self) -> bool:
        """Верификация кода восстановления"""
        try:
            url = "https://help.steampowered.com/en/wizard/AjaxVerifyAccountRecoveryCode"
            params = {
                'code': '',
                's': self.recovery_params['s'],
                'reset': self.recovery_params['reset'],
                'lost': self.recovery_params['lost'],
                'method': '8',
                'issueid': self.recovery_params['issueid'],
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                'gamepad': '0'
            }
            
            response = self.steam_client._session.get(url, params=params)
            if response.status_code == 200:
                try:
                    result = response.json()
                    return not result.get('errorMsg')
                except:
                    return True
            
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка верификации кода: {e}", "ERROR")
            return False
    
    def _get_next_step(self) -> bool:
        """Получение следующего шага"""
        try:
            url = "https://help.steampowered.com/en/wizard/AjaxAccountRecoveryGetNextStep"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                's': self.recovery_params['s'],
                'account': self.recovery_params['account'],
                'reset': self.recovery_params['reset'],
                'issueid': self.recovery_params['issueid'],
                'lost': '2'  # Переключаем на lost=2 для следующих шагов
            }
            
            response = self.steam_client._session.post(url, data=data)
            if response.status_code == 200:
                try:
                    result = response.json()
                    return not result.get('errorMsg')
                except:
                    return True
            
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка получения шага: {e}", "ERROR")
            return False
    
    def _verify_old_password(self) -> bool:
        """Верификация старого пароля"""
        try:
            # Получаем текущий пароль
            account_config = self.account_context.config_manager.accounts_settings.get(self.username, {})
            current_password = account_config.get('password', '')
            if not current_password:
                print_and_log("❌ Не удалось получить текущий пароль")
                return False
            
            # Получаем RSA ключ для шифрования
            rsa_key = self._get_rsa_key()
            if not rsa_key:
                return False
            
            # Шифруем пароль
            encrypted_password = self._encrypt_password(current_password, rsa_key)
            if not encrypted_password:
                return False
            
            url = "https://help.steampowered.com/en/wizard/AjaxAccountRecoveryVerifyPassword/"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                's': self.recovery_params['s'],
                'lost': '2',
                'reset': '1',
                'password': encrypted_password,
                'rsatimestamp': rsa_key['timestamp']
            }
            
            response = self.steam_client._session.post(url, data=data)
            if response.status_code == 200:
                try:
                    result = response.json()
                    return not result.get('errorMsg')
                except:
                    return True
            
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка верификации пароля: {e}", "ERROR")
            return False
    
    def _set_new_password(self, new_password: str) -> bool:
        """Установка нового пароля"""
        try:
            # Проверяем доступность пароля
            if not self._check_password_available(new_password):
                return False
            
            # Получаем RSA ключ
            rsa_key = self._get_rsa_key()
            if not rsa_key:
                return False
            
            # Шифруем новый пароль
            encrypted_password = self._encrypt_password(new_password, rsa_key)
            if not encrypted_password:
                return False
            
            url = "https://help.steampowered.com/en/wizard/AjaxAccountRecoveryChangePassword/"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                's': self.recovery_params['s'],
                'account': self.recovery_params['account'],
                'password': encrypted_password,
                'rsatimestamp': rsa_key['timestamp']
            }
            
            response = self.steam_client._session.post(url, data=data)
            if response.status_code == 200:
                try:
                    result = response.json()
                    if not result.get('errorMsg'):
                        print_and_log("✅ Новый пароль установлен")
                        return True
                    else:
                        print_and_log(f"❌ Ошибка установки пароля: {result.get('errorMsg')}")
                        return False
                except:
                    print_and_log("✅ Пароль установлен (ответ не в JSON)")
                    return True
            
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка установки пароля: {e}", "ERROR")
            return False
    
    def _get_rsa_key(self) -> Optional[Dict[str, str]]:
        """Получение RSA ключа для шифрования"""
        try:
            url = "https://help.steampowered.com/en/login/getrsakey/"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'username': self.username
            }
            
            response = self.steam_client._session.post(url, data=data)
            if response.status_code == 200:
                result = response.json()
                if not result.get('errorMsg'):
                    return {
                        'mod': result.get('publickey_mod', ''),
                        'exp': result.get('publickey_exp', ''),
                        'timestamp': result.get('timestamp', '')
                    }
            
            return None
            
        except Exception as e:
            print_and_log(f"❌ Ошибка получения RSA ключа: {e}", "ERROR")
            return None
    
    def _encrypt_password(self, password: str, rsa_key: Dict[str, str]) -> str:
        """Шифрование пароля с помощью RSA"""
        try:
            import rsa
            
            publickey_exp = int(rsa_key['exp'], 16)
            publickey_mod = int(rsa_key['mod'], 16)
            public_key = rsa.PublicKey(n=publickey_mod, e=publickey_exp)
            
            encrypted_password = rsa.encrypt(
                message=password.encode('ascii'),
                pub_key=public_key,
            )
            encrypted_password64 = base64.b64encode(encrypted_password)
            return str(encrypted_password64, 'utf8')
            
        except ImportError:
            print_and_log("❌ Библиотека rsa не установлена", "ERROR")
            print_and_log("💡 Установите: pip install rsa")
            return ""
        except Exception as e:
            print_and_log(f"❌ Ошибка шифрования пароля: {e}", "ERROR")
            return ""
    
    def _check_password_available(self, password: str) -> bool:
        """Проверка доступности пароля"""
        try:
            url = "https://help.steampowered.com/en/wizard/AjaxCheckPasswordAvailable/"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                'password': password
            }
            
            response = self.steam_client._session.post(url, data=data)
            if response.status_code == 200:
                result = response.json()
                if result.get('available'):
                    print_and_log("✅ Пароль доступен")
                    return True
                else:
                    print_and_log("❌ Пароль недоступен")
                    return False
            
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки доступности пароля: {e}", "ERROR")
            return False
    
    def _update_configuration(self, new_password: str) -> bool:
        """Обновление конфигурации с новым паролем"""
        try:
            print_and_log("💾 Обновляем конфигурацию...")
            
            # Получаем config_manager из контекста
            config_manager = self.account_context.config_manager
            
            # Обновляем пароль в конфигурации
            config_manager.set('password', new_password)
            
            # Сохраняем конфигурацию
            config_manager.save_config()
            
            print_and_log("✅ Конфигурация обновлена")
            return True
            
        except Exception as e:
            print_and_log(f"❌ Ошибка обновления конфигурации: {e}", "ERROR")
            return False

    # Остальные методы из вашего оригинального кода
    def _get_new_password(self) -> Optional[str]:
        """Получение нового пароля"""
        print_and_log("")
        print_and_log("📝 Введите новый пароль:")
        print_and_log("💡 Требования к паролю:")
        print_and_log("  • Минимум 8 символов")
        print_and_log("  • Должен содержать буквы и цифры")
        print_and_log("  • Рекомендуется использовать специальные символы")
        print_and_log("")
        
        while True:
            new_password: str = input("Новый пароль: ")
            
            if not new_password:
                print_and_log("❌ Пароль не может быть пустым", "ERROR")
                continue
            
            # Проверяем надежность пароля
            validation: Dict[str, Union[bool, int, list]] = self._validate_password(new_password)
            if not validation['is_valid']:
                print_and_log("❌ Пароль не соответствует требованиям:")
                for issue in validation['issues']:
                    print_and_log(f"  • {issue}")
                continue
            
            # Подтверждение пароля
            confirm_password: str = input("Подтвердите новый пароль: ")
            if new_password != confirm_password:
                print_and_log("❌ Пароли не совпадают", "ERROR")
                continue
            
            # Показываем оценку надежности
            score: int = validation['score']
            if score >= 4:
                print_and_log("✅ Отличный пароль!")
            elif score >= 2:
                print_and_log("⚠️  Пароль средней надежности")
            else:
                print_and_log("⚠️  Слабый пароль, но соответствует минимальным требованиям")
            
            return new_password
    
    def _confirm_password_change(self) -> bool:
        """Подтверждение смены пароля"""
        print_and_log("")
        print_and_log("⚠️  ВНИМАНИЕ:")
        print_and_log("  • Смена пароля может затронуть работу бота")
        print_and_log("  • Убедитесь, что у вас есть доступ к мобильному приложению Steam Guard")
        print_and_log("  • После смены пароля может потребоваться повторная настройка")
        print_and_log("")
        
        while True:
            choice: str = input("Продолжить смену пароля? (y/N): ").lower().strip()
            if choice in ('y', 'yes', 'да', 'д'):
                return True
            elif choice in ('n', 'no', 'нет', 'н', ''):
                print_and_log("Отменено.")
                return False
            else:
                print_and_log("❌ Введите 'y' для продолжения или 'n' для отмены", "ERROR")
    
    def _verify_current_password(self, password: str) -> bool:
        """Проверка текущего пароля"""
        try:
            print_and_log("🔍 Проверяем активность сессии...")
            
            if hasattr(self.steam_client, 'is_session_alive') and callable(self.steam_client.is_session_alive):
                if self.steam_client.is_session_alive():
                    print_and_log("✅ Сессия активна")
                    return True
                else:
                    print_and_log("❌ Сессия неактивна")
                    return False
            else:
                # Альтернативная проверка через тестовый запрос
                test_url = "https://store.steampowered.com/en/account/"
                test_response = self.steam_client._session.get(test_url)
                if test_response.status_code == 200 and "account" in test_response.text.lower():
                    print_and_log("✅ Сессия активна (по тесту)")
                    return True
                else:
                    print_and_log("❌ Сессия неактивна (по тесту)")
                    return False
                    
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки сессии: {e}", "ERROR")
            return False
    
    def _verify_steam_guard_data(self) -> bool:
        """Проверка наличия данных Steam Guard"""
        try:
            print_and_log("🔍 Проверяем данные Steam Guard...")
            
            if not self.steam_client.steam_guard:
                print_and_log("❌ Отсутствуют данные Steam Guard (mafile не загружен)")
                return False
            
            identity_secret = self.steam_client.steam_guard.get('identity_secret', '')
            account_config = self.account_context.config_manager.accounts_settings.get(self.username, {})
            steam_id = account_config.get('steam_id', '')
            
            if not identity_secret:
                print_and_log("❌ Отсутствует identity_secret в mafile")
                return False
            
            if not steam_id:
                print_and_log("❌ Отсутствует steamid в конфигурации")
                return False
            
            print_and_log("✅ Данные Steam Guard найдены")
            return True
                    
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки Steam Guard данных: {e}", "ERROR")
            return False
    
    def _validate_password(self, password: str) -> Dict[str, Union[bool, int, list]]:
        """Проверка надежности пароля"""
        result: Dict[str, Union[bool, int, list]] = {
            'is_valid': True,
            'score': 0,
            'issues': []
        }
        
        # Минимальная длина
        if len(password) < 8:
            result['issues'].append("Пароль должен содержать минимум 8 символов")
            result['is_valid'] = False
        
        # Проверка наличия букв
        if not any(c.isalpha() for c in password):
            result['issues'].append("Пароль должен содержать буквы")
            result['is_valid'] = False
        
        # Проверка наличия цифр
        if not any(c.isdigit() for c in password):
            result['issues'].append("Пароль должен содержать цифры")
            result['is_valid'] = False

        # Подсчет очков надежности
        if len(password) >= 12:
            result['score'] += 2
        elif len(password) >= 8:
            result['score'] += 1
            
        if any(c.isupper() for c in password):
            result['score'] += 1
            
        if any(c.islower() for c in password):
            result['score'] += 1
            
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            result['score'] += 2
            
        return result
