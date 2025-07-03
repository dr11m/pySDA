#!/usr/bin/env python3
"""
Steam Bot CLI - Точка входа
"""

import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cli_interface import main

if __name__ == "__main__":
    main() 