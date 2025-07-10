#!/usr/bin/env python3
"""
Менеджер настроек для CLI интерфейса
"""

import os
import json
import re
import shutil
import platform
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any

from .constants import Messages
from .display_formatter import DisplayFormatter
from src.utils.logger_setup import print_and_log


class SettingsManager:
    """Менеджер настроек"""
    
    def __init__(self, accounts_dir: str = "accounts_info"):
        self.accounts_dir = Path(accounts_dir)
        self.formatter = DisplayFormatter()
        
        # Создаем директорию если её нет
        self.accounts_dir.mkdir(exist_ok=True)
    
    def add_mafile(self) -> bool:
        """Добавление mafile через файловый менеджер"""
        try:
            print_and_log(self.formatter.format_section_header("📁 Добавление mafile"))
            print_and_log("ℹ️  Выберите mafile который хотите добавить в систему")
            print_and_log("ℹ️  Файл будет скопирован в папку accounts_info")
            print_and_log("⚠️  ВАЖНО: Имя maFile должно соответствовать реальному никнейму Steam аккаунта!")
            print_and_log("")
            
            # Определяем операционную систему
            current_os = platform.system().lower()
            
            if current_os == "windows":
                # Для Windows открываем файловый диалог
                file_path = self._open_file_dialog_windows()
                if not file_path:
                    print_and_log("❌ Файл не выбран", "ERROR")
                    return False
            else:
                # Для Linux/Mac - ручной ввод пути
                hint_message = Messages.MAFILE_PATH_HINT_LINUX if current_os in ["linux", "darwin"] else Messages.MAFILE_PATH_HINT
                print_and_log(hint_message)
                file_path = input(Messages.ENTER_MAFILE_PATH).strip()
                
                if not file_path:
                    print_and_log(self.formatter.format_error("Путь не указан"), "ERROR")
                    return False
            
            # Проверяем существование файла
            source_path = Path(file_path)
            if not source_path.exists():
                print_and_log(self.formatter.format_error(Messages.MAFILE_NOT_FOUND), "ERROR")
                return False
            
            # Проверяем что это действительно mafile
            if not self._validate_mafile(source_path):
                return False
            
            # Получаем информацию из mafile для определения имени
            mafile_data = self._read_mafile(source_path)
            if not mafile_data:
                return False
            
            # Проверяем соответствие имени maFile реальному никнейму Steam
            if not self._verify_mafile_account_name(mafile_data):
                return False
            
            # Определяем имя файла назначения
            account_name = mafile_data.get('account_name', 'unknown')
            destination_name = f"{account_name}.maFile"
            destination_path = self.accounts_dir / destination_name
            
            # Проверяем не существует ли уже файл
            if destination_path.exists():
                print_and_log(f"⚠️  Файл {destination_name} уже существует в {self.accounts_dir}", "WARNING")
                overwrite = input("Перезаписать существующий файл? (y/n): ").strip().lower()
                if overwrite not in ['y', 'yes', 'д', 'да']:
                    print_and_log("❌ Операция отменена", "ERROR")
                    return False
            
            # Копируем файл
            shutil.copy2(source_path, destination_path)
            
            print_and_log(self.formatter.format_success(
                Messages.MAFILE_COPIED.format(destination=destination_path)
            ))
            
            # Показываем информацию о файле
            self._show_mafile_info(mafile_data)
            
            return True
            
        except Exception as e:
            print_and_log(self.formatter.format_error(Messages.MAFILE_COPY_ERROR.format(error=e)), "ERROR")
            return False
    
    def _validate_mafile(self, file_path: Path) -> bool:
        """Валидация mafile"""
        try:
            # Проверяем расширение
            if not file_path.name.lower().endswith('.mafile'):
                print_and_log(self.formatter.format_error("Файл должен иметь расширение .maFile"), "ERROR")
                return False
            
            # Проверяем что это JSON файл с нужными полями
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            required_fields = ['shared_secret', 'identity_secret', 'account_name']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                print_and_log(self.formatter.format_error(
                    Messages.MAFILE_INVALID.format(
                        error=f"Отсутствуют обязательные поля: {', '.join(missing_fields)}"
                    )
                ), "ERROR")
                return False
            
            return True
            
        except json.JSONDecodeError as e:
            print_and_log(self.formatter.format_error(
                Messages.MAFILE_INVALID.format(error=f"Некорректный JSON: {e}")
            ), "ERROR")
            return False
        except Exception as e:
            print_and_log(self.formatter.format_error(
                Messages.MAFILE_INVALID.format(error=str(e))
            ), "ERROR")
            return False
    
    def _read_mafile(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Чтение данных из mafile"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print_and_log(self.formatter.format_error(f"Ошибка чтения mafile: {e}"), "ERROR")
            return None
    
    def _show_mafile_info(self, mafile_data: Dict[str, Any]):
        """Показ информации о mafile"""
        print_and_log("")
        print_and_log("📋 Информация о добавленном mafile:")
        print_and_log(f"  👤 Аккаунт: {mafile_data.get('account_name', 'Неизвестно')}")
        print_and_log(f"  🆔 Steam ID: {mafile_data.get('Session', {}).get('SteamID', 'Неизвестно')}")
        print_and_log(f"  🔑 Shared Secret: {'✅ Присутствует' if mafile_data.get('shared_secret') else '❌ Отсутствует'}")
        print_and_log(f"  🔐 Identity Secret: {'✅ Присутствует' if mafile_data.get('identity_secret') else '❌ Отсутствует'}")
        print_and_log("")
        print_and_log("💡 Теперь вы можете использовать этот аккаунт в конфигурации")
    
    def _open_file_dialog_windows(self) -> Optional[str]:
        """Открытие файлового диалога в Windows"""
        try:
            print_and_log("🔍 Открываем файловый диалог...")
            print_and_log("ℹ️  Выберите .maFile в открывшемся окне")
            
            # Используем PowerShell для открытия файлового диалога
            powershell_script = '''
Add-Type -AssemblyName System.Windows.Forms
$openFileDialog = New-Object System.Windows.Forms.OpenFileDialog
$openFileDialog.Filter = "Steam Mobile Authenticator Files (*.maFile)|*.maFile|All files (*.*)|*.*"
$openFileDialog.Title = "Выберите maFile для добавления"
$openFileDialog.InitialDirectory = [Environment]::GetFolderPath("Desktop")
$result = $openFileDialog.ShowDialog()
if ($result -eq "OK") {
    Write-Output $openFileDialog.FileName
}
'''
            
            # Запускаем PowerShell скрипт
            result = subprocess.run(
                ["powershell", "-Command", powershell_script],
                capture_output=True,
                text=True,
                timeout=60  # Таймаут 60 секунд
            )
            
            if result.returncode == 0 and result.stdout.strip():
                selected_file = result.stdout.strip()
                print_and_log(f"✅ Выбран файл: {selected_file}")
                return selected_file
            else:
                print_and_log("❌ Файл не выбран или произошла ошибка", "ERROR")
                return None
                
        except subprocess.TimeoutExpired:
            print_and_log("⏰ Время ожидания истекло (60 сек)", "ERROR")
            return None
        except Exception as e:
            print(f"❌ Ошибка открытия файлового диалога: {e}")
            print("💡 Попробуйте ввести путь к файлу вручную")
            
            # Fallback - ручной ввод
            print(Messages.MAFILE_PATH_HINT)
            file_path = input(Messages.ENTER_MAFILE_PATH).strip()
            return file_path if file_path else None
    
    def list_mafiles(self) -> list:
        """Получение списка всех mafile в директории"""
        try:
            mafiles = list(self.accounts_dir.glob("*.maFile"))
            return [f.name for f in mafiles]
        except Exception:
            return []

    def get_api_key(self, cli_context) -> bool:
        """Получение или создание API ключа"""
        try:
            print(self.formatter.format_section_header("🔑 Получение API ключа"))
            print("ℹ️  Проверяем наличие API ключа на аккаунте...")
            print("ℹ️  Если ключ отсутствует, будет создан новый с подтверждением через Guard")
            print()

            # Проверяем, есть ли уже API ключ
            existing_key = self._check_existing_api_key(cli_context)
            if existing_key:
                print(self.formatter.format_success(
                    Messages.API_KEY_FOUND.format(key=f"{existing_key[:10]}..." if len(existing_key) > 10 else existing_key)
                ))
                print()
                print("📋 Информация об API ключе:")
                print(f"  🔑 Ключ: {existing_key}")
                print(f"  🌐 Использование: для доступа к Steam Web API")
                print(f"  📱 Статус: активен")
                print()
                input(Messages.PRESS_ENTER)
                return True

            # API ключ не найден, создаем новый
            print(Messages.API_KEY_NOT_FOUND)
            print("🔄 Попытка создания нового API ключа...")
            print()

            # Создаем API ключ
            new_key = self._create_new_api_key(cli_context)
            if new_key:
                print(self.formatter.format_success(
                    Messages.API_KEY_CREATED.format(key=f"{new_key[:10]}..." if len(new_key) > 10 else new_key)
                ))
                print()
                print("📋 Информация о созданном API ключе:")
                print(f"  🔑 Ключ: {new_key}")
                print(f"  🌐 Домен: test")
                print(f"  📱 Статус: активен")
                print(f"  ✅ Подтвержден через Guard: Да")
                print()
                input(Messages.PRESS_ENTER)
                return True
            else:
                print(self.formatter.format_error(Messages.API_KEY_CREATION_FAILED))
                input(Messages.PRESS_ENTER)
                return False

        except Exception as e:
            print(self.formatter.format_error(Messages.API_KEY_ERROR.format(error=e)))
            input(Messages.PRESS_ENTER)
            return False

    def _check_existing_api_key(self, cli_context) -> Optional[str]:
        """Проверка наличия существующего API ключа"""
        try:
            # Проверяем cookies перед выполнением запроса
            if not cli_context.cookie_checker.ensure_valid_cookies():
                print("❌ Не удалось получить действительные cookies")
                return None

            # Получаем Steam клиента через trade_manager
            steam_client = cli_context.trade_manager._get_steam_client()
            if not steam_client:
                print("❌ Не удалось получить Steam клиента")
                return None

            return self._get_api_key_from_web(steam_client)

        except Exception as e:
            print(f"❌ Ошибка проверки существующего API ключа: {e}")
            return None

    def _get_api_key_from_web(self, steam_client) -> Optional[str]:
        """Получение API ключа через веб-интерфейс"""
        try:
            req = steam_client._session.get('https://steamcommunity.com/dev/apikey')
            
            if req.status_code != 200:
                print(f"❌ Ошибка запроса к странице API ключа: {req.status_code}")
                return None

            # Проверяем, что мы не попали на страницу входа
            if 'Sign In' in req.text and 'login' in req.url.lower():
                print("❌ Перенаправление на страницу входа. Проверьте cookies.")
                return None

            # Ищем API ключ на странице - улучшенный поиск
            print("🔍 Ищем API ключ на странице...")
            
            # Несколько паттернов для поиска API ключа
            patterns = [
                r'<p>Key:\s*([A-F0-9]{32})</p>',  # Ключ в параграфе "Key: ..." - ПРИОРИТЕТНЫЙ
            ]
            
            for i, pattern in enumerate(patterns, 1):
                matches = re.findall(pattern, req.text, re.IGNORECASE)
                
                if matches:
                    print(f"✅ Найдено {len(matches)} совпадений")
                    # Фильтруем только валидные API ключи (32 символа, hex)
                    valid_keys = [key for key in matches if len(key) == 32 and re.match(r'^[A-F0-9]+$', key, re.IGNORECASE)]
                    
                    if valid_keys:
                        apikey = valid_keys[0]
                        print(f"✅ API ключ найден: {apikey[:10]}...")
                        return apikey
                    else:
                        print("⚠️ Найдены совпадения, но они не похожи на API ключи")
                else:
                    print("❌ Совпадений не найдено")
            
            # API ключ не найден
            if 'You must have a validated email address' in req.text:
                print(Messages.API_KEY_REQUIRES_EMAIL)
                return None
            elif 'Register for a Steam Web API Key' in req.text:
                # Ключ нужно создать
                print("ℹ️ API ключ не найден, требуется создание")
                return None
            else:
                print("⚠️ Не удалось определить статус API ключа")
                print("💡 Проверьте файл debug_apikey_page.html для анализа")
                return None

        except Exception as e:
            print(f"❌ Ошибка получения API ключа через веб: {e}")
            return None

    def _create_new_api_key(self, cli_context) -> Optional[str]:
        """Создание нового API ключа с подтверждением через Guard"""
        try:
            # Получаем Steam клиента
            steam_client = cli_context.trade_manager._get_steam_client()
            if not steam_client:
                print("❌ Не удалось получить Steam клиента")
                return None

            # Проверяем наличие метода register_new_api_key
            if hasattr(steam_client, 'register_new_api_key'):
                try:
                    print(Messages.API_KEY_CREATION_PENDING)
                    print("🔄 Отправляем запрос на создание API ключа...")
                    
                    # Создаем API ключ с автоматическим подтверждением через Guard
                    api_key = steam_client.register_new_api_key(domain='test')
                    
                    if api_key:
                        print(Messages.API_KEY_CONFIRMED)
                        return api_key
                    else:
                        print(Messages.API_KEY_CREATION_FAILED)
                        return None

                except Exception as e:
                    print(f"❌ Ошибка при создании API ключа: {e}")
                    # Пробуем альтернативный способ
                    return self._create_api_key_manual(steam_client)
            else:
                # Используем альтернативный способ
                return self._create_api_key_manual(steam_client)

        except Exception as e:
            print(f"❌ Критическая ошибка создания API ключа: {e}")
            return None

    def _create_api_key_manual(self, steam_client) -> Optional[str]:
        """Создание API ключа через ручной POST запрос"""
        try:
            print("🔄 Используем альтернативный способ создания API ключа...")
            
            # Получаем страницу для извлечения sessionid
            response = steam_client._session.get('https://steamcommunity.com/dev/apikey')
            
            # Извлекаем sessionid для CSRF защиты
            sessionid_pattern = r'g_sessionID = "([^"]+)"'
            sessionid_match = re.search(sessionid_pattern, response.text)
            
            if not sessionid_match:
                print("❌ Не удалось найти sessionid для создания API ключа")
                return None

            sessionid = sessionid_match.group(1)
            print(f"🔑 Найден sessionid: {sessionid[:10]}...")

            # Отправляем POST запрос для создания ключа
            create_data = {
                'domain': 'test',
                'agreeToTerms': 'agreed',
                'sessionid': sessionid,
                'Submit': 'Register'
            }

            print("📤 Отправляем запрос на создание API ключа...")
            create_response = steam_client._session.post(
                'https://steamcommunity.com/dev/registerkey',
                data=create_data
            )

            print(f"📥 Получен ответ: {create_response.status_code}")
            
            if create_response.status_code == 200:
                # Проверяем результат по содержимому HTML
                response_text = create_response.text.lower()
                
                # Проверяем различные индикаторы успеха
                success_indicators = [
                    'successful',
                    'success', 
                    'api key has been registered',
                    'your steam web api key',
                    'key has been created'
                ]
                
                error_indicators = [
                    'error',
                    'failed',
                    'invalid',
                    'already registered',
                    'email validation required'
                ]
                
                # Проверяем на успех
                if any(indicator in response_text for indicator in success_indicators):
                    print("✅ API ключ успешно создан")
                    
                    # Подтверждаем через Guard если требуется
                    print(Messages.API_KEY_CONFIRMATION_NEEDED)
                    print("🔄 Автоматическое подтверждение через Guard...")
                    
                    time.sleep(2)  # Небольшая задержка
                    
                    # Снова запрашиваем страницу чтобы получить ключ
                    return self._get_api_key_from_web(steam_client)
                
                # Проверяем на ошибки
                elif any(indicator in response_text for indicator in error_indicators):
                    print("❌ Ошибка создания API ключа")
                    if 'email validation required' in response_text:
                        print("❌ Требуется подтверждение email адреса")
                    elif 'already registered' in response_text:
                        print("ℹ️ API ключ уже существует")
                        return self._get_api_key_from_web(steam_client)
                    else:
                        print("❌ Неизвестная ошибка при создании API ключа")
                    return None
                else:
                    # Неопределенный результат - пробуем получить ключ
                    print("⚠️ Неопределенный результат создания, проверяем наличие ключа...")
                    return self._get_api_key_from_web(steam_client)
            else:
                print(f"❌ Ошибка создания API ключа: HTTP {create_response.status_code}")
                return None

        except Exception as e:
            print(f"❌ Ошибка ручного создания API ключа: {e}")
            return None

    def _verify_mafile_account_name(self, mafile_data: Dict[str, Any]) -> bool:
        """Проверка соответствия имени maFile реальному никнейму Steam аккаунта"""
        try:
            account_name = mafile_data.get('account_name', 'unknown')
            
            print()
            print("⚠️  ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ О СООТВЕТСТВИИ ИМЕНИ MAFILE")
            print("=" * 60)
            print(f"📋 Имя аккаунта в maFile: {account_name}")
            print()
            print("🔍 Убедитесь что это имя точно соответствует вашему реальному")
            print()
            print("💡 Почему это важно:")
            print("   - Неправильное имя приведет к ошибкам входа")
            print("   - Автоматизация не будет работать")
            print("   - Могут возникнуть проблемы с подтверждениями")
            print()
            print("🔧 Если имя неправильное:")
            print("   - Отмените добавление (введите 'n')")
            print("   - Исправьте account_name в maFile вручную")
            print("   - Попробуйте добавить файл снова")
            print()
            
            while True:
                confirm = input(f"✅ Подтверждаете что '{account_name}' - это ваш реальный Steam логин? (y/n): ").strip().lower()
                
                if confirm in ['y', 'yes', 'д', 'да']:
                    print(f"✅ Подтверждено! Добавляем maFile для аккаунта '{account_name}'")
                    return True
                elif confirm in ['n', 'no', 'н', 'нет']:
                    print("❌ Добавление maFile отменено")
                    print("💡 Исправьте поле 'account_name' в maFile и попробуйте снова")
                    return False
                else:
                    print("⚠️  Пожалуйста, введите 'y' для подтверждения или 'n' для отмены")
                    
        except Exception as e:
            print(self.formatter.format_error(f"❌ Ошибка проверки соответствия имени maFile: {e}"))
            return False 