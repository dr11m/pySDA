#!/usr/bin/env python3
"""
Steam Account Manager - Интегрированное управление аккаунтами Steam
"""

import asyncio
from src.utils.logger_setup import logger
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import concurrent.futures

from .client import SteamClient
from .config import ConfigManager, AccountConfig
from .session_manager import SecureSessionManager
from .models import TradeOfferState, GameOptions
from .exceptions import ApiException


class AccountManager:
    """Менеджер для автоматизированного управления множественными Steam аккаунтами"""
    
    def __init__(self, config_manager: ConfigManager):
        """
        Инициализация менеджера аккаунтов
        
        Args:
            config_manager: Менеджер конфигурации
        """
        self.config_manager = config_manager
        self.session_managers: Dict[str, SecureSessionManager] = {}
        self.clients: Dict[str, SteamClient] = {}
        self.running_tasks: Dict[str, threading.Thread] = {}
        self.is_running = False
        
        # Настройка логирования
        self.logger = self._setup_logging()
        
        # Инициализируем session managers для всех аккаунтов
        self._initialize_session_managers()
    
    def _setup_logging(self):
        """Логирование настроено через loguru в logger_setup.py"""
        return logger
    
    def _initialize_session_managers(self) -> None:
        """Инициализация session managers для всех аккаунтов"""
        for account_name, config in self.config_manager.get_all_accounts().items():
            session_manager = SecureSessionManager(
                username=account_name,
                check_interval=config.seconds_to_check_session
            )
            self.session_managers[account_name] = session_manager
            
            # Получаем чувствительные данные и сохраняем их в session_manager
            password, api_key = self.config_manager.get_sensitive_data(account_name)
            if password and api_key:
                try:
                    session_manager.store_credentials(password, api_key, config.mafile_path)
                except Exception as e:
                    self.logger.error(f"Ошибка настройки credentials для {account_name}: {e}")
    
    def add_account_from_config(self, account_name: str) -> None:
        """
        Добавление нового аккаунта на основе конфигурации
        
        Args:
            account_name: Имя аккаунта
        """
        if account_name in self.session_managers:
            self.logger.warning(f"Аккаунт {account_name} уже инициализирован")
            return
        
        config = self.config_manager.get_account(account_name)
        session_manager = SecureSessionManager(
            username=account_name,
            check_interval=config.seconds_to_check_session
        )
        self.session_managers[account_name] = session_manager
        
        # Настройка credentials
        password, api_key = self.config_manager.get_sensitive_data(account_name)
        if password and api_key:
            session_manager.store_credentials(password, api_key, config.mafile_path)
        
        self.logger.info(f"Добавлен аккаунт: {account_name}")
    
    def remove_account(self, account_name: str) -> None:
        """
        Удаление аккаунта из менеджера
        
        Args:
            account_name: Имя аккаунта
        """
        # Останавливаем задачи аккаунта
        self._stop_account_tasks(account_name)
        
        # Удаляем из менеджеров
        if account_name in self.session_managers:
            del self.session_managers[account_name]
        if account_name in self.clients:
            del self.clients[account_name]
        
        self.logger.info(f"Удален аккаунт: {account_name}")
    
    def login_account(self, account_name: str, force_refresh: bool = False) -> bool:
        """
        Вход в аккаунт
        
        Args:
            account_name: Имя аккаунта
            force_refresh: Принудительное обновление сессии
            
        Returns:
            True если вход успешен
        """
        if account_name not in self.session_managers:
            self.logger.error(f"Аккаунт {account_name} не найден")
            return False
        
        session_manager = self.session_managers[account_name]
        
        try:
            if session_manager.login(force_refresh):
                # Создаем Steam клиент
                if session_manager.client:
                    self.clients[account_name] = session_manager.client
                    self.logger.info(f"Успешный вход для {account_name}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка входа для {account_name}: {e}")
            return False
    
    def logout_account(self, account_name: str) -> None:
        """
        Выход из аккаунта
        
        Args:
            account_name: Имя аккаунта
        """
        self._stop_account_tasks(account_name)
        
        if account_name in self.session_managers:
            self.session_managers[account_name].stop_monitoring()
        
        if account_name in self.clients:
            try:
                self.clients[account_name].logout()
            except Exception as e:
                self.logger.error(f"Ошибка выхода для {account_name}: {e}")
            finally:
                del self.clients[account_name]
        
        self.logger.info(f"Выход из аккаунта: {account_name}")
    
    def start_account_monitoring(self, account_name: str) -> None:
        """
        Запуск мониторинга для аккаунта
        
        Args:
            account_name: Имя аккаунта
        """
        if account_name not in self.session_managers:
            self.logger.error(f"Аккаунт {account_name} не найден")
            return
        
        config = self.config_manager.get_account(account_name)
        
        # Запускаем мониторинг сессии
        session_manager = self.session_managers[account_name]
        session_manager.start_monitoring()
        
        # Запускаем мониторинг трейдов (если разрешено)
        if config.allowed_to_check_and_accept_new_trades:
            self._start_trade_monitoring(account_name)
        
        self.logger.info(f"Запущен мониторинг для {account_name}")
    
    def stop_account_monitoring(self, account_name: str) -> None:
        """
        Остановка мониторинга для аккаунта
        
        Args:
            account_name: Имя аккаунта
        """
        self._stop_account_tasks(account_name)
        
        if account_name in self.session_managers:
            self.session_managers[account_name].stop_monitoring()
        
        self.logger.info(f"Остановлен мониторинг для {account_name}")
    
    def _start_trade_monitoring(self, account_name: str) -> None:
        """
        Запуск мониторинга трейдов для аккаунта
        
        Args:
            account_name: Имя аккаунта
        """
        if account_name in self.running_tasks:
            return  # Уже запущен
        
        def trade_monitor():
            config = self.config_manager.get_account(account_name)
            
            while self.is_running and account_name in self.running_tasks:
                try:
                    if account_name in self.clients:
                        self._check_and_process_trades(account_name)
                    
                    time.sleep(config.seconds_to_check_trades)
                    
                except Exception as e:
                    self.logger.error(f"Ошибка в мониторинге трейдов для {account_name}: {e}")
                    time.sleep(30)  # Пауза при ошибке
        
        task_thread = threading.Thread(target=trade_monitor, name=f"trade_monitor_{account_name}")
        task_thread.daemon = True
        self.running_tasks[account_name] = task_thread
        task_thread.start()
    
    def _stop_account_tasks(self, account_name: str) -> None:
        """
        Остановка всех задач аккаунта
        
        Args:
            account_name: Имя аккаунта
        """
        if account_name in self.running_tasks:
            # Поток завершится сам при следующей проверке is_running
            del self.running_tasks[account_name]
    
    def _check_and_process_trades(self, account_name: str) -> None:
        """
        Проверка и обработка трейдов для аккаунта
        
        Args:
            account_name: Имя аккаунта
        """
        if account_name not in self.clients:
            return
        
        client = self.clients[account_name]
        config = self.config_manager.get_account(account_name)
        
        try:
            # Получаем активные трейд-офферы
            trades_response = client.get_trade_offers()
            received_offers = trades_response.get('response', {}).get('trade_offers_received', [])
            
            for offer in received_offers:
                if offer.get('trade_offer_state') != TradeOfferState.Active:
                    continue
                
                trade_id = offer.get('tradeofferid')
                if not trade_id:
                    continue
                
                # Проверяем условия принятия трейда
                should_accept = self._should_accept_trade(offer, config)
                
                if should_accept:
                    try:
                        result = client.accept_trade_offer(trade_id)
                        if result:
                            self.logger.info(f"Принят трейд {trade_id} для {account_name}")
                        else:
                            self.logger.warning(f"Не удалось принять трейд {trade_id} для {account_name}")
                    
                    except Exception as e:
                        self.logger.error(f"Ошибка принятия трейда {trade_id} для {account_name}: {e}")
        
        except Exception as e:
            self.logger.error(f"Ошибка получения трейдов для {account_name}: {e}")
    
    def _should_accept_trade(self, offer: Dict[str, Any], config: AccountConfig) -> bool:
        """
        Определение, следует ли принять трейд
        
        Args:
            offer: Данные трейд-оффера
            config: Конфигурация аккаунта
            
        Returns:
            True если трейд следует принять
        """
        # Если трейд уже принят в веб-интерфейсе
        if config.accept_every_accepted_on_web_trade:
            # Дополнительная логика для проверки статуса в веб-интерфейсе
            pass
        
        # Если это "бесплатный" трейд (мы ничего не отдаем)
        if config.accept_every_free_trade:
            items_to_give = offer.get('items_to_give', [])
            if not items_to_give:  # Мы ничего не отдаем
                return True
        
        return False
    
    def get_account_status(self, account_name: str) -> Dict[str, Any]:
        """
        Получение статуса аккаунта
        
        Args:
            account_name: Имя аккаунта
            
        Returns:
            Словарь со статусом аккаунта
        """
        status = {
            'account_name': account_name,
            'session_valid': False,
            'monitoring_active': False,
            'trade_monitoring_active': False,
            'last_check': None,
            'config': None
        }
        
        try:
            # Получаем конфигурацию
            config = self.config_manager.get_account(account_name)
            status['config'] = config.to_dict()
            
            # Проверяем session manager
            if account_name in self.session_managers:
                session_status = self.session_managers[account_name].get_status()
                status.update(session_status)
            
            # Проверяем мониторинг трейдов
            status['trade_monitoring_active'] = account_name in self.running_tasks
            
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса для {account_name}: {e}")
            status['error'] = str(e)
        
        return status
    
    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение статусов всех аккаунтов
        
        Returns:
            Словарь со статусами всех аккаунтов
        """
        statuses = {}
        
        for account_name in self.config_manager.list_accounts():
            statuses[account_name] = self.get_account_status(account_name)
        
        return statuses
    
    def start_all_monitoring(self) -> None:
        """Запуск мониторинга для всех аккаунтов"""
        self.is_running = True
        
        for account_name in self.config_manager.list_accounts():
            try:
                if self.login_account(account_name):
                    self.start_account_monitoring(account_name)
                else:
                    self.logger.error(f"Не удалось войти в аккаунт {account_name}")
            
            except Exception as e:
                self.logger.error(f"Ошибка запуска мониторинга для {account_name}: {e}")
    
    def stop_all_monitoring(self) -> None:
        """Остановка мониторинга для всех аккаунтов"""
        self.is_running = False
        
        for account_name in list(self.session_managers.keys()):
            self.stop_account_monitoring(account_name)
        
        # Очищаем задачи
        self.running_tasks.clear()
    
    def perform_action_on_account(self, account_name: str, action: Callable, *args, **kwargs) -> Any:
        """
        Выполнение действия на конкретном аккаунте
        
        Args:
            account_name: Имя аккаунта
            action: Функция для выполнения
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Результат выполнения действия
        """
        if account_name not in self.clients:
            raise ValueError(f"Клиент для аккаунта {account_name} не активен")
        
        client = self.clients[account_name]
        
        try:
            return action(client, *args, **kwargs)
        except Exception as e:
            self.logger.error(f"Ошибка выполнения действия для {account_name}: {e}")
            raise
    
    def perform_action_on_all(self, action: Callable, *args, **kwargs) -> Dict[str, Any]:
        """
        Выполнение действия на всех активных аккаунтах параллельно
        
        Args:
            action: Функция для выполнения
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
            
        Returns:
            Словарь с результатами для каждого аккаунта
        """
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.clients)) as executor:
            # Запускаем задачи
            future_to_account = {
                executor.submit(self.perform_action_on_account, account_name, action, *args, **kwargs): account_name
                for account_name in self.clients.keys()
            }
            
            # Собираем результаты
            for future in concurrent.futures.as_completed(future_to_account):
                account_name = future_to_account[future]
                try:
                    result = future.result()
                    results[account_name] = {'success': True, 'result': result}
                except Exception as e:
                    results[account_name] = {'success': False, 'error': str(e)}
        
        return results 
