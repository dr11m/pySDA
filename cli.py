#!/usr/bin/env python3
"""
Steam Bot CLI - Точка входа
"""

import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

from cli_interface import run_cli

if __name__ == "__main__":
    run_cli() 