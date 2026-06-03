"""Tests for CLI configuration validation."""

from pathlib import Path

from src.cli.config_manager import ConfigManager


def _write_config(config_path: Path, mafile_path: str) -> None:
    normalized_mafile_path = mafile_path.replace("\\", "/")
    config_path.write_text(
        "\n".join(
            [
                "accounts:",
                "  test_account:",
                '    username: "test_user"',
                '    password: "test_pass"',
                f'    mafile_path: "{normalized_mafile_path}"',
                '    steam_id: "76561198000000000"',
            ]
        ),
        encoding="utf-8",
    )


def test_validate_config_with_existing_mafile(tmp_path: Path) -> None:
    mafile = tmp_path / "test_account.maFile"
    mafile.write_text('{"steamid": 123, "shared_secret": "x", "identity_secret": "y"}', encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    _write_config(config_path, str(mafile))

    manager = ConfigManager(config_path=str(config_path))
    assert manager.load_config() is True
    assert manager.select_account("test_account") is True
    assert manager.validate_config() is True


def test_validate_config_with_missing_mafile(tmp_path: Path) -> None:
    missing_mafile = tmp_path / "missing.maFile"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, str(missing_mafile))

    manager = ConfigManager(config_path=str(config_path))
    assert manager.load_config() is True
    assert manager.select_account("test_account") is True
    assert manager.validate_config() is False


def test_validate_config_with_case_mismatched_mafile(tmp_path: Path) -> None:
    # Файл на диске имеет расширение .mafile (строчная f)
    mafile = tmp_path / "test_account.mafile"
    mafile.write_text('{"steamid": 123, "shared_secret": "x", "identity_secret": "y"}', encoding="utf-8")

    # В конфигурации указано расширение .maFile (заглавная F)
    config_mafile_path = tmp_path / "test_account.maFile"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, str(config_mafile_path))

    manager = ConfigManager(config_path=str(config_path))
    assert manager.load_config() is True
    assert manager.select_account("test_account") is True
    
    # Должен успешно валидироваться благодаря fallback
    assert manager.validate_config() is True
    
    # Путь в конфигурации должен обновиться на существующий файл на диске
    updated_path = Path(manager.active_account_config['mafile_path'])
    assert updated_path.name == "test_account.mafile"

