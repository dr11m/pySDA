#!/usr/bin/env python3
"""
Управление конфигурацией для CLI интерфейса
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import copy

from .constants import Config, Messages
from .display_formatter import DisplayFormatter
from ruamel.yaml import YAML
from src.utils.logger_setup import logger


class ConfigManager:
    """Менеджер конфигурации"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or Config.DEFAULT_CONFIG_PATH
        self.config_data: Optional[Dict[str, Any]] = None
        self.accounts_settings: Optional[Dict[str, Any]] = {}
        self.active_account_config: Optional[Dict[str, Any]] = None
        self.selected_account_name = None
        self.current_account_config = {}
        self.yaml = YAML()

    def clone(self) -> 'ConfigManager':
        """Создает и возвращает клон текущего экземпляра ConfigManager."""
        new_manager = ConfigManager(self.config_path)
        # Копируем основные данные, но сбрасываем состояние выбора аккаунта
        new_manager.config_data = copy.deepcopy(self.config_data)
        new_manager.accounts_settings = copy.deepcopy(self.accounts_settings)
        new_manager.active_account_config = copy.deepcopy(self.active_account_config)
        new_manager.selected_account_name = None
        new_manager.current_account_config = {}
        return new_manager

    def load_config(self) -> bool:
        """
        Загрузить конфигурацию из файла
        
        Returns:
            bool: True если конфигурация успешно загружена
        """
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                print(DisplayFormatter.format_error(f"{Messages.CONFIG_NOT_FOUND}: {self.config_path}"))
                return False
            
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config_data = self.yaml.load(f)
            self.default_config = self.config_data.get('default', {})
            self.accounts_settings = self.config_data.get('accounts', {})
            return True
            
        except Exception as e:
            print(DisplayFormatter.format_error("Ошибка загрузки конфигурации", e))
            return False

    def select_account(self, account_name: str) -> bool:
        """
        Выбрать аккаунт и загрузить его настройки.
        Конфигурация аккаунта должна быть полностью определена в секции 'accounts'.
        """
        account_specific_settings = self.accounts_settings.get(account_name)
        
        if not account_specific_settings:
            self.active_account_config = None
            return False
        
        self.active_account_config = account_specific_settings
        return True

    def validate_config(self) -> bool:
        """
        Проверить корректность конфигурации для активного аккаунта.
        
        Returns:
            bool: True если конфигурация корректна
        """
        if not self.active_account_config:
            print(DisplayFormatter.format_error("Конфигурация для аккаунта не загружена"))
            return False
        
        missing_fields = []
        for field in Config.REQUIRED_FIELDS:
            if not self.active_account_config.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            error_msg = f"Отсутствуют обязательные поля в конфигурации аккаунта: {', '.join(missing_fields)}"
            print(DisplayFormatter.format_error(error_msg))
            return False
        
        return True
    
    def get(self, key: str, default_value: Any = None) -> Any:
        """
        Получение значения из конфигурации.
        Сначала ищет на глобальном уровне, затем в конфигурации выбранного аккаунта,
        затем в 'default', и в конце возвращает default_value.
        """
        # 1. Поиск на глобальном уровне
        if self.config_data and key in self.config_data:
            return self.config_data[key]
            
        # 2. Поиск в конфигурации активного аккаунта
        if self.active_account_config and key in self.active_account_config:
            return self.active_account_config[key]

        # 3. Поиск в секции 'default'  
        if hasattr(self, 'default_config') and self.default_config and key in self.default_config:
            return self.default_config[key]

        return default_value

    def get_full_config(self) -> Dict[str, Any]:
        """Получить полную конфигурацию"""
        return self.config_data or {}
    
    def is_loaded(self) -> bool:
        """Проверить, загружена ли конфигурация"""
        return self.config_data is not None
    
    def reload(self) -> bool:
        """Перезагрузить конфигурацию"""
        self.config_data = None
        self.accounts_settings = {}
        self.active_account_config = None
        return self.load_config()
    
    def get_all_account_names(self) -> List[str]:
        """Получить список имен всех аккаунтов"""
        if not self.accounts_settings:
            return []
        return list(self.accounts_settings.keys())
    
    def get_account_display_name(self, account_name: str) -> str:
        """
        Получить отображаемое имя аккаунта с описанием
        
        Args:
            account_name: Имя аккаунта
            
        Returns:
            Строка вида "username - description" или просто "username"
        """
        if not self.accounts_settings or account_name not in self.accounts_settings:
            return account_name
            
        account_config = self.accounts_settings[account_name]
        description = account_config.get('description')
        
        if description:
            return f"{account_name} - {description}"
        else:
            return account_name
    
    def __str__(self) -> str:
        """Строковое представление конфигурации"""
        if not self.is_loaded():
            return "Конфигурация не загружена"
        
        username = self.get('username', 'N/A')
        steam_id = self.get('steam_id', 'N/A')
        
        return f"Активная конфигурация для: {username} (ID: {steam_id})" 