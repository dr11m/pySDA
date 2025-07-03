#!/usr/bin/env python3
"""
Steam Configuration Manager - Управление конфигурацией аккаунтов
"""

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any
from src.utils.logger_setup import logger
from cryptography.fernet import Fernet
import keyring


@dataclass
class AccountConfig:
    """Конфигурация для отдельного аккаунта"""
    name: str
    password: str = ""
    api_key: str = ""
    mafile_path: str = ""
    seconds_to_check_session: int = 300
    allowed_to_check_and_accept_new_trades: bool = True
    seconds_to_check_trades: int = 60
    accept_every_accepted_on_web_trade: bool = False
    accept_every_free_trade: bool = False
    
    def __post_init__(self):
        """Валидация параметров"""
        if not self.name:
            raise ValueError("Name не может быть пустым")
        if self.seconds_to_check_session < 30:
            raise ValueError("seconds_to_check_session должно быть не менее 30 секунд")
        if self.seconds_to_check_trades < 10:
            raise ValueError("seconds_to_check_trades должно быть не менее 10 секунд")
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccountConfig':
        """Создание из словаря"""
        return cls(**data)


class ConfigManager:
    """Менеджер конфигурации для управления настройками аккаунтов"""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Инициализация менеджера конфигурации
        
        Args:
            config_dir: Директория для конфигурационных файлов
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / ".steampy" / "config"
        
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "accounts.json"
        
        # Настройка логирования
        self._setup_logging()  # Пустая функция, логирование через loguru
        
        # Загружаем конфигурацию
        self.accounts: Dict[str, AccountConfig] = {}
        self._load_config()
    
    def _setup_logging(self):
        """Логирование уже настроено через loguru в logger_setup.py"""
        pass
    
    def _load_config(self) -> None:
        """Загрузка конфигурации из файла"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for name, account_data in data.get('accounts', {}).items():
                    try:
                        self.accounts[name] = AccountConfig.from_dict(account_data)
                    except Exception as e:
                        logger.error(f"Ошибка загрузки конфига для {name}: {e}")
                
                logger.info(f"Загружено {len(self.accounts)} аккаунтов")
        
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            self.accounts = {}
    
    def _save_config(self) -> None:
        """Сохранение конфигурации в файл"""
        try:
            config_data = {
                'accounts': {
                    name: account.to_dict() 
                    for name, account in self.accounts.items()
                }
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            # Устанавливаем права доступа только для владельца
            self.config_file.chmod(0o600)
            logger.info("Конфигурация сохранена")
        
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
            raise
    
    def add_account(self, account: AccountConfig) -> None:
        """
        Добавление нового аккаунта
        
        Args:
            account: Конфигурация аккаунта
        """
        if account.name in self.accounts:
            raise ValueError(f"Аккаунт {account.name} уже существует")
        
        self.accounts[account.name] = account
        self._save_config()
        self.logger.info(f"Добавлен аккаунт: {account.name}")
    
    def update_account(self, name: str, **kwargs) -> None:
        """
        Обновление параметров аккаунта
        
        Args:
            name: Имя аккаунта
            **kwargs: Параметры для обновления
        """
        if name not in self.accounts:
            raise ValueError(f"Аккаунт {name} не найден")
        
        account = self.accounts[name]
        updated_data = account.to_dict()
        updated_data.update(kwargs)
        
        # Валидируем новые данные
        new_account = AccountConfig.from_dict(updated_data)
        self.accounts[name] = new_account
        
        self._save_config()
        self.logger.info(f"Обновлен аккаунт: {name}")
    
    def remove_account(self, name: str) -> None:
        """
        Удаление аккаунта
        
        Args:
            name: Имя аккаунта
        """
        if name not in self.accounts:
            raise ValueError(f"Аккаунт {name} не найден")
        
        del self.accounts[name]
        self._save_config()
        self.logger.info(f"Удален аккаунт: {name}")
    
    def get_account(self, name: str) -> AccountConfig:
        """
        Получение конфигурации аккаунта
        
        Args:
            name: Имя аккаунта
            
        Returns:
            Конфигурация аккаунта
        """
        if name not in self.accounts:
            raise ValueError(f"Аккаунт {name} не найден")
        
        return self.accounts[name]
    
    def list_accounts(self) -> List[str]:
        """Получение списка всех аккаунтов"""
        return list(self.accounts.keys())
    
    def get_all_accounts(self) -> Dict[str, AccountConfig]:
        """Получение всех конфигураций аккаунтов"""
        return self.accounts.copy()
    
    def store_sensitive_data(self, account_name: str, password: str = None, 
                           api_key: str = None) -> None:
        """
        Безопасное сохранение чувствительных данных в системном хранилище
        
        Args:
            account_name: Имя аккаунта
            password: Пароль (опционально)
            api_key: API ключ (опционально)
        """
        try:
            if password:
                keyring.set_password("steampy", f"{account_name}_password", password)
            if api_key:
                keyring.set_password("steampy", f"{account_name}_api_key", api_key)
            
            self.logger.info(f"Чувствительные данные сохранены для {account_name}")
        
        except Exception as e:
            self.logger.error(f"Ошибка сохранения чувствительных данных: {e}")
            raise
    
    def get_sensitive_data(self, account_name: str) -> tuple[Optional[str], Optional[str]]:
        """
        Получение чувствительных данных из системного хранилища
        
        Args:
            account_name: Имя аккаунта
            
        Returns:
            Кортеж (password, api_key)
        """
        try:
            password = keyring.get_password("steampy", f"{account_name}_password")
            api_key = keyring.get_password("steampy", f"{account_name}_api_key")
            return password, api_key
        
        except Exception as e:
            self.logger.error(f"Ошибка получения чувствительных данных: {e}")
            return None, None
    
    def validate_config(self) -> Dict[str, List[str]]:
        """
        Валидация всех конфигураций
        
        Returns:
            Словарь с ошибками валидации для каждого аккаунта
        """
        errors = {}
        
        for name, account in self.accounts.items():
            account_errors = []
            
            # Проверяем наличие файла mafile
            if account.mafile_path and not Path(account.mafile_path).exists():
                account_errors.append(f"mafile не найден: {account.mafile_path}")
            
            # Проверяем чувствительные данные
            password, api_key = self.get_sensitive_data(name)
            if not password:
                account_errors.append("Пароль не установлен в системном хранилище")
            if not api_key:
                account_errors.append("API ключ не установлен в системном хранилище")
            
            if account_errors:
                errors[name] = account_errors
        
        return errors
    
    def export_config(self, file_path: str, include_sensitive: bool = False) -> None:
        """
        Экспорт конфигурации в файл
        
        Args:
            file_path: Путь к файлу для экспорта
            include_sensitive: Включить ли чувствительные данные (НЕ РЕКОМЕНДУЕТСЯ)
        """
        export_data = {}
        
        for name, account in self.accounts.items():
            account_data = account.to_dict()
            
            if include_sensitive:
                password, api_key = self.get_sensitive_data(name)
                if password:
                    account_data['password'] = password
                if api_key:
                    account_data['api_key'] = api_key
            
            export_data[name] = account_data
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Конфигурация экспортирована в {file_path}")
    
    def import_config(self, file_path: str, overwrite: bool = False) -> None:
        """
        Импорт конфигурации из файла
        
        Args:
            file_path: Путь к файлу для импорта
            overwrite: Перезаписывать ли существующие аккаунты
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)
        
        imported_count = 0
        
        for name, account_data in import_data.items():
            if name in self.accounts and not overwrite:
                self.logger.warning(f"Пропускаем существующий аккаунт: {name}")
                continue
            
            try:
                # Извлекаем чувствительные данные для отдельного сохранения
                password = account_data.pop('password', None)
                api_key = account_data.pop('api_key', None)
                
                account = AccountConfig.from_dict(account_data)
                self.accounts[name] = account
                
                # Сохраняем чувствительные данные отдельно
                if password or api_key:
                    self.store_sensitive_data(name, password, api_key)
                
                imported_count += 1
                
            except Exception as e:
                self.logger.error(f"Ошибка импорта аккаунта {name}: {e}")
        
        if imported_count > 0:
            self._save_config()
            self.logger.info(f"Импортировано {imported_count} аккаунтов") 
