from loguru import logger
import os
import yaml

def load_debug_config():
    """Загружает только debug настройки для логирования из config.yaml"""
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
            return config.get('debug_console_output', False)
    except Exception:
        # Если файл не найден или ошибка - возвращаем дефолт
        return False

# Загружаем только debug настройку для логирования
debug_console_output = load_debug_config()

# Создаём папку для логов если её нет
os.makedirs("logs", exist_ok=True)

# Убираем стандартный вывод в консоль только если debug_console_output = False
if not debug_console_output:
    logger.remove()

# Настройка основного лога (только в файл)
logger.add(
    "logs/log.log", 
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {function} | {message}", 
    rotation="10 MB", 
    retention=3,
    level="DEBUG"
)

# Настройка лога для ошибок (только в файл)
logger.add(
    "logs/error.log", 
    backtrace=True, 
    diagnose=True, 
    rotation="5 MB", 
    retention=2, 
    filter=lambda record: record["level"].name == "ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {function} | {message}"
)

def print_and_log(message: str, level: str = "INFO"):
    """
    Выводит сообщение в консоль и записывает в лог.
    
    Args:
        message: Сообщение для вывода
        level: Уровень логирования (INFO, WARNING, ERROR, SUCCESS)
    """
    # Выводим в консоль
    print(message)
    
    # Записываем в лог
    if level == "INFO":
        logger.info(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "ERROR":
        logger.error(message)
    elif level == "SUCCESS":
        logger.success(message)
    elif level == "DEBUG":
        logger.debug(message)
    else:
        logger.info(message)
