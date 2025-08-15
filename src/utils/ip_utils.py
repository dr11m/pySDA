#!/usr/bin/env python3
"""
Утилиты для работы с IP адресами
"""
import requests
from requests import Session
from src.utils.logger_setup import logger

def check_ip(session: Session) -> None:
    """
    Проверяет и выводит в лог IP-адрес, используя предоставленную сессию.
    """
    try:
        response = session.get("https://api.ipify.org?format=json", timeout=10)
        if response.status_code == 200:
            ip = response.json().get('ip', 'N/A')
            logger.info(f"💡 IP check: {ip}")
        else:
            logger.warning(f"⚠️ IP check failed with status code: {response.status_code}")
    except requests.RequestException as e:
        logger.error(f"❌ IP check request failed: {e}")
