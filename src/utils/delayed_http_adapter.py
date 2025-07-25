#!/usr/bin/env python3
"""
Реализация кастомного HTTPAdapter для requests, который добавляет
задержку после каждого выполненного запроса.
"""
import time
from requests.adapters import HTTPAdapter
from src.utils.logger_setup import logger

class DelayedHTTPAdapter(HTTPAdapter):
    """
    Кастомный HTTP-адаптер, который вносит задержку после каждого запроса.
    """
    def __init__(self, *args, delay: float = 0, **kwargs):
        """
        :param delay: Задержка в секундах, которая будет выполнена ПОСЛЕ запроса.
        """
        self.delay = delay
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        """
        Отправляет запрос и затем выполняет задержку.
        """
        try:
            # Выполняем оригинальный запрос, вызывая метод родительского класса
            response = super().send(request, **kwargs)
            return response
        finally:
            # Независимо от результата запроса (успех или ошибка),
            # выполняем задержку.
            if hasattr(self, 'delay') and self.delay > 0:
                logger.debug(f"Пауза на {self.delay:.2f} сек после запроса к {request.url}")
                time.sleep(self.delay) 