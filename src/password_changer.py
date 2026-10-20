#  основан на https://github.com/sometastycake/steam-password-change/blob/master/steampassword/chpassword.py
#!/usr/bin/env python3
"""
Менеджер паролей для CLI интерфейса Steam аккаунтов.

Этот модуль предоставляет функциональность для смены паролей Steam аккаунтов
через официальный интерфейс Steam Help. Основан на оригинальном репозитории
steam-password-change.

Основные возможности:
- Валидация надежности паролей
- Смена пароля через Steam Help интерфейс
- Поддержка мобильного подтверждения Steam Guard
- Автоматическое обновление конфигурации
"""
import base64
import time
import urllib.parse
import re
from bs4 import BeautifulSoup, Tag
from pydantic import ValidationError
from typing import Optional, Dict, Any, Union, List
from .cli.constants import Messages
from .cli.display_formatter import DisplayFormatter
from .utils.logger_setup import print_and_log
from .utils.cookies_and_session import session_to_dict, extract_cookies_for_domain
from .cli.account_context import AccountContext
from .steampy.client import SteamClient
from .steampy.security import (
    SteamPasswordAvailabilityResponse,
    SteamPasswordChangeResponse,
    SteamRecoveryResponse,
    SteamRsaKeyResponse,
    account_session_id,
)
from .steampy.confirmation import ConfirmationExecutor, Confirmation
from .steampy.models import EResult

from .utils.logger_setup import logger


# Константы для улучшения читаемости
class PasswordConstants:
    """Константы для работы с паролями и процесса смены пароля."""
    MIN_PASSWORD_LENGTH = 8
    STRONG_PASSWORD_LENGTH = 12
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    MAX_POLL_ATTEMPTS = 10
    POLL_DELAY = 3
    MOBILE_CONFIRMATION_TYPE = 6
    MOBILE_CONFIRMATION_TYPE_NAME = 'Account details'
    RSA_ENCODING = 'ascii'
    RSA_ENCODING_UTF8 = 'utf8'

class HttpConstants:
    """Константы для HTTP запросов к Steam серверам."""
    BROWSER_USER_AGENT = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
        '537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    )
    
    COMMON_HEADERS = {
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'User-Agent': BROWSER_USER_AGENT,
        'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"'
    }
    
    AJAX_HEADERS = {
        **COMMON_HEADERS,
        'Accept': '*/*',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    FORM_HEADERS = {
        **COMMON_HEADERS,
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://help.steampowered.com'
    }

class SteamUrls:
    """URL адреса Steam Help для смены пароля."""
    HELP_CHANGE_PASSWORD = "https://help.steampowered.com/wizard/HelpChangePassword?redir=store/account/"
    ENTER_CODE = "https://help.steampowered.com/en/wizard/HelpWithLoginInfoEnterCode"
    SEND_RECOVERY_CODE = "https://help.steampowered.com/en/wizard/AjaxSendAccountRecoveryCode"
    POLL_CONFIRMATION = "https://help.steampowered.com/en/wizard/AjaxPollAccountRecoveryConfirmation"
    VERIFY_RECOVERY_CODE = "https://help.steampowered.com/en/wizard/AjaxVerifyAccountRecoveryCode"
    GET_NEXT_STEP = "https://help.steampowered.com/en/wizard/AjaxAccountRecoveryGetNextStep"
    VERIFY_PASSWORD = "https://help.steampowered.com/en/wizard/AjaxAccountRecoveryVerifyPassword/"
    CHANGE_PASSWORD = "https://help.steampowered.com/en/wizard/AjaxAccountRecoveryChangePassword/"
    GET_RSA_KEY = "https://help.steampowered.com/en/login/getrsakey/"
    CHECK_PASSWORD_AVAILABLE = "https://help.steampowered.com/en/wizard/AjaxCheckPasswordAvailable/"
    ACCOUNT_TEST = "https://store.steampowered.com/en/account/"

class HttpRequestHelper:
    """Вспомогательный класс для работы с HTTP запросами к Steam."""
    
    @staticmethod
    def get_common_headers() -> Dict[str, str]:
        return HttpConstants.COMMON_HEADERS.copy()
    
    @staticmethod
    def get_ajax_headers() -> Dict[str, str]:
        return HttpConstants.AJAX_HEADERS.copy()
    
    @staticmethod
    def get_form_headers() -> Dict[str, str]:
        return HttpConstants.FORM_HEADERS.copy()
    
    @staticmethod
    def build_referer_url(base_url: str, params: Dict[str, str]) -> str:
        """Построение URL для Referer заголовка из базового URL и параметров."""
        param_strings = [f"{k}={v}" for k, v in params.items()]
        return f"{base_url}?{'&'.join(param_strings)}"


class PasswordChanger:
    """
    Класс для смены пароля Steam аккаунта.
    
    Реализует полный процесс смены пароля через Steam Help интерфейс,
    включая мобильное подтверждение Steam Guard. Объединяет функциональность
    PasswordManager и PasswordValidator в единый класс.
    Основан на https://github.com/sometastycake/steam-password-change
    """
    
    def __init__(self, account_context: AccountContext) -> None:
        """
        Инициализация с контекстом аккаунта.
        
        Args:
            account_context: Контекст аккаунта с настроенными прокси и сессией
        """
        self.account_context: AccountContext = account_context
        self.formatter: DisplayFormatter = DisplayFormatter()
        self.http_helper: HttpRequestHelper = HttpRequestHelper()
        self.username: str = account_context.account_name
        self.steam_client: Optional[SteamClient] = None

        # Параметры для восстановления (эквивалент PasswordChangeParams)
        self.recovery_params: Dict[str, str] = {}
        self._password_submission_attempted: bool = False

    def _help_session_id(self, url: str) -> str:
        """Require authentication and the CSRF cookie for the actual Steam Help destination."""
        session_id: str | None = account_session_id(self.steam_client._session, self.steam_client.steam_id, url)
        if not session_id:
            raise ValueError("Missing or mismatched Steam Help session")
        return session_id

    def _has_password_change_route(self) -> bool:
        """Allow only the authenticated password-change route observed in Steam's own wizard."""
        return (
            self.recovery_params.get("reset") == "1"
            and self.recovery_params.get("lost") == "0"
            and self.recovery_params.get("issueid") == "406"
            and bool(self.recovery_params.get("s"))
            and bool(self.recovery_params.get("account"))
        )

    def change_password(self, account_context: AccountContext) -> bool:
        """
        Смена пароля Steam аккаунта.

        Args:
            account_context: Контекст аккаунта с настроенной сессией

        Returns:
            bool: True если пароль успешно изменен, False в противном случае
        """
        try:
            print_and_log(self.formatter.format_section_header("🔒 Смена пароля"))
            print_and_log("⚠️  ВНИМАНИЕ: Смена пароля может затронуть работу бота!")
            print_and_log("💡 Убедитесь, что у вас есть доступ к мобильному приложению Steam Guard")
            print_and_log("")
            
            # Запускаем процесс смены пароля
            return self.execute()
            
        except Exception as e:
            print_and_log(f"❌ Ошибка смены пароля: {type(e).__name__}", "ERROR")
            input("Нажмите Enter для продолжения...")
            return False
        
    def execute(self) -> bool:
        """
        Выполнение процесса смены пароля.
        
        Returns:
            bool: True если пароль успешно изменен, False в противном случае
        """
        self._password_submission_attempted = False
        try:
            print_and_log(f"🔒 Начинаем смену пароля для аккаунта: {self.username}")
            print_and_log("")
            
            # Получаем Steam клиент
            self.steam_client = self.account_context.cookie_manager.get_steam_client()
            if not self.steam_client:
                print_and_log("❌ Не удалось получить Steam клиент", "ERROR")
                return False
            
            # Проверка активности сессии
            if not self._verify_current_session():
                print_and_log("❌ Сессия неактивна, необходимо войти в аккаунт", "ERROR")
                return False
            
            # Проверка наличия Steam Guard данных
            if not self._verify_steam_guard_data():
                print_and_log("❌ Отсутствуют данные Steam Guard", "ERROR")
                return False
            
            # Получение нового пароля
            new_password: Optional[str] = self._get_new_password()
            if not new_password:
                return False
            
            # Подтверждение смены
            if not self._confirm_password_change(new_password):
                return False
            
            # Полный процесс смены пароля
            if self._change_password_full_process(new_password):
                # Обновление конфигурации
                if self._update_configuration(new_password):
                    print_and_log("✅ Пароль успешно изменен и сохранен в конфигурации!")
                    print_and_log("💡 Обновите копии пароля в других проектах, если они используются.")
                    return True
                else:
                    print_and_log(
                        "❌ Пароль в Steam изменён, но config.yaml не обновлён. Сохраните введённый пароль вручную; не повторяйте смену."
                    )
                    return False
            else:
                if self._password_submission_attempted:
                    print_and_log(
                        "❌ Смена пароля не подтверждена. После сетевой ошибки пароль уже мог измениться; не повторяйте запрос вслепую."
                    )
                else:
                    print_and_log("❌ Смена пароля остановлена. Запрос установки нового пароля не отправлялся.")
                return False

        except Exception as e:
            print_and_log(f"❌ Ошибка в процессе смены пароля: {type(e).__name__}", "ERROR")
            return False
    
    def _change_password_full_process(self, new_password: str) -> bool:
        """
        Полный процесс смены пароля на основе оригинального репозитория.
        
        Args:
            new_password: Новый пароль для установки
            
        Returns:
            bool: True если процесс завершен успешно
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
            if not self._has_password_change_route():
                print_and_log("❌ Steam вернул другой сценарий восстановления. Смена пароля остановлена.")
                return False
            
            # Шаг 2: Переход к вводу кода (аналог HelpWithLoginInfoEnterCode)
            print_and_log("🔄 Переход к вводу кода...")
            if not self._goto_enter_code():
                return False
            
            # Шаг 3: Отправка запроса на восстановление (аналог AjaxSendAccountRecoveryCode)
            print_and_log("🔄 Отправка запроса на восстановление...")
            if not self._send_recovery_request():
                return False
            
            print_and_log("🔄 Проверка подтверждения в мобильном приложении...")
            if not self.confirm_via_guard():
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
            print_and_log(f"❌ Ошибка в процессе смены пароля: {type(e).__name__}", "ERROR")
            return False
    
    def confirm_via_guard(self) -> bool:
        """
        Подтверждение смены пароля через мобильное приложение Steam Guard.
        
        Returns:
            bool: True если подтверждение получено успешно
        """
        try:
            confirmation_executor = ConfirmationExecutor(
                identity_secret=self.account_context.cookie_manager.steam_client.steam_guard['identity_secret'],
                my_steam_id=self.account_context.cookie_manager.steam_client.steam_id,
                session=self.account_context.cookie_manager.steam_client._session
            )
            # Получаем JSON с подтверждениями напрямую
            confirmations_page = confirmation_executor._fetch_confirmations_page()
            confirmations_json = confirmations_page.json()
            
            if not confirmations_json.get('success'):
                logger.error("❌ Не удалось получить мобильные подтверждения")
                return False

            all_confirmations = confirmations_json.get('conf', [])
            
            if len(all_confirmations) == 0:
                print_and_log("❌ Нет подтверждений в мобильном приложении")
                return False
            
            for confirmation in all_confirmations:
                # Проверяем тип подтверждения (Account details = 6)
                if (confirmation.get('type_name', "") == PasswordConstants.MOBILE_CONFIRMATION_TYPE_NAME and 
                    confirmation.get('type', -1) == PasswordConstants.MOBILE_CONFIRMATION_TYPE):
                    print_and_log("✅ Найдено подтверждение изменения данных аккаунта.")
                    # Проверяем, что это наше подтверждение по creator_id
                    if confirmation.get("creator_id", "") == self.recovery_params["s"]:
                        print_and_log("✅ Подтверждение соответствует текущему запросу смены пароля.")
                        conf = Confirmation(
                            data_confid=confirmation['id'],
                            nonce=confirmation['nonce'],
                            creator_id=int(confirmation['creator_id'])
                        )
                        response = confirmation_executor._send_confirmation(conf)
                        # Проверяем результат подтверждения
                        if response and response.get('success'):
                            return True
                        else:
                            logger.error("Steam did not accept the account-details confirmation")
                            return False
            
            else:
                print_and_log("❌ Не найдено подтверждение для аккаунта")
                return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка в процессе смены пароля (во время подтверждения в мобильном приложении): {type(e).__name__}", "ERROR")
            return False

    def _initialize_recovery(self, steam_id: str) -> bool:
        """
        Инициализация процесса восстановления пароля.

        Аналог _receive_password_change_params из оригинального кода.

        Args:
            steam_id: Steam ID аккаунта

        Returns:
            bool: True если инициализация прошла успешно
        """
        try:
            print_and_log(f"🔍 Начинаем инициализацию для Steam ID: {steam_id}")

            print_and_log("🔍 Отправляем запрос с куки от steamcommunity.com...")

            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Referer": "https://store.steampowered.com/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                **self.http_helper.get_common_headers(),
            }

            response = self.steam_client._session.get(SteamUrls.HELP_CHANGE_PASSWORD, headers=headers, allow_redirects=True)

            print_and_log(f"🔍 Статус ответа: {response.status_code}")
            print_and_log("🔍 Ответ Steam Help получен.")
            print_and_log(f"🔍 История редиректов: {len(response.history)} редиректов")

            page: BeautifulSoup = BeautifulSoup(response.text, "html.parser")
            error_description: Tag | None = page.select_one(".page_error #error_description")
            if error_description is not None:
                error_code: re.Match[str] | None = re.search(r"\((\d+)\)\s*$", error_description.get_text(" ", strip=True))
                if error_code is not None and int(error_code.group(1)) == EResult.RATE_LIMIT_EXCEEDED.value:
                    print_and_log("❌ Steam Help: превышен лимит запросов (84). Повторите попытку позже.")
                else:
                    print_and_log("❌ Steam Help вернул ошибку. Смена пароля остановлена.")
                return False
            if response.status_code != 200:
                print_and_log(f"❌ Steam Help: HTTP {response.status_code}")
                return False

            if self.account_context.username.lower() in response.text.lower():
                print(f"✅ {self.username} найден в тексте - АВТОРИЗОВАН")
            else:
                print(f"❌ {self.username} НЕ найден в тексте - НЕ АВТОРИЗОВАН")
                return False

            # Проверяем, не перенаправило ли снова на логин
            if "/login" in response.url:
                print_and_log("❌ Steam снова перенаправил на страницу входа")
                print_and_log("💡 Возможные причины:")
                print_and_log("  • Сессия истекла")
                print_and_log("  • Нет авторизации для операций восстановления")
                print_and_log("  • Требуется повторный вход в аккаунт")
                return False

            # Parse the native continuation independently of language redirects.
            continuation_urls: list[str] = [
                urllib.parse.urljoin(response.url, anchor["href"])
                for anchor in page.find_all("a", href=True)
                if re.fullmatch(
                    r"/(?:[a-z]{2}(?:-[a-z0-9]{2,3})?/)?wizard/HelpWithLoginInfoEnterCode/?",
                    urllib.parse.urlparse(urllib.parse.urljoin(response.url, anchor["href"])).path,
                )
            ]
            if len(continuation_urls) != 1:
                print_and_log("❌ Steam не выдал однозначную ссылку продолжения смены пароля.")
                return False
            continuation: urllib.parse.ParseResult = urllib.parse.urlparse(continuation_urls[0])
            if continuation.scheme != "https" or continuation.netloc != "help.steampowered.com":
                return False
            query_params: dict[str, list[str]] = urllib.parse.parse_qs(continuation.query)
            required_fields: tuple[str, ...] = ("s", "account", "reset", "issueid", "lost")
            if any(len(query_params.get(key, [])) != 1 for key in required_fields):
                print_and_log("❌ Steam не выдал обязательные параметры смены пароля.")
                return False
            self.recovery_params = {key: query_params[key][0] for key in required_fields}
            if not self._has_password_change_route():
                print_and_log("❌ Steam выдал сценарий восстановления или неизвестный режим. Продолжение остановлено.")
                return False
            print_and_log("✅ Получен штатный сценарий смены пароля: lost=0.")
            return True

        except Exception as e:
            print_and_log(f"❌ Исключение в _initialize_recovery: {type(e).__name__}", "ERROR")
            return False

    def _goto_enter_code(self) -> bool:
        """
        Переход к странице ввода кода с использованием извлеченных параметров.
        
        Returns:
            bool: True если переход выполнен успешно
        """
        try:
            print_and_log("🔍 Переход к странице ввода кода...")
            
            # Используем все параметры, полученные при инициализации
            url = SteamUrls.ENTER_CODE
            params = {
                's': self.recovery_params['s'],  # ID сессии восстановления
                'account': self.recovery_params['account'],  # Имя аккаунта
                'reset': self.recovery_params['reset'],  # Флаг сброса
                'lost': self.recovery_params['lost'],  # Флаг потерянного доступа
                'issueid': self.recovery_params['issueid'],  # ID проблемы
                'sessionid': self._help_session_id(url),  # ID сессии Steam
                'wizard_ajax': '1',  # Флаг AJAX запроса
                'gamepad': '0'  # Флаг геймпада
            }
            
            print_and_log(f"🔍 URL: {url}")
            print_and_log("🔍 Параметры запроса подготовлены.")

            headers = {
                **self.http_helper.get_ajax_headers(),
                'Referer': self.http_helper.build_referer_url(url, self.recovery_params)
            }
            
            response = self.steam_client._session.get(url, params=params, headers=headers)
            
            print_and_log(f"🔍 Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                print_and_log(f"🔍 Длина содержимого: {len(content)}")
                print_and_log("🔍 Страница Steam Help получена.")

                print_and_log("✅ Переход к вводу кода выполнен успешно")
                return True
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка перехода к вводу кода: {type(e).__name__}", "ERROR")
            return False
    
    def _send_recovery_request(self) -> bool:
        """
        Отправка запроса на восстановление пароля.
        
        Returns:
            bool: True если запрос отправлен успешно
        """
        try:
            url = SteamUrls.SEND_RECOVERY_CODE
            data = {
                'sessionid': self._help_session_id(url),  # ID сессии Steam
                'wizard_ajax': '1',  # Флаг AJAX запроса
                'gamepad': '0',  # Флаг геймпада
                's': self.recovery_params['s'],  # ID сессии восстановления
                'method': '8',  # Мобильное подтверждение Steam Guard
                'link': '',  # Пустая ссылка
                'n': '1'  # Количество кодов
            }
            
            headers = {
                **self.http_helper.get_form_headers(),
                'Referer': self.http_helper.build_referer_url(SteamUrls.ENTER_CODE, self.recovery_params)
            }
            
            response = self.steam_client._session.post(url, data=data, headers=headers)
            if response.status_code == 200:
                try:
                    result: SteamRecoveryResponse = SteamRecoveryResponse.model_validate_json(response.content)
                    logger.info("Password recovery request response received")
                    if result.success:
                        print_and_log("✅ Запрос на восстановление отправлен")
                        return True
                    else:
                        print_and_log("❌ Steam отклонил запрос восстановления.")
                        return False
                except ValidationError:
                    print_and_log("❌ Неожиданный ответ Steam: запрос не подтверждён.")
                    return False

            print_and_log(f"❌ HTTP ошибка: {response.status_code}")
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка отправки запроса: {type(e).__name__}", "ERROR")
            return False
    
    def _poll_confirmation(self) -> bool:
        """
        Поллинг подтверждения смены пароля.
        
        Returns:
            bool: True если подтверждение получено
        """
        try:
            url = SteamUrls.POLL_CONFIRMATION
            data = {
                'sessionid': self._help_session_id(url),  # ID сессии Steam
                'wizard_ajax': '1',  # Флаг AJAX запроса
                'gamepad': '0',  # Флаг геймпада
                's': self.recovery_params['s'],  # ID сессии восстановления
                'reset': self.recovery_params['reset'],  # Флаг сброса
                'lost': self.recovery_params['lost'],  # Флаг потерянного доступа
                'method': '8',  # Мобильное подтверждение Steam Guard
                'issueid': self.recovery_params['issueid']  # ID проблемы
            }
            
            headers = {
                **self.http_helper.get_form_headers(),
                'Referer': self.http_helper.build_referer_url(SteamUrls.ENTER_CODE, self.recovery_params)
            }
            
            for attempt in range(PasswordConstants.MAX_POLL_ATTEMPTS):
                print_and_log(f"⏳ Попытка {attempt + 1}/{PasswordConstants.MAX_POLL_ATTEMPTS}")
                
                response = self.steam_client._session.post(url, data=data, headers=headers)
                
                if response.status_code == 200:
                    try:
                        result: SteamRecoveryResponse = SteamRecoveryResponse.model_validate_json(response.content)
                        logger.info("Password recovery confirmation response received")
                        if not result.errorMsg and (result.success is None or bool(result.success)):
                            print_and_log("✅ Подтверждение получено!")
                            return True
                        elif "ожидание" in (result.errorMsg or "").lower():
                            time.sleep(PasswordConstants.POLL_DELAY)
                            continue
                        else:
                            print_and_log("❌ Steam отклонил подтверждение.")
                            return False
                    except ValidationError:
                        print_and_log("❌ Неожиданный ответ Steam: подтверждение не получено.")
                        return False

                time.sleep(PasswordConstants.POLL_DELAY)
            
            print_and_log("❌ Подтверждение не получено в течение 3 минут")
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка поллинга: {type(e).__name__}", "ERROR")
            return False
    
    def _verify_recovery_code(self) -> bool:
        """
        Верификация кода восстановления пароля.
        
        Returns:
            bool: True если код верифицирован успешно
        """
        try:
            url = SteamUrls.VERIFY_RECOVERY_CODE
            params = {
                'code': '',  # Пустой код (подтверждение уже получено)
                's': self.recovery_params['s'],  # ID сессии восстановления
                'reset': self.recovery_params['reset'],  # Флаг сброса
                'lost': self.recovery_params['lost'],  # Флаг потерянного доступа
                'method': '8',  # Мобильное подтверждение Steam Guard
                'issueid': self.recovery_params['issueid'],  # ID проблемы
                'sessionid': self._help_session_id(url),  # ID сессии Steam
                'wizard_ajax': '1',  # Флаг AJAX запроса
                'gamepad': '0'  # Флаг геймпада
            }
            
            response = self.steam_client._session.get(url, params=params)
            if response.status_code == 200:
                try:
                    result: SteamRecoveryResponse = SteamRecoveryResponse.model_validate_json(response.content)
                    logger.info("Password recovery code verification response received")
                    return not result.errorMsg and (result.success is None or bool(result.success))
                except ValidationError:
                    return False

            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка верификации кода: {type(e).__name__}", "ERROR")
            return False
    
    def _get_next_step(self) -> bool:
        """
        Получение следующего шага процесса восстановления.
        
        Returns:
            bool: True если следующий шаг получен успешно
        """
        try:
            if not self._has_password_change_route():
                return False
            url = SteamUrls.GET_NEXT_STEP
            data = {
                'sessionid': self._help_session_id(url),  # ID сессии Steam
                'wizard_ajax': '1',  # Флаг AJAX запроса
                's': self.recovery_params['s'],  # ID сессии восстановления
                'account': self.recovery_params['account'],  # Имя аккаунта
                'reset': self.recovery_params['reset'],  # Флаг сброса
                'issueid': self.recovery_params['issueid'],  # ID проблемы
                'lost': self.recovery_params['lost']
            }
            
            response = self.steam_client._session.post(url, data=data)
            if response.status_code == 200:
                try:
                    result: SteamRecoveryResponse = SteamRecoveryResponse.model_validate_json(response.content)
                    logger.info("Password recovery next-step response received")
                    return not result.errorMsg and (result.success is None or bool(result.success))
                except ValidationError:
                    return False

            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка получения шага: {type(e).__name__}", "ERROR")
            return False
    
    def _verify_old_password(self) -> bool:
        """
        Верификация текущего пароля аккаунта.
        
        Returns:
            bool: True если пароль верифицирован успешно
        """
        try:
            if not self._has_password_change_route():
                return False
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
            
            url = SteamUrls.VERIFY_PASSWORD
            data = {
                'sessionid': self._help_session_id(url),  # ID сессии Steam
                's': self.recovery_params['s'],  # ID сессии восстановления
                'lost': self.recovery_params['lost'],
                'reset': self.recovery_params['reset'],
                'password': encrypted_password,  # Зашифрованный текущий пароль
                'rsatimestamp': rsa_key['timestamp']  # Временная метка RSA ключа
            }
        
            response = self.steam_client._session.post(url, data=data)
            if response.status_code == 200:
                try:
                    result: SteamRecoveryResponse = SteamRecoveryResponse.model_validate_json(response.content)
                    logger.info("Current password verification response received")
                    return not result.errorMsg and (result.success is None or bool(result.success))
                except ValidationError:
                    return False

            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка верификации пароля: {type(e).__name__}", "ERROR")
            return False
    
    def _set_new_password(self, new_password: str) -> bool:
        """
        Установка нового пароля для аккаунта.
        
        Args:
            new_password: Новый пароль для установки
            
        Returns:
            bool: True если пароль установлен успешно
        """
        try:
            if not self._has_password_change_route():
                print_and_log("❌ Запрос смены пароля остановлен: сценарий восстановления или неизвестные параметры Steam.")
                return False
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
            
            url = SteamUrls.CHANGE_PASSWORD
            data = {
                'sessionid': self._help_session_id(url),  # ID сессии Steam
                'wizard_ajax': '1',  # Флаг AJAX запроса
                's': self.recovery_params['s'],  # ID сессии восстановления
                'account': self.recovery_params['account'],  # Имя аккаунта
                'password': encrypted_password,  # Зашифрованный новый пароль
                'rsatimestamp': rsa_key['timestamp']  # Временная метка RSA ключа
            }

            self._password_submission_attempted = True
            response = self.steam_client._session.post(url, data=data, allow_redirects=False)
            if response.status_code != 200:
                print_and_log(f"❌ Steam не подтвердил смену пароля: HTTP {response.status_code}")
                return False
            try:
                result: SteamPasswordChangeResponse = SteamPasswordChangeResponse.model_validate_json(response.content)
            except ValidationError:
                print_and_log("❌ Неожиданный ответ Steam: смена пароля не подтверждена.")
                return False
            if not result.ready_to_verify:
                print_and_log("❌ Steam отклонил смену пароля.")
                return False
            if not self.steam_client.login_with_password(new_password):
                print_and_log("❌ Вход новым паролем не подтверждён. Пароль уже мог измениться; проверьте его вручную.")
                return False
            if not self.account_context.cookie_manager.save_verified_session(new_password):
                print_and_log("⚠️ Новый пароль подтверждён, но сохранение сессии не завершено. Не повторяйте смену пароля.")
            print_and_log("✅ Новый пароль установлен")
            return True

        except Exception as e:
            print_and_log(f"❌ Ошибка установки пароля: {type(e).__name__}", "ERROR")
            return False
    
    def _get_rsa_key(self) -> Optional[Dict[str, str]]:
        """
        Получение RSA ключа для шифрования пароля.
        
        Returns:
            Optional[Dict[str, str]]: RSA ключ или None при ошибке
        """
        try:
            url = SteamUrls.GET_RSA_KEY
            data = {
                "sessionid": self._help_session_id(url),  # ID сессии Steam
                "username": self.account_context.username,  # Имя пользователя
            }
            
            response = self.steam_client._session.post(url, data=data)
            if response.status_code == 200:
                result: SteamRsaKeyResponse = SteamRsaKeyResponse.model_validate_json(response.content)
                if result.confirmed:
                    return {
                        'mod': result.publickey_mod,
                        'exp': result.publickey_exp,
                        'timestamp': result.timestamp,
                    }
            
            return None
            
        except Exception as e:
            print_and_log(f"❌ Ошибка получения RSA ключа: {type(e).__name__}", "ERROR")
            return None
    
    def _encrypt_password(self, password: str, rsa_key: Dict[str, str]) -> str:
        """
        Шифрование пароля с помощью RSA.
        
        Args:
            password: Пароль для шифрования
            rsa_key: RSA ключ для шифрования
            
        Returns:
            str: Зашифрованный пароль в base64 или пустая строка при ошибке
        """
        try:
            import rsa
            
            publickey_exp = int(rsa_key['exp'], 16)
            publickey_mod = int(rsa_key['mod'], 16)
            public_key = rsa.PublicKey(n=publickey_mod, e=publickey_exp)
            
            encrypted_password = rsa.encrypt(
                message=password.encode(PasswordConstants.RSA_ENCODING),
                pub_key=public_key,
            )
            encrypted_password64 = base64.b64encode(encrypted_password)
            return str(encrypted_password64, PasswordConstants.RSA_ENCODING_UTF8)

        except ImportError:
            print_and_log("❌ Библиотека rsa не установлена", "ERROR")
            print_and_log("💡 Установите: uv sync")
            return ""
        except Exception as e:
            print_and_log(f"❌ Ошибка шифрования пароля: {type(e).__name__}", "ERROR")
            return ""
    
    def _check_password_available(self, password: str) -> bool:
        """
        Проверка доступности пароля для использования.
        
        Args:
            password: Пароль для проверки
            
        Returns:
            bool: True если пароль доступен для использования
        """
        try:
            url = SteamUrls.CHECK_PASSWORD_AVAILABLE
            data = {
                'sessionid': self._help_session_id(url),  # ID сессии Steam
                'wizard_ajax': '1',  # Флаг AJAX запроса
                'password': password  # Пароль для проверки
            }
            
            response = self.steam_client._session.post(url, data=data)
            if response.status_code == 200:
                result: SteamPasswordAvailabilityResponse = SteamPasswordAvailabilityResponse.model_validate_json(response.content)
                logger.info("Password availability response received")
                if result.available:
                    print_and_log("✅ Пароль доступен")
                    return True
                else:
                    print_and_log("❌ Пароль недоступен")
                    return False
            
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки доступности пароля: {type(e).__name__}", "ERROR")
            return False
    
    def _update_configuration(self, new_password: str) -> bool:
        """
        Обновление конфигурации с новым паролем.
        
        Args:
            new_password: Новый пароль для сохранения
            
        Returns:
            bool: True если конфигурация обновлена успешно
        """
        try:
            print_and_log("💾 Обновляем конфигурацию...")

            self.account_context.config_manager.update_account_password(self.username, new_password)
            self.account_context.cookie_manager.set_password(new_password)

            print_and_log("✅ Конфигурация обновлена")
            return True
            
        except Exception as e:
            print_and_log(f"❌ Ошибка обновления конфигурации: {type(e).__name__}", "ERROR")
            return False

    # Остальные методы из вашего оригинального кода
    def _get_new_password(self) -> Optional[str]:
        """
        Интерактивное получение нового пароля от пользователя.

        Returns:
            Optional[str]: Новый пароль или None при отмене
        """
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
            if new_password == self.account_context.cookie_manager.password:
                print_and_log("❌ Новый пароль должен отличаться от текущего.")
                continue

            # Проверяем надежность пароля
            validation: Dict[str, Union[bool, int, List[str]]] = self.validate_password_strength(new_password)
            if not validation["is_valid"]:
                print_and_log("❌ Пароль не соответствует требованиям:")
                for issue in validation["issues"]:
                    print_and_log(f"  • {issue}")
                continue

            # Подтверждение пароля
            confirm_password: str = input("Подтвердите новый пароль: ")
            if new_password != confirm_password:
                print_and_log("❌ Пароли не совпадают", "ERROR")
                continue

            # Показываем оценку надежности
            score: int = validation["score"]
            if score >= 4:
                print_and_log("✅ Отличный пароль!")
            elif score >= 2:
                print_and_log("⚠️  Пароль средней надежности")
            else:
                print_and_log("⚠️  Слабый пароль, но соответствует минимальным требованиям")

            return new_password

    def _confirm_password_change(self, new_password: str) -> bool:
        """Preview the password in the console and require consent before submission.

        Args:
            new_password: Exact password to display without writing it to logs.

        Returns:
            True if the user confirms the displayed password.
        """
        print_and_log("")
        print_and_log("⚠️  ВНИМАНИЕ:")
        print_and_log("  • Смена пароля может затронуть работу бота")
        print_and_log("  • Убедитесь, что у вас есть доступ к мобильному приложению Steam Guard")
        print_and_log("  • После смены пароля может потребоваться повторная настройка")
        print_and_log("  • Один тестовый аккаунт проверен без новых видимых ограничений; это не гарантия для всех аккаунтов.")
        print_and_log(
            "  • При сбросе забытого пароля Steam ограничивает торговлю и Market на 5 дней, а после долгой неактивности — на 30 дней."
        )
        print_and_log("")
        print_and_log(f"Аккаунт: {self.username}")
        print(f"Новый пароль: {new_password}")
        print_and_log("Убедитесь, что новый пароль указан верно.")

        while True:
            choice: str = input("Установить этот пароль? (y/N): ").lower().strip()
            if choice in ("y", "yes", "да", "д"):
                return True
            elif choice in ("n", "no", "нет", "н", ""):
                print_and_log("Отменено.")
                return False
            else:
                print_and_log("❌ Введите 'y' для продолжения или 'n' для отмены", "ERROR")

    def _verify_current_session(self) -> bool:
        """
        Проверка активности текущей сессии Steam.
        
        Returns:
            bool: True если сессия активна
        """
        try:
            print_and_log("🔍 Проверяем активность сессии...")
            expected_id: str = str(self.account_context.config_manager.accounts_settings[self.username]["steam_id"])
            if str(self.steam_client.steam_id) != expected_id or not account_session_id(
                self.steam_client._session, expected_id, SteamUrls.CHANGE_PASSWORD
            ):
                print_and_log("❌ Сессия не соответствует выбранному Steam-аккаунту.")
                return False

            if hasattr(self.steam_client, 'is_session_alive') and callable(self.steam_client.is_session_alive):
                if self.steam_client.is_session_alive():
                    print_and_log("✅ Сессия активна")
                    return True
                else:
                    print_and_log("❌ Сессия неактивна")
                    return False
            else:
                # Альтернативная проверка через тестовый запрос
                test_url = SteamUrls.ACCOUNT_TEST
                test_response = self.steam_client._session.get(test_url)
                if test_response.status_code == 200 and "account" in test_response.text.lower():
                    print_and_log("✅ Сессия активна (по тесту)")
                    return True
                else:
                    print_and_log("❌ Сессия неактивна (по тесту)")
                    return False
                    
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки сессии: {type(e).__name__}", "ERROR")
            return False
    
    def _verify_steam_guard_data(self) -> bool:
        """
        Проверка наличия данных Steam Guard для мобильного подтверждения.
        
        Returns:
            bool: True если данные Steam Guard доступны
        """
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

            if not self.steam_client.steam_guard.get("shared_secret"):
                print_and_log("❌ Отсутствует shared_secret для проверки входа новым паролем")
                return False

            if not steam_id:
                print_and_log("❌ Отсутствует steamid в конфигурации")
                return False
            
            print_and_log("✅ Данные Steam Guard найдены")
            return True
                    
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки Steam Guard данных: {type(e).__name__}", "ERROR")
            return False
    
    def validate_password_strength(self, password: str) -> Dict[str, Union[bool, int, List[str]]]:
        """
        Проверка надежности пароля.
        
        Args:
            password: Пароль для проверки
            
        Returns:
            Dict с результатами проверки:
            - is_valid: bool - соответствует ли пароль требованиям
            - score: int - оценка надежности (0-6)
            - issues: List[str] - список проблем с паролем
        """
        result: Dict[str, Union[bool, int, List[str]]] = {
            'is_valid': True,
            'score': 0,
            'issues': []
        }
        
        # Минимальная длина
        if len(password) < PasswordConstants.MIN_PASSWORD_LENGTH:
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
        if len(password) >= PasswordConstants.STRONG_PASSWORD_LENGTH:
            result['score'] += 2
        elif len(password) >= PasswordConstants.MIN_PASSWORD_LENGTH:
            result['score'] += 1
            
        if any(c.isupper() for c in password):
            result['score'] += 1
            
        if any(c.islower() for c in password):
            result['score'] += 1
            
        if any(c in PasswordConstants.SPECIAL_CHARS for c in password):
            result['score'] += 2
            
        return result
