"""Regressions for concurrent password persistence and account ownership."""

import multiprocessing
import os
from multiprocessing.connection import Connection
from multiprocessing.context import BaseContext
from multiprocessing.process import BaseProcess
from multiprocessing.synchronize import Event
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from src.cli.config_manager import ConfigManager


def _write_config(path: Path) -> None:
    """Create two accounts with distinct identities and passwords."""
    path.write_text(
        "# retain this comment\naccounts:\n"
        "  selected:\n    username: first_login\n    steam_id: '76561198000000000'\n    password: first-old\n"
        "  other:\n    username: other_login\n    steam_id: '76561198000000001'\n    password: other-old\n"
        "request_read_timeout_seconds: 30\n",
        encoding="utf-8",
    )


def _persist_in_process(
    config_path: str,
    account_name: str,
    password: str,
    loaded: Event,
    start: Event,
    updating: Event,
    completed: Event,
    result: Connection,
    before_replace: Event | None = None,
    release_replace: Event | None = None,
) -> None:
    """Persist in a separate process, optionally pausing after reading the file."""
    manager: ConfigManager = ConfigManager(config_path)
    assert manager.load_config()
    loaded.set()
    assert start.wait(10)
    original_replace: Any = os.replace

    def paused_replace(source: Path, destination: Path) -> None:
        assert before_replace is not None and release_replace is not None
        before_replace.set()
        assert release_replace.wait(10)
        original_replace(source, destination)

    try:
        updating.set()
        if before_replace is None:
            manager.update_account_password(account_name, password)
        else:
            with patch("os.replace", paused_replace):
                manager.update_account_password(account_name, password)
        result.send(None)
    except Exception as error:
        result.send(type(error).__name__)
    finally:
        result.close()
        completed.set()


def test_concurrent_processes_preserve_both_account_passwords(tmp_path: Path) -> None:
    """A delayed replacement must not overwrite another process's password update."""
    config_path: Path = tmp_path / "config.yaml"
    _write_config(config_path)
    context: BaseContext = multiprocessing.get_context("spawn")
    first_loaded: Event = context.Event()
    second_loaded: Event = context.Event()
    first_start: Event = context.Event()
    second_start: Event = context.Event()
    first_updating: Event = context.Event()
    second_updating: Event = context.Event()
    first_completed: Event = context.Event()
    second_completed: Event = context.Event()
    before_replace: Event = context.Event()
    release_replace: Event = context.Event()
    first_result: Connection
    first_output: Connection
    first_result, first_output = context.Pipe(duplex=False)
    second_result: Connection
    second_output: Connection
    second_result, second_output = context.Pipe(duplex=False)
    first: BaseProcess = context.Process(
        target=_persist_in_process,
        args=(
            str(config_path),
            "selected",
            "first-new",
            first_loaded,
            first_start,
            first_updating,
            first_completed,
            first_output,
            before_replace,
            release_replace,
        ),
    )
    second: BaseProcess = context.Process(
        target=_persist_in_process,
        args=(str(config_path), "other", "other-new", second_loaded, second_start, second_updating, second_completed, second_output),
    )
    first.start()
    second.start()
    try:
        assert first_loaded.wait(10) and second_loaded.wait(10)
        first_start.set()
        assert before_replace.wait(10)
        second_start.set()
        assert second_updating.wait(10)
        # Without serialization, the second process finishes before the stale first replacement.
        second_completed.wait(1)
    finally:
        release_replace.set()
        for process in (first, second):
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(10)
        first_output.close()
        second_output.close()

    assert first.exitcode == second.exitcode == 0
    assert first_result.poll(1) and second_result.poll(1)
    assert first_result.recv() is None
    assert second_result.recv() is None
    first_result.close()
    second_result.close()
    document: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert document["accounts"]["selected"]["password"] == "first-new"
    assert document["accounts"]["other"]["password"] == "other-new"
    assert document["request_read_timeout_seconds"] == 30
    assert config_path.read_text(encoding="utf-8").startswith("# retain this comment")


@pytest.mark.parametrize("field,replacement", [("username", "replacement_login"), ("steam_id", "76561198000000002")])
def test_password_update_rejects_account_alias_remap(tmp_path: Path, field: str, replacement: str) -> None:
    """A password verified for the original owner must not be saved under a remapped alias."""
    config_path: Path = tmp_path / "config.yaml"
    _write_config(config_path)
    manager: ConfigManager = ConfigManager(str(config_path))
    assert manager.load_config()
    document: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    document["accounts"]["selected"][field] = replacement
    config_path.write_text(yaml.safe_dump(document), encoding="utf-8")
    remapped: bytes = config_path.read_bytes()

    with pytest.raises(ValueError):
        manager.update_account_password("selected", "first-new")

    assert config_path.read_bytes() == remapped
    assert manager.accounts_settings["selected"]["password"] == "first-old"
