"""Centralized Loguru configuration and logging helpers."""

import os
import sys

import yaml
from loguru import logger


LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"


def load_debug_config() -> bool:
    """Load debug logging flag from config.yaml."""
    try:
        with open("config.yaml", "r", encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}
            return bool(config.get("debug_console_output", False))
    except Exception:
        return False


debug_console_output = load_debug_config()
os.makedirs("logs", exist_ok=True)

# Windows consoles default to cp1251 which cannot encode emoji used in
# messages; without this both print() and loguru console sinks crash
# with UnicodeEncodeError.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logger.remove()

if debug_console_output:
    logger.add(
        sys.stdout,
        format=LOG_FORMAT,
        level="DEBUG",
        filter=lambda record: record["level"].no < 40,
    )

logger.add(
    "logs/log.log",
    format=LOG_FORMAT,
    rotation="10 MB",
    retention=3,
    level="DEBUG",
)

logger.add(
    "logs/error.log",
    format=LOG_FORMAT,
    rotation="5 MB",
    retention=2,
    level="ERROR",
    backtrace=True,
    diagnose=False,
)

logger.add(
    sys.stderr,
    format=LOG_FORMAT,
    level="ERROR",
    backtrace=True,
    diagnose=False,
)


def log_exception(message: str) -> None:
    """Log an active exception with traceback."""
    logger.exception(message)


def print_and_log(message: str, level: str = "INFO") -> None:
    """Print a message and log it with the provided severity level."""
    print(message)

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
