#!/usr/bin/env python3
"""
Демонстрация работы системы контроля ошибок и уведомлений
Имитирует реальные сценарии работы с аккаунтами
"""

import time
import random
from typing import Dict, List
from src.cli.multi_account_auto_manager import AccountErrorTracker
from src.cli.config_manager import ConfigManager
from src.factories import create_instance_from_config


class MockSteamError(Exception):
    """Имитация ошибки Steam API"""
    pass


class MockNetworkError(Exception):
    """Имитация сетевой ошибки"""
    pass


class MockAuthError(Exception):
    """Имитация ошибки авторизации"""
    pass


class MockAccountSimulator:
    """Симулятор работы с аккаунтами Steam"""
    
    def __init__(self, account_name: str):
        self.account_name = account_name
        self.success_rate = random.uniform(0.7, 0.95)  # 70-95% успешных операций
        self.error_types = [
            ("Сетевая ошибка", MockNetworkError, 0.3),
            ("Ошибка Steam API", MockSteamError, 0.4),
            ("Ошибка авторизации", MockAuthError, 0.3)
        ]
    
    def simulate_operation(self) -> bool:
        """Симулирует операцию с аккаунтом"""
        if random.random() < self.success_rate:
            return True
        
        # Выбираем тип ошибки
        error_name, error_class, weight = random.choices(
            self.error_types, 
            weights=[w for _, _, w in self.error_types]
        )[0]
        
        raise error_class(f"[{self.account_name}] {error_name}")


def get_notification_provider_from_config() -> object:
    """Получает провайдер уведомлений из реального конфига"""
    try:
        config = ConfigManager()
        config.load_config()  # Явно загружаем конфиг
        notification_config = config.get('notification_provider')
        
        print(f"🔍 Отладка: notification_config = {notification_config}")
        
        if notification_config:
            print(f"🔍 Отладка: Создаем провайдер из конфига...")
            notification_provider = create_instance_from_config(notification_config)
            print(f"✅ Используется провайдер уведомлений: {type(notification_provider).__name__}")
            return notification_provider
        else:
            raise Exception("Провайдер уведомлений не настроен в конфиге")
            
    except Exception as e:
        print(f"❌ Ошибка загрузки провайдера уведомлений: {e}")
        print("🔄 Используется LoggerNotification по умолчанию")
        from src.implementations.notifications.logger_notification import LoggerNotification
        return LoggerNotification()


def demo_realistic_error_tracking():
    """Демонстрация с имитацией реальных ошибок"""
    print("🚀 Демонстрация системы контроля ошибок с реальными сценариями")
    print("=" * 70)
    
    # Получаем провайдер уведомлений из конфига
    notification_provider = get_notification_provider_from_config()
    
    # Создаем трекер ошибок
    tracker = AccountErrorTracker(max_errors=3, notification_provider=notification_provider)
    
    print(f"📊 Максимальное количество ошибок: {tracker.max_errors}")
    print(f"🔔 Провайдер уведомлений: {type(notification_provider).__name__}")
    print()
    
    # Создаем симуляторы аккаунтов с разными характеристиками
    accounts = {
        "steam_account_1": MockAccountSimulator("steam_account_1"),  # Надежный аккаунт
        "steam_account_2": MockAccountSimulator("steam_account_2"),  # Проблемный аккаунт
        "steam_account_3": MockAccountSimulator("steam_account_3"),  # Средний аккаунт
        "steam_account_4": MockAccountSimulator("steam_account_4"),  # Очень проблемный
    }
    
    # Настраиваем разные характеристики для аккаунтов
    accounts["steam_account_1"].success_rate = 0.95  # 95% успеха
    accounts["steam_account_2"].success_rate = 0.75  # 75% успеха
    accounts["steam_account_3"].success_rate = 0.85  # 85% успеха
    accounts["steam_account_4"].success_rate = 0.60  # 60% успеха - очень проблемный
    
    print("🔄 Симуляция работы аккаунтов Steam...")
    print()
    
    # Симулируем несколько циклов работы
    for cycle in range(1, 15):
        print(f"🔄 Цикл {cycle}/5:")
        
        for account_name, simulator in accounts.items():
            if tracker.is_account_disabled(account_name):
                print(f"  ⏸️  [{account_name}] Пропуск - аккаунт отключен")
                continue
            
            try:
                # Симулируем операцию
                success = simulator.simulate_operation()
                
                if success:
                    tracker.record_success(account_name)
                    print(f"  ✅ [{account_name}] Операция успешна")
                else:
                    # Не должно произойти, но на всякий случай
                    tracker.record_error(account_name)
                    print(f"  ❌ [{account_name}] Неожиданная ошибка")
                    
            except MockNetworkError as e:
                tracker.record_error(account_name)
                print(f"  🌐 [{account_name}] Сетевая ошибка: {e}")
                
            except MockSteamError as e:
                tracker.record_error(account_name)
                print(f"  🎮 [{account_name}] Ошибка Steam API: {e}")
                
            except MockAuthError as e:
                tracker.record_error(account_name)
                print(f"  🔐 [{account_name}] Ошибка авторизации: {e}")
        
        print()
        time.sleep(1)  # Пауза между циклами
    
    print("=" * 70)
    print("📊 Финальная статистика:")
    
    # Выводим детальную статистику
    summary = tracker.get_status_summary()
    print(f"  Всего аккаунтов: {summary['total_accounts']}")
    print(f"  Отключено: {summary['disabled_accounts']}")
    print(f"  С ошибками: {summary['accounts_with_errors']}")
    
    print("\n  Детали по аккаунтам:")
    for account, count in summary['error_counts'].items():
        status = "❌ Отключен" if account in summary['disabled_list'] else "✅ Активен"
        success_rate = accounts[account].success_rate * 100
        print(f"    {account}: {count} ошибок - {status} (успех: {success_rate:.0f}%)")
    
    if summary['disabled_list']:
        print(f"\n  🚫 Отключенные аккаунты: {', '.join(summary['disabled_list'])}")
    
    print("\n" + "=" * 70)
    print("🔄 Демонстрация восстановления аккаунтов:")
    
    # Показываем возможность восстановления
    disabled_accounts = summary['disabled_list']
    if disabled_accounts:
        account_to_restore = disabled_accounts[0]
        print(f"  🔧 Восстанавливаем аккаунт {account_to_restore}...")
        tracker.reset_account_errors(account_to_restore)
        print(f"  ✅ {account_to_restore} снова активен")
        
        # Обновляем статистику
        summary = tracker.get_status_summary()
        print(f"  📊 Отключено после восстановления: {summary['disabled_accounts']}")
    else:
        print("  ✅ Все аккаунты активны, восстановление не требуется")
    
    print("\n🏁 Демонстрация завершена!")



if __name__ == '__main__':
    demo_realistic_error_tracking()
