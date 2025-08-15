#!/usr/bin/env python3
"""
Утилиты для работы с IP адресами
"""
from src.utils.logger_setup import print_and_log


def check_ip(original_get_method) -> None:
    """
    Проверяет и выводит в лог IP-адрес, используя оригинальный метод get сессии.
    
    Args:
        original_get_method: Оригинальный метод get сессии (не переопределенный)
    """
    try:
        response = original_get_method("https://api.ipify.org?format=json", timeout=5)
        if response.status_code == 200:
            ip = response.json().get('ip', 'N/A')
            print_and_log(f"💡 IP check: {ip}")
        else:
            print_and_log(f"⚠️ IP check failed with status code: {response.status_code}")
    except Exception as e:
        print_and_log(f"❌ IP check request failed: {e}")
