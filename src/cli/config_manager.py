#!/usr/bin/env python3
"""
Управление конфигурацией для CLI интерфейса
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional

from .constants import Config, Messages
from .display_formatter import DisplayFormatter


class ConfigManager:
    """Менеджер конфигурации"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or Config.DEFAULT_CONFIG_PATH
        self.config_data: Optional[Dict[str, Any]] = None
        self.steam_config: Optional[Dict[str, Any]] = None
    
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
                self.config_data = yaml.safe_load(f)
            
            if 'steam' not in self.config_data:
                print(DisplayFormatter.format_error("Секция 'steam' не найдена в конфигурации"))
                return False
            
            self.steam_config = self.config_data['steam']
            return True
            
        except Exception as e:
            print(DisplayFormatter.format_error("Ошибка загрузки конфигурации", e))
            return False
    
    def validate_config(self) -> bool:
        """
        Проверить корректность конфигурации
        
        Returns:
            bool: True если конфигурация корректна
        """
        if not self.steam_config:
            print(DisplayFormatter.format_error("Конфигурация не загружена"))
            return False
        
        missing_fields = []
        for field in Config.REQUIRED_FIELDS:
            if not self.steam_config.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            error_msg = f"Отсутствуют обязательные поля: {', '.join(missing_fields)}"
            print(DisplayFormatter.format_error(error_msg))
            return False
        
        return True
    
    def get_username(self) -> Optional[str]:
        """Получить имя пользователя"""
        return self.steam_config.get('username') if self.steam_config else None
    
    def get_password(self) -> Optional[str]:
        """Получить пароль"""
        return self.steam_config.get('password') if self.steam_config else None
    
    def get_mafile_path(self) -> Optional[str]:
        """Получить путь к mafile"""
        return self.steam_config.get('mafile_path') if self.steam_config else None
    
    def get_steam_id(self) -> Optional[str]:
        """Получить Steam ID"""
        return self.steam_config.get('steam_id') if self.steam_config else None
    
    def get_proxy_list(self) -> Optional[list]:
        """Получить список прокси"""
        return self.steam_config.get('proxies') if self.steam_config else None
    
    def get_accounts_dir(self) -> str:
        """Получить директорию для аккаунтов"""
        return self.steam_config.get('accounts_dir', Config.ACCOUNTS_DIR)
    
    def get_steam_config(self) -> Dict[str, Any]:
        """Получить всю конфигурацию Steam"""
        return self.steam_config or {}
    
    def get_full_config(self) -> Dict[str, Any]:
        """Получить полную конфигурацию"""
        return self.config_data or {}
    
    def is_loaded(self) -> bool:
        """Проверить, загружена ли конфигурация"""
        return self.config_data is not None and self.steam_config is not None
    
    def reload(self) -> bool:
        """Перезагрузить конфигурацию"""
        self.config_data = None
        self.steam_config = None
        return self.load_config() and self.validate_config()
    
    def __str__(self) -> str:
        """Строковое представление конфигурации"""
        if not self.is_loaded():
            return "Конфигурация не загружена"
        
        username = self.get_username()
        steam_id = self.get_steam_id()
        proxy_count = len(self.get_proxy_list() or [])
        
        return f"Конфигурация: {username} (ID: {steam_id}), прокси: {proxy_count}" 