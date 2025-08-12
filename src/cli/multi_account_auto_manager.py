#!/usr/bin/env python3
"""
Менеджер для запуска автоматизации в едином цикле для всех аккаунтов.
"""
import time
from typing import Dict, Set, Any, Optional, List

from src.cli.account_context import build_account_context
from src.cli.auto_manager import AutoManager
from src.cli.config_manager import ConfigManager
from src.utils.logger_setup import logger, print_and_log
from src.factories import create_instance_from_config
from src.interfaces.notification_interface import NotificationInterface

class AccountErrorTracker:
    """Отслеживает ошибки для каждого аккаунта"""
    
    def __init__(self, max_errors: int = 3, notification_provider: NotificationInterface = None):
        self.max_errors = max_errors
        self.error_counts: Dict[str, int] = {}
        self.disabled_accounts: Set[str] = set()
        self.notification_provider = notification_provider
    
    def record_error(self, account_name: str) -> bool:
        """
        Записывает ошибку для аккаунта
        
        Returns:
            bool: True если аккаунт должен быть отключен
        """
        current_errors = self.error_counts.get(account_name, 0) + 1
        self.error_counts[account_name] = current_errors
        
        logger.warning(f"[{account_name}] Ошибка #{current_errors}/{self.max_errors}")
        
        if current_errors >= self.max_errors:
            self.disabled_accounts.add(account_name)
            logger.error(f"[{account_name}] Достигнут лимит ошибок ({self.max_errors}). Аккаунт отключен от автоматизации.")
            message = f"В проекте pySDA произошло множество критических ошибок подряд, аккаунт {account_name} убран из автопроверки"
            try:
                self.notification_provider.notify_user(message)
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")
            
            return True
        
        return False
    
    def record_success(self, account_name: str):
        """Записывает успешное выполнение для аккаунта"""
        if account_name in self.error_counts:
            old_count = self.error_counts[account_name]
            self.error_counts[account_name] = 0
            if old_count > 0:
                logger.info(f"[{account_name}] Ошибки сброшены после успешного выполнения (было {old_count})")
    
    def reset_account_errors(self, account_name: str):
        """Сбрасывает ошибки для аккаунта (ручной сброс)"""
        if account_name in self.error_counts:
            old_count = self.error_counts[account_name]
            self.error_counts[account_name] = 0
            logger.info(f"[{account_name}] Ошибки сброшены вручную (было {old_count})")
        
        if account_name in self.disabled_accounts:
            self.disabled_accounts.remove(account_name)
            logger.info(f"[{account_name}] Аккаунт снова включен в автоматизацию")
    
    def is_account_disabled(self, account_name: str) -> bool:
        """Проверяет, отключен ли аккаунт"""
        return account_name in self.disabled_accounts
    
    def get_disabled_accounts(self) -> Set[str]:
        """Возвращает список отключенных аккаунтов"""
        return self.disabled_accounts.copy()
    
    def get_error_count(self, account_name: str) -> int:
        """Возвращает количество ошибок для аккаунта"""
        return self.error_counts.get(account_name, 0)
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Возвращает сводку по всем аккаунтам"""
        return {
            'total_accounts': len(self.error_counts),
            'disabled_accounts': len(self.disabled_accounts),
            'accounts_with_errors': len([acc for acc, count in self.error_counts.items() if count > 0]),
            'error_counts': self.error_counts.copy(),
            'disabled_list': list(self.disabled_accounts)
        }

class MultiAccountAutoManager:
    def __init__(self, config_manager: ConfigManager, allowed_account_names: Optional[List[str]] = None):
        # Используем клон ConfigManager для избежания конфликтов состояний
        self.config_manager = config_manager.clone()
        self._last_check_times: Dict[str, float] = {}
        self.allowed_account_names: Optional[List[str]] = allowed_account_names
        
        # Получаем задержку из конфига и переводим в секунды
        delay_ms = self.config_manager.get('min_request_delay_ms', 1000)
        self.min_request_delay_sec = delay_ms / 1000.0
        
        notification_provider = None  # <-- фикс
        notification_config = self.config_manager.get('notification_provider')
        if notification_config:
            try:
                notification_provider = create_instance_from_config(notification_config)
                logger.info("✅ Система уведомлений инициализирована")
            except Exception as e:
                logger.error(f"Ошибка инициализации системы уведомлений: {e}")
                notification_provider = None
        if not notification_provider:
            raise Exception("Система уведомлений не инициализирована")
        # Система контроля ошибок
        self.error_tracker = AccountErrorTracker(max_errors=3, notification_provider=notification_provider)

    def start(self):
        """Запускает блокирующий единый цикл автоматизации для всех аккаунтов."""
        account_names = (
            list(self.allowed_account_names)
            if self.allowed_account_names is not None
            else self.config_manager.get_all_account_names()
        )
        if not account_names:
            print_and_log("❌ Не найдено ни одного аккаунта для запуска автоматизации.")
            return

        print_and_log(f"🚀 Запуск автоматизации в режиме единого цикла для {len(account_names)} аккаунтов.")
        print_and_log(f"🕒 Минимальная задержка между запросами: {self.min_request_delay_sec * 1000:.0f} мс.")
        print_and_log("ℹ️  Для остановки нажмите Ctrl+C")
        print_and_log("🛡️  Система контроля ошибок активна (максимум 3 ошибки подряд)")
        print()

        # Предзагружаем инстансы AutoManager для каждого аккаунта
        auto_managers = {
            name: AutoManager(account_name=name) for name in account_names
        }

        # Для периодического вывода статистики
        last_stats_time = time.time()
        stats_interval = 300

        try:
            while True:
                now = time.time()
                processed_in_this_cycle = False
                active_accounts = [name for name in account_names if not self.error_tracker.is_account_disabled(name)]

                # Периодический вывод статистики
                if now - last_stats_time >= stats_interval:
                    self._print_error_statistics()
                    last_stats_time = now

                # Показываем статистику отключенных аккаунтов
                disabled_accounts = self.error_tracker.get_disabled_accounts()
                if disabled_accounts:
                    print_and_log(f"⚠️ Отключенные аккаунты: {', '.join(disabled_accounts)}")

                for account_name in active_accounts:
                    auto_manager = auto_managers[account_name]
                    settings = auto_manager.settings
                    last_check = self._last_check_times.get(account_name, 0)

                    if (now - last_check) >= settings.check_interval:
                        print_and_log(f"[{account_name}] 🔄 Настало время проверки (интервал: {settings.check_interval} с).")
                        
                        self._process_account(account_name, auto_manager)
                        
                        self._last_check_times[account_name] = time.time()
                        processed_in_this_cycle = True

                # Если в этом цикле ничего не делали, ждем секунду, чтобы не грузить CPU
                if not processed_in_this_cycle:
                    time.sleep(1)

        except KeyboardInterrupt:
            print_and_log("🛑 Получен сигнал Ctrl+C. Завершение работы...")
            self._print_error_statistics()
        
        print_and_log("🏁 Цикл автоматизации корректно остановлен.")

    def _process_account(self, account_name: str, auto_manager: AutoManager):
        """Выполняет задачи автоматизации для одного аккаунта."""
        try:
            print_and_log(f"[{account_name}] 🛠️  Создание контекста...")
            context = build_account_context(self.config_manager, account_name)
            if context:
                print_and_log(f"[{account_name}] ✅ Контекст создан, выполняем задачи...")
                auto_manager._execute_automation_tasks(context, auto_manager.settings)
                print_and_log(f"[{account_name}] ✅ Задачи выполнены успешно")
                # Записываем успешное выполнение
                self.error_tracker.record_success(account_name)
            else:
                print_and_log(f"[{account_name}] ❌ Пропуск итерации из-за ошибки создания контекста.")
                self.error_tracker.record_error(account_name)
        except Exception as e:
            print_and_log(f"[{account_name}] ❌ Необработанная ошибка во время выполнения задач: {e}")
            self.error_tracker.record_error(account_name)

    def _print_error_statistics(self):
        """Выводит статистику ошибок"""
        print_and_log("📊 Статистика ошибок:")
        print_and_log(f"  Всего аккаунтов: {len(self.error_tracker.error_counts)}")
        print_and_log(f"  Отключено: {len(self.error_tracker.disabled_accounts)}")
        print_and_log(f"  С ошибками: {sum(1 for count in self.error_tracker.error_counts.values() if count > 0)}")
        
        if self.error_tracker.error_counts:
            print_and_log("  Детали по аккаунтам:")
            for account, count in self.error_tracker.error_counts.items():
                status = "🔴 ОТКЛЮЧЕН" if account in self.error_tracker.disabled_accounts else f"⚠️ {count} ошибок"
                print_and_log(f"    {account}: {status}") 