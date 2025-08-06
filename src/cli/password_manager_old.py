#  основан на https://github.com/sometastycake/steam-password-change/blob/master/steampassword/chpassword.py
#!/usr/bin/env python3
"""
Менеджер паролей для CLI интерфейса
"""
import base64
import time
from typing import Optional, Dict, Any, Union
from .constants import Messages
from .display_formatter import DisplayFormatter
from src.utils.logger_setup import print_and_log
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
    """Класс для смены пароля Steam аккаунта через правильный API"""
    
    BROWSER = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
        '537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36'
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
            
            # Шаг 4: Выполнение смены пароля через правильный API
            if self._perform_password_change_via_api(new_password):
                # Шаг 5: Обновление конфигурации
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
            
            # Проверяем только активность сессии
            if self.steam_client.is_session_alive():
                print_and_log("✅ Сессия активна")
                return True
            else:
                print_and_log("❌ Сессия неактивна")
                return False
                    
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки сессии: {e}", "ERROR")
            return False
    
    def _verify_steam_guard_data(self) -> bool:
        """Проверка наличия данных Steam Guard"""
        try:
            print_and_log("🔍 Проверяем данные Steam Guard...")
            
            # Получаем данные из steam_guard (mafile)
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
                print_and_log("❌ Отсутствует steamid в mafile")
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
    
    def _perform_password_change_via_api(self, new_password: str) -> bool:
        """Выполнение смены пароля через правильный Steam API"""
        try:
            print_and_log("🔄 Выполняем смену пароля через Steam API...")
            
            # Шаг 1: Получение параметров смены пароля
            params = self._get_password_change_params()
            if not params:
                return False
            
            # Шаг 2: Вход в страницу ввода кода
            if not self._login_info_enter_code(params):
                return False
            
            # Шаг 3: Отправка кода восстановления
            if not self._send_recovery_code(params):
                return False
            
            # Шаг 4: Подтверждение в мобильном приложении
            print_and_log("📱 Ожидаем подтверждения в мобильном приложении...")
            print_and_log("💡 Откройте Steam Guard и подтвердите смену пароля")
            
            if not self._handle_mobile_confirmation(params):
                return False
            
            # Шаг 5: Проверка подтверждения восстановления
            if not self._poll_account_recovery_confirmation(params):
                return False
            
            # Шаг 6: Проверка кода восстановления
            if not self._verify_account_recovery_code(params):
                return False
            
            # Шаг 7: Получение следующего шага
            if not self._account_recovery_get_next_step(params):
                return False
            
            # Шаг 8: Проверка старого пароля
            if not self._verify_old_password(params):
                return False
            
            # Шаг 9: Установка нового пароля
            if not self._set_new_password(params, new_password):
                return False
            
            print_and_log("✅ Пароль успешно изменен через Steam API")
            return True
                
        except Exception as e:
            print_and_log(f"❌ Ошибка смены пароля: {e}", "ERROR")
            return False
    
    def _get_password_change_params(self) -> Optional[Dict[str, str]]:
        """Получение параметров для смены пароля"""
        try:
            print_and_log("🔍 Получение параметров смены пароля...")
            
            # Используем правильные параметры для смены пароля
            # Эти параметры основаны на рабочем коде
            params = {
                's': '1',  # session ID
                'account': self.username,
                'reset': '1',
                'lost': '2',
                'issueid': '0'
            }
            
            print_and_log("✅ Параметры смены пароля готовы")
            print_and_log(f"🔍 Используемые параметры: {params}")
            return params
                
        except Exception as e:
            print_and_log(f"❌ Ошибка получения параметров: {e}", "ERROR")
            return None
    
    def _login_info_enter_code(self, params: Dict[str, str]) -> bool:
        """Вход в страницу ввода кода"""
        try:
            print_and_log("🔍 Вход в страницу ввода кода...")
            
            url = "https://help.steampowered.com/en/wizard/HelpWithLoginInfoEnterCode"
            response = self.steam_client._session.get(
                url,
                params={
                    's': params['s'],
                    'account': params['account'],
                    'reset': params['reset'],
                    'lost': params['lost'],
                    'issueid': params['issueid'],
                    'sessionid': self.steam_client._get_session_id(),
                    'wizard_ajax': '1',
                    'gamepad': '0',
                },
                headers={
                    'Accept': '*/*',
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': self.BROWSER,
                    'Referer': 'https://help.steampowered.com/wizard/HelpChangePassword?redir=store/account/',
                }
            )
            
            if response.status_code == 200:
                print_and_log("✅ Вход в страницу ввода кода выполнен")
                return True
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
                print_and_log(f"🔍 Ответ сервера: {response.text[:200]}")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка входа в страницу: {e}", "ERROR")
            return False
    
    def _send_recovery_code(self, params: Dict[str, str]) -> bool:
        """Отправка кода восстановления"""
        try:
            print_and_log("📤 Отправка кода восстановления...")
            
            url = "https://help.steampowered.com/en/wizard/AjaxSendAccountRecoveryCode"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                'gamepad': '0',
                's': params['s'],
                'method': '8',
                'link': '',
            }
            
            response = self.steam_client._session.post(
                url,
                data=data,
                headers={
                    'Accept': '*/*',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': 'https://help.steampowered.com',
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': self.BROWSER,
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print_and_log("✅ Код восстановления отправлен")
                    return True
                else:
                    print_and_log(f"❌ Ошибка отправки кода: {result.get('errorMsg', 'Unknown error')}")
                    return False
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка отправки кода: {e}", "ERROR")
            return False
    
    def _handle_mobile_confirmation(self, params: Dict[str, str]) -> bool:
        """Обработка подтверждения в мобильном приложении"""
        try:
            print_and_log("📱 Обработка подтверждения в мобильном приложении...")
            print_and_log("💡 Пожалуйста, подтвердите смену пароля в Steam Guard")
            
            # Получаем данные для подтверждения из steam_guard (mafile)
            if not self.steam_client.steam_guard:
                print_and_log("❌ Отсутствуют данные Steam Guard (mafile не загружен)")
                return False
            
            identity_secret = self.steam_client.steam_guard.get('identity_secret', '')
            account_config = self.account_context.config_manager.accounts_settings.get(self.username, {})
            steam_id = account_config.get('steam_id', '')
            
            if not identity_secret or not steam_id:
                print_and_log("❌ Отсутствуют данные Steam Guard (identity_secret или steamid в mafile)")
                return False
            
            # Создаем ConfirmationExecutor
            confirmation_executor = ConfirmationExecutor(
                identity_secret=identity_secret,
                my_steam_id=steam_id,
                session=self.steam_client._session
            )
            
            # Ждем подтверждения
            for attempt in range(10):  # 10 попыток по 3 секунды
                time.sleep(3)
                print_and_log(f"⏳ Ожидание подтверждения... Попытка {attempt + 1}/10")
                
                try:
                    # Получаем все подтверждения
                    confirmations = confirmation_executor._get_confirmations()
                    
                    # Ищем подтверждение для смены пароля по creator_id (params['s'])
                    creator_id = params.get('s', '')
                    if creator_id:
                        try:
                            creator_id_int = int(creator_id)
                            # Ищем подтверждение с нужным creator_id
                            for confirmation in confirmations:
                                if confirmation.creator_id == creator_id_int:
                                    # Подтверждаем
                                    result = confirmation_executor._send_confirmation(confirmation)
                                    if result.get('success'):
                                        print_and_log("✅ Подтверждение получено и отправлено")
                                        return True
                                    else:
                                        print_and_log(f"❌ Ошибка подтверждения: {result}")
                        except ValueError:
                            print_and_log("❌ Неверный формат creator_id")
                    
                    # Если не нашли подтверждение, продолжаем ждать
                    print_and_log("⏳ Подтверждение еще не появилось, продолжаем ждать...")
                    
                except Exception as e:
                    print_and_log(f"⏳ Ошибка при проверке подтверждений: {e}")
                    continue
            
            print_and_log("❌ Подтверждение не получено в течение 30 секунд")
            return False
            
        except Exception as e:
            print_and_log(f"❌ Ошибка обработки подтверждения: {e}", "ERROR")
            return False
    
    def _poll_account_recovery_confirmation(self, params: Dict[str, str]) -> bool:
        """Проверка подтверждения восстановления аккаунта"""
        try:
            print_and_log("🔍 Проверка подтверждения восстановления...")
            
            url = "https://help.steampowered.com/en/wizard/AjaxPollAccountRecoveryConfirmation"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                's': params['s'],
                'reset': params['reset'],
                'lost': params['lost'],
                'method': '8',
                'issueid': params['issueid'],
                'gamepad': '0',
            }
            
            response = self.steam_client._session.post(
                url,
                data=data,
                headers={
                    'Accept': '*/*',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': 'https://help.steampowered.com',
                    'User-Agent': self.BROWSER,
                    'X-Requested-With': 'XMLHttpRequest',
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if not result.get('errorMsg'):
                    print_and_log("✅ Подтверждение восстановления получено")
                    return True
                else:
                    print_and_log(f"❌ Ошибка подтверждения: {result.get('errorMsg')}")
                    return False
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки подтверждения: {e}", "ERROR")
            return False
    
    def _verify_account_recovery_code(self, params: Dict[str, str]) -> bool:
        """Проверка кода восстановления аккаунта"""
        try:
            print_and_log("🔍 Проверка кода восстановления...")
            
            url = "https://help.steampowered.com/en/wizard/AjaxVerifyAccountRecoveryCode"
            response = self.steam_client._session.get(
                url,
                params={
                    'code': '',
                    's': params['s'],
                    'reset': params['reset'],
                    'lost': params['lost'],
                    'method': '8',
                    'issueid': params['issueid'],
                    'sessionid': self.steam_client._get_session_id(),
                    'wizard_ajax': '1',
                    'gamepad': '0',
                },
                headers={
                    'Accept': '*/*',
                    'User-Agent': self.BROWSER,
                    'X-Requested-With': 'XMLHttpRequest',
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if not result.get('errorMsg'):
                    print_and_log("✅ Код восстановления проверен")
                    return True
                else:
                    print_and_log(f"❌ Ошибка проверки кода: {result.get('errorMsg')}")
                    return False
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки кода: {e}", "ERROR")
            return False
    
    def _account_recovery_get_next_step(self, params: Dict[str, str]) -> bool:
        """Получение следующего шага восстановления аккаунта"""
        try:
            print_and_log("🔍 Получение следующего шага...")
            
            url = "https://help.steampowered.com/en/wizard/AjaxAccountRecoveryGetNextStep"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                's': params['s'],
                'account': params['account'],
                'reset': params['reset'],
                'issueid': params['issueid'],
                'lost': '2',
            }
            
            response = self.steam_client._session.post(
                url,
                data=data,
                headers={
                    'Accept': '*/*',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': 'https://help.steampowered.com',
                    'User-Agent': self.BROWSER,
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if not result.get('errorMsg'):
                    print_and_log("✅ Следующий шаг получен")
                    return True
                else:
                    print_and_log(f"❌ Ошибка получения шага: {result.get('errorMsg')}")
                    return False
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка получения шага: {e}", "ERROR")
            return False
    
    def _verify_old_password(self, params: Dict[str, str]) -> bool:
        """Проверка старого пароля"""
        try:
            print_and_log("🔍 Проверка старого пароля...")
            
            # Получаем текущий пароль из конфигурации
            account_config = self.account_context.config_manager.accounts_settings.get(self.username, {})
            current_password = account_config.get('password', '')
            if not current_password:
                print_and_log("❌ Не удалось получить текущий пароль")
                return False
            
            # Получаем RSA ключ
            rsa_key = self._get_rsa_key()
            if not rsa_key:
                return False
            
            # Шифруем текущий пароль
            encrypted_password = self._encrypt_password(current_password, rsa_key['mod'], rsa_key['exp'])
            
            url = "https://help.steampowered.com/en/wizard/AjaxAccountRecoveryVerifyPassword/"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                's': params['s'],
                'lost': '2',
                'reset': '1',
                'password': encrypted_password,
                'rsatimestamp': rsa_key['timestamp'],
            }
            
            response = self.steam_client._session.post(
                url,
                data=data,
                headers={
                    'Accept': '*/*',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': 'https://help.steampowered.com',
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': self.BROWSER,
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if not result.get('errorMsg'):
                    print_and_log("✅ Старый пароль проверен")
                    return True
                else:
                    print_and_log(f"❌ Ошибка проверки старого пароля: {result.get('errorMsg')}")
                    return False
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка проверки старого пароля: {e}", "ERROR")
            return False
    

    
    def _set_new_password(self, params: Dict[str, str], new_password: str) -> bool:
        """Установка нового пароля"""
        try:
            print_and_log("🔐 Устанавливаем новый пароль...")
            
            # Проверяем доступность пароля
            if not self._check_password_available(new_password):
                return False
            
            # Получаем RSA ключ
            rsa_key = self._get_rsa_key()
            if not rsa_key:
                return False
            
            # Шифруем новый пароль
            encrypted_password = self._encrypt_password(new_password, rsa_key['mod'], rsa_key['exp'])
            
            url = "https://help.steampowered.com/ru/wizard/AjaxAccountRecoveryChangePassword/"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'wizard_ajax': '1',
                's': params['s'],
                'account': params['account'],
                'password': encrypted_password,
                'rsatimestamp': rsa_key['timestamp'],
            }
            
            response = self.steam_client._session.post(
                url,
                data=data,
                headers={
                    'Accept': '*/*',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': 'https://help.steampowered.com',
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': self.BROWSER,
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if not result.get('errorMsg'):
                    print_and_log("✅ Новый пароль установлен")
                    return True
                else:
                    print_and_log(f"❌ Ошибка установки пароля: {result.get('errorMsg')}")
                    return False
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
                return False
                
        except Exception as e:
            print_and_log(f"❌ Ошибка установки нового пароля: {e}", "ERROR")
            return False
    
    def _get_rsa_key(self) -> Optional[Dict[str, str]]:
        """Получение RSA ключа для шифрования"""
        try:
            url = "https://help.steampowered.com/en/login/getrsakey/"
            data = {
                'sessionid': self.steam_client._get_session_id(),
                'username': self.username,
            }
            
            response = self.steam_client._session.post(
                url,
                data=data,
                headers={
                    'Accept': '*/*',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'Origin': 'https://help.steampowered.com',
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': self.BROWSER,
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if not result.get('errorMsg'):
                    return {
                        'mod': result.get('publickey_mod', ''),
                        'exp': result.get('publickey_exp', ''),
                        'timestamp': result.get('timestamp', '')
                    }
                else:
                    print_and_log(f"❌ Ошибка получения RSA ключа: {result.get('errorMsg')}")
                    return None
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
                return None
                
        except Exception as e:
            print_and_log(f"❌ Ошибка получения RSA ключа: {e}", "ERROR")
            return None
    
    def _encrypt_password(self, password: str, mod: str, exp: str) -> str:
        """Шифрование пароля с помощью RSA"""
        try:
            # Упрощенная версия шифрования
            # В реальности нужно использовать библиотеку rsa
            import rsa
            
            publickey_exp = int(exp, 16)
            publickey_mod = int(mod, 16)
            public_key = rsa.PublicKey(n=publickey_mod, e=publickey_exp)
            
            encrypted_password = rsa.encrypt(
                message=password.encode('ascii'),
                pub_key=public_key,
            )
            encrypted_password64 = base64.b64encode(encrypted_password)
            return str(encrypted_password64, 'utf8')
            
        except ImportError:
            print_and_log("❌ Библиотека rsa не установлена", "ERROR")
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
                'password': password,
            }
            
            response = self.steam_client._session.post(
                url,
                data=data,
                headers={
                    'Origin': 'https://help.steampowered.com',
                    'User-Agent': self.BROWSER,
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('available'):
                    print_and_log("✅ Пароль доступен")
                    return True
                else:
                    print_and_log("❌ Пароль недоступен")
                    return False
            else:
                print_and_log(f"❌ HTTP ошибка: {response.status_code}")
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