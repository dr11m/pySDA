"""Check that installed console entry points resolve to packaged callables."""

from importlib.metadata import EntryPoint, distribution
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest


@pytest.mark.parametrize("name", ["steam-bot", "steam-browser"])
def test_console_entry_point_resolves(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A published wheel must expose an importable console command."""
    monkeypatch.chdir(tmp_path)
    entry_point: EntryPoint = next(
        entry for entry in distribution("pySDA").entry_points if entry.group == "console_scripts" and entry.name == name
    )
    command: Callable[[], None] = entry_point.load()
    assert callable(command)


@pytest.mark.parametrize("module", ["src.cookie_manager", "src.trade_confirmation_manager"])
def test_library_imports_in_fresh_process(module: str, tmp_path: Path) -> None:
    """Library imports must work independently of pytest's collection order."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
