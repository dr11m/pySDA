#!/usr/bin/env python3
"""
Тест для проверки работы прокси для каждого аккаунта.
Проверяет, что каждый аккаунт использует правильный прокси (или прямой IP для no_proxy).
"""

import requests
import json
import time
from typing import Dict, Optional
from pathlib import Path

from src.cli.config_manager import ConfigManager
from src.utils.logger_setup import logger


class ProxyConnectionTester:
    """Тестер для проверки подключения через прокси"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config_manager.load_config()
        
    def get_current_ip(self, proxy: Optional[Dict[str, str]] = None) -> Optional[str]:
        """
        Получает текущий IP адрес через указанный прокси
        
        Args:
            proxy: Словарь с настройками прокси или None для прямого подключения
            
        Returns:
            IP адрес в виде строки или None при ошибке
        """
        try:
            # Используем несколько API для надежности
            apis = [
                'https://api.ipify.org?format=json',
                'https://httpbin.org/ip',
                'https://api.myip.com'
            ]
            
            for api_url in apis:
                try:
                    response = requests.get(api_url, proxies=proxy, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Разные API возвращают IP в разных полях
                        if 'ip' in data:
                            return data['ip']
                        elif 'origin' in data:
                            return data['origin']
                        
                except Exception as e:
                    logger.debug(f"API {api_url} недоступен: {e}")
                    continue
            
            logger.error("Все API для проверки IP недоступны")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения IP: {e}")
            return None
    
    def test_account_proxy(self, account_name: str) -> Dict[str, any]:
        """
        Тестирует прокси для конкретного аккаунта
        
        Args:
            account_name: Имя аккаунта
            
        Returns:
            Словарь с результатами теста
        """
        logger.info(f"🔍 Тестирование прокси для аккаунта: {account_name}")
        
        # Получаем конфигурацию аккаунта
        if not self.config_manager.select_account(account_name):
            return {
                'account_name': account_name,
                'status': 'error',
                'message': f'Конфигурация для аккаунта {account_name} не найдена'
            }
        
        # Получаем провайдер прокси
        proxy_provider_config = self.config_manager.get('proxy_provider')
        if not proxy_provider_config:
            return {
                'account_name': account_name,
                'status': 'error',
                'message': 'Провайдер прокси не настроен'
            }
        
        try:
            # Создаем экземпляр провайдера прокси
            from src.factories import create_instance_from_config
            proxy_provider = create_instance_from_config(proxy_provider_config)
            
            # Получаем прокси для аккаунта
            proxy = proxy_provider.get_proxy(account_name)
            
            logger.info(f"📋 Прокси для {account_name}: {proxy}")
            
            # Получаем IP через прокси
            ip_address = self.get_current_ip(proxy)
            
            if ip_address is None:
                return {
                    'account_name': account_name,
                    'status': 'error',
                    'message': 'Не удалось получить IP адрес',
                    'proxy': proxy
                }
            
            # Определяем результат теста
            if proxy is None:
                # Для no_proxy - проверяем, что IP не из локальной сети
                if self._is_local_ip(ip_address):
                    status = 'warning'
                    message = f'IP {ip_address} выглядит как локальный адрес (возможно, VPN или прокси активен)'
                else:
                    status = 'success'
                    message = f'Прямое подключение: IP {ip_address}'
            else:
                # Для прокси - проверяем, что IP отличается от прямого подключения
                direct_ip = self.get_current_ip(None)
                if direct_ip and direct_ip != ip_address:
                    status = 'success'
                    message = f'Прокси работает: IP {ip_address} (прямой IP: {direct_ip})'
                else:
                    status = 'warning'
                    message = f'IP {ip_address} совпадает с прямым подключением (возможно, прокси не работает)'
            
            return {
                'account_name': account_name,
                'status': status,
                'message': message,
                'proxy': proxy,
                'ip_address': ip_address
            }
            
        except Exception as e:
            logger.error(f"Ошибка тестирования прокси для {account_name}: {e}")
            return {
                'account_name': account_name,
                'status': 'error',
                'message': f'Ошибка: {str(e)}'
            }
    
    def _is_local_ip(self, ip: str) -> bool:
        """Проверяет, является ли IP локальным адресом"""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            
            # Локальные сети: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
            first = int(parts[0])
            second = int(parts[1])
            
            return (first == 10 or 
                   (first == 172 and 16 <= second <= 31) or 
                   (first == 192 and second == 168))
        except:
            return False
    
    def test_all_accounts(self) -> Dict[str, any]:
        """
        Тестирует прокси для всех аккаунтов
        
        Returns:
            Словарь с результатами всех тестов
        """
        logger.info("🚀 Начинаем тестирование прокси для всех аккаунтов")
        
        account_names = self.config_manager.get_all_account_names()
        if not account_names:
            logger.error("Аккаунты не найдены в конфигурации")
            return {'status': 'error', 'message': 'Аккаунты не найдены'}
        
        results = {
            'total_accounts': len(account_names),
            'success_count': 0,
            'warning_count': 0,
            'error_count': 0,
            'accounts': []
        }
        
        for account_name in account_names:
            result = self.test_account_proxy(account_name)
            results['accounts'].append(result)
            
            # Подсчитываем статистику
            if result['status'] == 'success':
                results['success_count'] += 1
            elif result['status'] == 'warning':
                results['warning_count'] += 1
            else:
                results['error_count'] += 1
            
            # Небольшая задержка между запросами
            time.sleep(1)
        
        # Определяем общий статус
        if results['error_count'] > 0:
            results['status'] = 'error'
        elif results['warning_count'] > 0:
            results['status'] = 'warning'
        else:
            results['status'] = 'success'
        
        return results
    
    def print_results(self, results: Dict[str, any]):
        """Выводит результаты тестирования в консоль"""
        print("\n" + "="*60)
        print("🔍 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ПРОКСИ")
        print("="*60)
        
        if results['status'] == 'error' and 'message' in results:
            print(f"❌ {results['message']}")
            return
        
        print(f"📊 Всего аккаунтов: {results['total_accounts']}")
        print(f"✅ Успешно: {results['success_count']}")
        print(f"⚠️  Предупреждения: {results['warning_count']}")
        print(f"❌ Ошибки: {results['error_count']}")
        print()
        
        for account_result in results['accounts']:
            status_icon = {
                'success': '✅',
                'warning': '⚠️',
                'error': '❌'
            }.get(account_result['status'], '❓')
            
            print(f"{status_icon} {account_result['account_name']}")
            print(f"   {account_result['message']}")
            
            if 'proxy' in account_result and account_result['proxy']:
                proxy_str = account_result['proxy'].get('http', 'N/A')
                print(f"   Прокси: {proxy_str}")
            elif 'proxy' in account_result and account_result['proxy'] is None:
                print(f"   Прокси: no_proxy (прямое подключение)")
            
            if 'ip_address' in account_result:
                print(f"   IP: {account_result['ip_address']}")
            
            print()


def main():
    """Основная функция для запуска тестирования"""
    print("🌐 Тестирование подключения через прокси")
    print("Проверяем, что каждый аккаунт использует правильный прокси")
    print()
    
    tester = ProxyConnectionTester()
    results = tester.test_all_accounts()
    tester.print_results(results)
    
    # Возвращаем код выхода
    if results['status'] == 'error':
        return 1
    elif results['status'] == 'warning':
        return 2
    else:
        return 0


if __name__ == '__main__':
    exit(main()) 