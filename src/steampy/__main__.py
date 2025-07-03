#!/usr/bin/env python3
"""
Точка входа для запуска steampy модулей как пакетов
"""

import sys
import argparse

def main():
    """Главная функция для запуска модулей"""
    
    parser = argparse.ArgumentParser(
        description="SteamPy - Инструменты для работы с Steam API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Доступные модули:
  session-manager    Управление Steam сессиями
  
Примеры:
  python -m steampy session-manager --username myuser --get-2fa
  python -m steampy session-manager --username myuser --monitor
        """
    )
    
    parser.add_argument(
        'module',
        choices=['session-manager'],
        help='Модуль для запуска'
    )
    
    # Парсим только первый аргумент (имя модуля)
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
    
    module_name = sys.argv[1]
    module_args = sys.argv[2:]
    
    if module_name == 'session-manager':
        from .session_manager import main as session_manager_main
        
        # Заменяем sys.argv для корректной работы argparse в модуле
        original_argv = sys.argv
        sys.argv = ['session_manager'] + module_args
        
        try:
            session_manager_main()
        finally:
            sys.argv = original_argv
    else:
        from src.utils.logger_setup import logger
        logger.error(f"Неизвестный модуль: {module_name}")
        print(f"Неизвестный модуль: {module_name}")
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main() 
