"""Tests for browser extension discovery and launch flags."""

from pathlib import Path

from browser_launcher import extensions
from browser_launcher.extensions import build_extension_args, discover_extensions


def _unpacked_extension(root: Path, name: str) -> Path:
    """Create a fake unpacked extension directory with a manifest."""
    ext_dir = root / name
    ext_dir.mkdir(parents=True)
    (ext_dir / "manifest.json").write_text("{}", encoding="utf-8")
    return ext_dir


def test_discover_finds_unpacked_dirs_and_skips_other_files(
    tmp_path: Path, monkeypatch
) -> None:
    """Only subfolders with manifest.json should be reported, sorted by name."""
    _unpacked_extension(tmp_path, "b-ext")
    _unpacked_extension(tmp_path, "a-ext")
    (tmp_path / "empty-dir").mkdir()
    (tmp_path / "something.crx").write_text("fake", encoding="utf-8")
    monkeypatch.setattr(extensions, "EXTENSIONS_DIR", tmp_path)

    found = discover_extensions()

    assert [info.name for info in found] == ["a-ext", "b-ext"]
    assert all(info.path for info in found)


def test_discover_returns_empty_when_dir_missing(tmp_path: Path, monkeypatch) -> None:
    """Missing extensions directory should mean no extensions."""
    monkeypatch.setattr(extensions, "EXTENSIONS_DIR", tmp_path / "absent")

    assert discover_extensions() == []


def test_build_extension_args_empty() -> None:
    """No extensions should add no Chromium flags."""
    assert build_extension_args([]) == []


def test_build_extension_args_joins_paths() -> None:
    """Chosen extensions should be force-loaded via Chromium flags."""
    args = build_extension_args(["/ext/a", "/ext/b"])

    assert args == [
        "--disable-extensions-except=/ext/a,/ext/b",
        "--load-extension=/ext/a,/ext/b",
    ]
