from loguru import logger
import os

# Создаём папку для логов если её нет
os.makedirs("logs", exist_ok=True)

# Убираем стандартный вывод в консоль
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
