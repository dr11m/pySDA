#!/usr/bin/env python3
"""
Steam Session Manager - Безопасное управление Steam сессиями
Автор: AI Assistant
Версия: 1.0.0
"""

import argparse
import json
from src.utils.logger_setup import logger
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any
import signal
import getpass
import traceback

import requests
from cryptography.fernet import Fernet
import keyring

from .client import SteamClient
from .guard import generate_one_time_code, load_steam_guard
from .models import SteamUrl

# logger уже импортирован из logger_setup

class SecureSessionManager:
    """Безопасный менеджер Steam сессий с автообновлением"""
    
    def __init__(self, username: str, check_interval: int = 300):
        """
        Инициализация менеджера сессий
        
        Args:
            username: Steam username
            check_interval: Интервал проверки сессии в секундах (по умолчанию 5 минут)
        """
        self.username = username
        self.check_interval = check_interval
        self.running = False
        self.client: Optional[SteamClient] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.last_check = datetime.now()
        
        # Настройка логирования
        self._setup_logging()  # Пустая функция, логирование через loguru
        
        # Безопасное хранение данных
        self.data_dir = Path.home() / ".steampy" / "sessions"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Ключ шифрования для данных сессии
        self.encryption_key = self._get_or_create_encryption_key()
        
    def _setup_logging(self):
        """Логирование уже настроено через loguru в logger_setup.py"""
        pass
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Получение или создание ключа шифрования"""
        try:
            # Пытаемся получить ключ из системного хранилища
            key_str = keyring.get_password("steampy_session_manager", f"{self.username}_encryption_key")
            if key_str:
                return key_str.encode()
            
            # Создаем новый ключ
            key = Fernet.generate_key()
            keyring.set_password("steampy_session_manager", f"{self.username}_encryption_key", key.decode())
            self.logger.info("Создан новый ключ шифрования")
            return key
            
        except Exception as e:
            self.logger.warning(f"Не удалось использовать системное хранилище ключей: {e}")
            # Fallback: файловое хранение ключа (менее безопасно)
            key_file = self.data_dir / f"{self.username}.key"
            if key_file.exists():
                return key_file.read_bytes()
            
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            key_file.chmod(0o600)  # Только владелец может читать
            return key
    
    def _encrypt_data(self, data: Dict[str, Any]) -> bytes:
        """Шифрование данных"""
        fernet = Fernet(self.encryption_key)
        json_data = json.dumps(data, default=str).encode()
        return fernet.encrypt(json_data)
    
    def _decrypt_data(self, encrypted_data: bytes) -> Dict[str, Any]:
        """Расшифровка данных"""
        fernet = Fernet(self.encryption_key)
        json_data = fernet.decrypt(encrypted_data)
        return json.loads(json_data.decode())
    
    def _save_session_secure(self, session_data: Dict[str, Any]) -> None:
        """Безопасное сохранение данных сессии"""
        try:
            session_file = self.data_dir / f"{self.username}.session"
            encrypted_data = self._encrypt_data({
                'cookies': session_data,
                'timestamp': datetime.now().isoformat(),
                'username': self.username
            })
            
            session_file.write_bytes(encrypted_data)
            session_file.chmod(0o600)
            self.logger.info("Сессия сохранена безопасно")
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения сессии: {e}")
    
    def _load_session_secure(self) -> Optional[Dict[str, Any]]:
        """Безопасная загрузка данных сессии"""
        try:
            session_file = self.data_dir / f"{self.username}.session"
            if not session_file.exists():
                return None
            
            encrypted_data = session_file.read_bytes()
            data = self._decrypt_data(encrypted_data)
            
            # Проверяем возраст сессии
            session_time = datetime.fromisoformat(data['timestamp'])
            if datetime.now() - session_time > timedelta(hours=24):
                self.logger.warning("Сессия устарела (>24 часов)")
                return None
            
            return data['cookies']
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки сессии: {e}")
            return None
    
    def _get_credentials(self) -> tuple[str, str, str]:
        """Безопасное получение credentials"""
        try:
            password = keyring.get_password("steampy", f"{self.username}_password")
            api_key = keyring.get_password("steampy", f"{self.username}_api_key")
            guard_path = keyring.get_password("steampy", f"{self.username}_guard_path")
            
            if not all([password, api_key, guard_path]):
                raise ValueError("Credentials не найдены в системном хранилище")
            
            return password, api_key, guard_path
            
        except Exception as e:
            self.logger.error(f"Ошибка получения credentials: {e}")
            raise
    
    def store_credentials(self, password: str, api_key: str, guard_path: str) -> None:
        """Безопасное сохранение credentials"""
        try:
            keyring.set_password("steampy", f"{self.username}_password", password)
            keyring.set_password("steampy", f"{self.username}_api_key", api_key)
            keyring.set_password("steampy", f"{self.username}_guard_path", guard_path)
            self.logger.info("Credentials сохранены в системном хранилище")
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения credentials: {e}")
            raise
    
    def is_session_valid(self) -> bool:
        """Проверка актуальности сессии"""
        if not self.client:
            return False
        
        try:
            # Безопасная проверка без вывода в консоль
            response = self.client._session.get(
                SteamUrl.COMMUNITY_URL,
                timeout=10,
                headers={'User-Agent': 'Steam Client'}
            )
            
            is_valid = (
                response.status_code == 200 and 
                self.username.lower() in response.text.lower()
            )
            
            if is_valid:
                self.logger.debug("Сессия актуальна")
            else:
                self.logger.warning("Сессия неактуальна")
            
            return is_valid
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки сессии: {e}")
            return False
    
    def login(self, force_refresh: bool = False) -> bool:
        """Вход в Steam с созданием новой сессии"""
        try:
            password, api_key, guard_path = self._get_credentials()
            
            # Загружаем существующую сессию если не принудительное обновление
            session_data = None if force_refresh else self._load_session_secure()
            
            self.client = SteamClient(
                api_key="FDACB8261DBA8547548C54F7C7D1F951",
                username=self.username,
                password=password,
                steam_guard=guard_path
            )
            
            # Восстанавливаем cookies если есть
            if session_data:
                for name, value in session_data.items():
                    self.client._session.cookies[name] = value
                
                # Проверяем актуальность
                if self.is_session_valid():
                    self.logger.info("Сессия восстановлена из сохраненных данных")
                    return True
            
            # Создаем новую сессию
            self.logger.info("Создание новой сессии...")
            self.client.login_if_need_to()
            
            # Сохраняем новую сессию
            cookies = self.client._session.cookies.get_dict()
            self._save_session_secure(cookies)
            
            self.logger.info("Успешный вход в Steam")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка входа в Steam: {e}")
            return False
    
    def get_2fa_code(self) -> Optional[str]:
        """Получение 2FA кода"""
        try:
            _, _, guard_path = self._get_credentials()
            guard_data = load_steam_guard(guard_path)
            code = generate_one_time_code(guard_data['shared_secret'])
            self.logger.info("2FA код сгенерирован")
            return code
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации 2FA кода: {e}")
            return None
    
    def get_current_cookies(self) -> Optional[Dict[str, str]]:
        """Получение текущих cookies"""
        if not self.client:
            session_data = self._load_session_secure()
            return session_data if session_data else None
        
        return self.client._session.cookies.get_dict()
    
    def refresh_session(self) -> bool:
        """Принудительное обновление сессии"""
        self.logger.info("Принудительное обновление сессии...")
        return self.login(force_refresh=True)
    
    def _monitor_session(self) -> None:
        """Мониторинг сессии в отдельном потоке"""
        while self.running:
            try:
                if not self.is_session_valid():
                    self.logger.warning("Сессия неактуальна, обновляем...")
                    if self.login():
                        self.logger.info("Сессия обновлена")
                    else:
                        self.logger.error("Не удалось обновить сессию")
                
                self.last_check = datetime.now()
                
                # Ждем следующую проверку
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Ошибка в мониторинге сессии: {e}")
                time.sleep(60)  # Пауза при ошибке
    
    def start_monitoring(self) -> None:
        """Запуск мониторинга сессии"""
        if self.running:
            self.logger.warning("Мониторинг уже запущен")
            return
        
        if not self.login():
            raise RuntimeError("Не удалось войти в Steam")
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_session, daemon=True)
        self.monitor_thread.start()
        self.logger.info(f"Мониторинг сессии запущен (интервал: {self.check_interval}с)")
    
    def stop_monitoring(self) -> None:
        """Остановка мониторинга сессии"""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        self.logger.info("Мониторинг сессии остановлен")
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса менеджера"""
        return {
            'username': self.username,
            'running': self.running,
            'check_interval': self.check_interval,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'session_valid': self.is_session_valid() if self.client else False,
            'has_saved_session': self._load_session_secure() is not None
        }


def create_cli() -> argparse.ArgumentParser:
    """Создание CLI интерфейса"""
    parser = argparse.ArgumentParser(
        description="Steam Session Manager - Безопасное управление Steam сессиями",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s --username myuser --setup-credentials
  %(prog)s --username myuser --get-2fa
  %(prog)s --username myuser --get-cookies
  %(prog)s --username myuser --refresh
  %(prog)s --username myuser --monitor --interval 300
  %(prog)s --username myuser --status
        """
    )
    
    parser.add_argument(
        '--username', '-u',
        required=True,
        help='Steam username'
    )
    
    parser.add_argument(
        '--setup-credentials',
        action='store_true',
        help='Настройка credentials (пароль, API ключ, путь к guard файлу)'
    )
    
    parser.add_argument(
        '--get-2fa',
        action='store_true',
        help='Получить 2FA код'
    )
    
    parser.add_argument(
        '--get-cookies',
        action='store_true',
        help='Получить текущие cookies'
    )
    
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='Принудительно обновить сессию'
    )
    
    parser.add_argument(
        '--monitor',
        action='store_true',
        help='Запустить мониторинг сессии'
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=300,
        help='Интервал проверки сессии в секундах (по умолчанию: 300)'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Показать статус менеджера'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )
    
    return parser


def setup_credentials_interactive(manager: SecureSessionManager) -> None:
    """Интерактивная настройка credentials"""
    print(f"Настройка credentials для пользователя: {manager.username}")
    print("ВНИМАНИЕ: Данные будут сохранены в системном хранилище ключей")
    
    try:
        password = getpass.getpass("Пароль Steam: ")
        api_key = input("API ключ Steam (получить на https://steamcommunity.com/dev/apikey): ")
        guard_path = input("Путь к .mafile (Steam Guard): ")
        
        # Проверяем файл guard
        if not Path(guard_path).exists():
            print(f"ОШИБКА: Файл {guard_path} не найден")
            return
        
        manager.store_credentials(password, api_key, guard_path)
        print("✓ Credentials успешно сохранены")
        
    except KeyboardInterrupt:
        print("\nОтменено пользователем")
    except Exception as e:
        print(f"ОШИБКА: {e}")


def signal_handler(signum, frame, manager):
    """Обработчик сигналов для корректного завершения"""
    print(f"\nПолучен сигнал {signum}, завершение работы...")
    manager.stop_monitoring()
    sys.exit(0)


def main():
    """Главная функция CLI"""
    parser = create_cli()
    args = parser.parse_args()
    
    # Настройка уровня логирования
    if args.verbose:
        logger.info("Verbose режим включен")
    
    try:
        manager = SecureSessionManager(args.username, args.interval)
        
        # Обработчик сигналов для мониторинга
        if args.monitor:
            signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, manager))
            signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, manager))
        
        # Выполнение команд
        if args.setup_credentials:
            setup_credentials_interactive(manager)
            
        elif args.get_2fa:
            code = manager.get_2fa_code()
            if code:
                print(f"2FA код: {code}")
            else:
                print("ОШИБКА: Не удалось получить 2FA код")
                sys.exit(1)
                
        elif args.get_cookies:
            cookies = manager.get_current_cookies()
            if cookies:
                print("Текущие cookies:")
                for name, value in cookies.items():
                    print(f"  {name}: {value[:20]}...")
            else:
                print("Cookies не найдены")
                
        elif args.refresh:
            if manager.refresh_session():
                print("✓ Сессия обновлена")
            else:
                print("ОШИБКА: Не удалось обновить сессию")
                sys.exit(1)
                
        elif args.monitor:
            print(f"Запуск мониторинга для {args.username} (интервал: {args.interval}с)")
            print("Нажмите Ctrl+C для остановки")
            
            manager.start_monitoring()
            
            try:
                while manager.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                manager.stop_monitoring()
                print("Мониторинг остановлен")
                
        elif args.status:
            status = manager.get_status()
            print("Статус менеджера сессий:")
            for key, value in status.items():
                print(f"  {key}: {value}")
                
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"ОШИБКА: {e}")
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 
