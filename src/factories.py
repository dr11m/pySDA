#!/usr/bin/env python3
"""
Фабрика для динамического создания экземпляров классов.
"""

import importlib
from typing import Any, Dict

from src.utils.logger_setup import logger

def create_instance_from_config(config: Dict[str, Any], **kwargs) -> Any:
    """
    Динамически создает экземпляр класса на основе конфигурации.
    Класс-реализация должен сам получать свои параметры из окружения.
    
    Args:
        config: Словарь с ключами 'module_path' и 'class_name'.
        **kwargs: Дополнительные именованные аргументы для передачи в конструктор класса.
                  Это позволяет передавать runtime-параметры, такие как 'account_name'.
                  
    Returns:
        Экземпляр созданного класса.
    """
    module_path = config.get('module_path')
    class_name = config.get('class_name')
    
    if not module_path or not class_name:
        raise ValueError(f"Конфигурация не содержит 'module_path' или 'class_name': {config}")
    
    try:
        logger.info(f"Загрузка реализации: {module_path}.{class_name}")
        module = importlib.import_module(module_path)
        Class = getattr(module, class_name)
        
        # Создаем экземпляр, передавая дополнительные аргументы, если они есть
        return Class(**kwargs)
        
    except (ImportError, AttributeError) as e:
        logger.error(f"❌ Не удалось загрузить или найти класс: {module_path}.{class_name}")
        raise ImportError(f"Не удалось импортировать {class_name} из {module_path}") from e
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при создании экземпляра {class_name}: {e}")
        raise 