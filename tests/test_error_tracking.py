#!/usr/bin/env python3
"""
Тесты для системы контроля ошибок и уведомлений
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import time

from src.cli.multi_account_auto_manager import AccountErrorTracker, MultiAccountAutoManager
from src.interfaces.notification_interface import NotificationInterface
from src.implementations.notifications.logger_notification import LoggerNotification
from src.implementations.notifications.telegram_notification import TelegramNotification
from src.cli.config_manager import ConfigManager

import os
print("Текущий рабочий каталог:", os.getcwd())
print("Содержимое config.yaml:")
with open("config.yaml", "r", encoding="utf-8") as f:
    print(f.read())


class MockNotificationProvider(NotificationInterface):
    """Мок-реализация уведомлений для тестирования"""
    
    def __init__(self):
        self.notifications = []
    
    def notify_user(self, message: str) -> bool:
        self.notifications.append(message)
        return True


class TestAccountErrorTracker(unittest.TestCase):
    """Тесты для AccountErrorTracker"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.mock_notification = MockNotificationProvider()
        self.tracker = AccountErrorTracker(max_errors=3, notification_provider=self.mock_notification)
    
    def test_initial_state(self):
        """Тест начального состояния"""
        self.assertEqual(self.tracker.max_errors, 3)
        self.assertEqual(len(self.tracker.error_counts), 0)
        self.assertEqual(len(self.tracker.disabled_accounts), 0)
    
    def test_record_first_error(self):
        """Тест записи первой ошибки"""
        result = self.tracker.record_error("test_account")
        
        self.assertFalse(result)  # Аккаунт не должен быть отключен
        self.assertEqual(self.tracker.get_error_count("test_account"), 1)
        self.assertFalse(self.tracker.is_account_disabled("test_account"))
        self.assertEqual(len(self.mock_notification.notifications), 0)  # Уведомление не отправлено
    
    def test_record_multiple_errors(self):
        """Тест записи нескольких ошибок"""
        # Первая ошибка
        result1 = self.tracker.record_error("test_account")
        self.assertFalse(result1)
        self.assertEqual(self.tracker.get_error_count("test_account"), 1)
        
        # Вторая ошибка
        result2 = self.tracker.record_error("test_account")
        self.assertFalse(result2)
        self.assertEqual(self.tracker.get_error_count("test_account"), 2)
        
        # Третья ошибка (критическая)
        result3 = self.tracker.record_error("test_account")
        self.assertTrue(result3)  # Аккаунт должен быть отключен
        self.assertEqual(self.tracker.get_error_count("test_account"), 3)
        self.assertTrue(self.tracker.is_account_disabled("test_account"))
        
        # Проверяем уведомление
        self.assertEqual(len(self.mock_notification.notifications), 1)
        self.assertIn("test_account", self.mock_notification.notifications[0])
        self.assertIn("убран из автопроверки", self.mock_notification.notifications[0])
    
    def test_record_success_resets_errors(self):
        """Тест сброса ошибок при успешном выполнении"""
        # Записываем 2 ошибки
        self.tracker.record_error("test_account")
        self.tracker.record_error("test_account")
        self.assertEqual(self.tracker.get_error_count("test_account"), 2)
        
        # Успешное выполнение
        self.tracker.record_success("test_account")
        self.assertEqual(self.tracker.get_error_count("test_account"), 0)
        self.assertFalse(self.tracker.is_account_disabled("test_account"))
    
    def test_multiple_accounts(self):
        """Тест работы с несколькими аккаунтами"""
        # Ошибки для первого аккаунта
        self.tracker.record_error("account1")
        self.tracker.record_error("account1")
        
        # Ошибки для второго аккаунта
        self.tracker.record_error("account2")
        
        # Проверяем состояние
        self.assertEqual(self.tracker.get_error_count("account1"), 2)
        self.assertEqual(self.tracker.get_error_count("account2"), 1)
        self.assertFalse(self.tracker.is_account_disabled("account1"))
        self.assertFalse(self.tracker.is_account_disabled("account2"))
        
        # Критическая ошибка для первого аккаунта
        self.tracker.record_error("account1")
        self.assertTrue(self.tracker.is_account_disabled("account1"))
        self.assertFalse(self.tracker.is_account_disabled("account2"))
    
    def test_reset_account_errors(self):
        """Тест ручного сброса ошибок"""
        # Записываем ошибки и отключаем аккаунт
        self.tracker.record_error("test_account")
        self.tracker.record_error("test_account")
        self.tracker.record_error("test_account")
        self.assertTrue(self.tracker.is_account_disabled("test_account"))
        
        # Ручной сброс
        self.tracker.reset_account_errors("test_account")
        self.assertEqual(self.tracker.get_error_count("test_account"), 0)
        self.assertFalse(self.tracker.is_account_disabled("test_account"))
    
    def test_get_status_summary(self):
        """Тест получения сводки статуса"""
        # Добавляем данные
        self.tracker.record_error("account1")
        self.tracker.record_error("account1")
        self.tracker.record_error("account1")  # Отключается
        self.tracker.record_error("account2")
        
        summary = self.tracker.get_status_summary()
        
        self.assertEqual(summary['total_accounts'], 2)
        self.assertEqual(summary['disabled_accounts'], 1)
        self.assertEqual(summary['accounts_with_errors'], 2)
        self.assertIn('account1', summary['disabled_list'])
        self.assertEqual(summary['error_counts']['account1'], 3)
        self.assertEqual(summary['error_counts']['account2'], 1)
    
    def test_no_notification_provider(self):
        """Тест работы без провайдера уведомлений"""
        tracker = AccountErrorTracker(max_errors=2)  # Без уведомлений
        
        # Записываем критические ошибки
        result1 = tracker.record_error("test_account")
        result2 = tracker.record_error("test_account")
        
        self.assertFalse(result1)
        self.assertTrue(result2)  # Аккаунт отключен
        self.assertTrue(tracker.is_account_disabled("test_account"))


class TestMultiAccountAutoManager(unittest.TestCase):
    """Тесты для MultiAccountAutoManager"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        # Создаем мок конфигурации
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.clone.return_value = self.mock_config
        self.mock_config.get_all_account_names.return_value = ["test_account1", "test_account2"]
        
        # Мок для notification_provider
        self.mock_notification_config = {
            'module_path': 'src.implementations.notifications.logger_notification',
            'class_name': 'LoggerNotification'
        }
    
    @patch('src.factories.create_instance_from_config')
    def test_initialization_with_notifications(self, mock_create_instance):
        """Тест инициализации с системой уведомлений"""
        self.mock_config.get.side_effect = lambda key, default=None: {
            'min_request_delay_ms': 1000,
            'notification_provider': self.mock_notification_config
        }.get(key, default)
        
        mock_notification = MockNotificationProvider()
        mock_create_instance.return_value = mock_notification
        
        manager = MultiAccountAutoManager(self.mock_config)
        
        self.assertIsNotNone(manager.error_tracker)
        self.assertEqual(manager.error_tracker.max_errors, 3)
        self.assertIsNotNone(manager.error_tracker.notification_provider)
    
    @patch('src.factories.create_instance_from_config')
    def test_initialization_without_notifications(self, mock_create_instance):
        """Тест инициализации без системы уведомлений"""
        self.mock_config.get.side_effect = lambda key, default=None: {
            'min_request_delay_ms': 1000,
            'notification_provider': None
        }.get(key, default)
        
        with self.assertRaises(Exception) as context:
            MultiAccountAutoManager(self.mock_config)
        self.assertIn("Система уведомлений не инициализирована", str(context.exception))
    
    @patch('src.factories.create_instance_from_config')
    def test_initialization_notification_error(self, mock_create_instance):
        """Тест инициализации с ошибкой в системе уведомлений"""
        # Используем несуществующий класс для notification_provider
        broken_notification_config = {
            'module_path': 'src.implementations.nonexistent_module',
            'class_name': 'NonExistentNotification'
        }
        self.mock_config.get.side_effect = lambda key, default=None: {
            'min_request_delay_ms': 1000,
            'notification_provider': broken_notification_config
        }.get(key, default)
        
        mock_create_instance.side_effect = Exception("Notification error")
        
        with self.assertRaises(Exception) as context:
            MultiAccountAutoManager(self.mock_config)
        self.assertIn("Система уведомлений не инициализирована", str(context.exception))


class TestLoggerNotification(unittest.TestCase):
    """Тесты для LoggerNotification"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.notification = LoggerNotification()
    
    @patch('src.implementations.notifications.logger_notification.notification.logger')
    def test_notify_user_success(self, mock_logger):
        """Тест успешной отправки уведомления"""
        message = "Тестовое уведомление"
        result = self.notification.notify_user(message)
        
        self.assertTrue(result)
        mock_logger.critical.assert_called_once()
        call_args = mock_logger.critical.call_args[0][0]
        self.assertIn("🔔 УВЕДОМЛЕНИЕ:", call_args)
        self.assertIn(message, call_args)
    
    @patch('src.implementations.notifications.logger_notification.notification.logger')
    def test_notify_user_exception(self, mock_logger):
        """Тест обработки исключения при отправке уведомления"""
        mock_logger.critical.side_effect = Exception("Logger error")
        
        result = self.notification.notify_user("Тестовое уведомление")
        
        self.assertFalse(result)
        mock_logger.error.assert_called_once()


class TestTelegramNotification(unittest.TestCase):
    """Тесты для TelegramNotification"""
    
    @patch('os.getenv')
    @patch('pathlib.Path.exists')
    def test_initialization_success(self, mock_exists, mock_getenv):
        """Тест успешной инициализации"""
        mock_exists.return_value = True
        mock_getenv.side_effect = lambda key: {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'TELEGRAM_CHAT_ID': 'test_chat_id'
        }.get(key)
        
        with patch('dotenv.load_dotenv'):
            notification = TelegramNotification()
            
        self.assertEqual(notification.bot_token, 'test_token')
        self.assertEqual(notification.chat_id, 'test_chat_id')
    
    @patch('os.getenv')
    @patch('pathlib.Path.exists')
    def test_initialization_missing_env(self, mock_exists, mock_getenv):
        """Тест инициализации с отсутствующими переменными окружения"""
        mock_exists.return_value = True
        mock_getenv.return_value = None
        
        with patch('dotenv.load_dotenv'):
            with self.assertRaises(ValueError):
                TelegramNotification()
    
    @patch('requests.get')
    @patch('os.getenv')
    @patch('pathlib.Path.exists')
    def test_notify_user_success(self, mock_exists, mock_getenv, mock_requests):
        """Тест успешной отправки уведомления"""
        mock_exists.return_value = True
        mock_getenv.side_effect = lambda key: {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'TELEGRAM_CHAT_ID': 'test_chat_id'
        }.get(key)
        
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response
        
        with patch('dotenv.load_dotenv'):
            notification = TelegramNotification()
        
        result = notification.notify_user("Тестовое сообщение")
        
        self.assertTrue(result)
        mock_requests.assert_called_once()
        call_args = mock_requests.call_args
        self.assertIn('https://api.telegram.org/bottest_token/sendMessage', call_args[0][0])


if __name__ == '__main__':
    unittest.main() 