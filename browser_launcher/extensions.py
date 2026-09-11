"""Discover unpacked Chrome extensions for persistent browser contexts.

Playwright's bundled Chromium cannot install extensions from the Chrome Web
Store or load packed .crx files. The supported way is loading an unpacked
extension directory via Chromium flags:

    --disable-extensions-except=<dir> --load-extension=<dir>

Extension sources live in the fixed ``browser_extensions/`` directory: each
subfolder containing a manifest.json is one loadable extension. Packed .crx
files must be unpacked manually before launch.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List

from loguru import logger

EXTENSIONS_DIR = Path("browser_extensions")


@dataclass(frozen=True)
class ExtensionInfo:
    """One loadable unpacked extension found on disk."""

    name: str
    path: str


def discover_extensions() -> List[ExtensionInfo]:
    """Scan the fixed extensions directory for unpacked extensions."""
    found: List[ExtensionInfo] = []
    if not EXTENSIONS_DIR.is_dir():
        logger.debug("Extensions directory '{}' not found", EXTENSIONS_DIR)
        return found
    entries = sorted(EXTENSIONS_DIR.iterdir(), key=lambda entry: entry.name)
    skipped: int = 0
    for entry in entries:
        if entry.is_dir() and (entry / "manifest.json").is_file():
            found.append(ExtensionInfo(name=entry.name, path=str(entry.resolve())))
        else:
            skipped += 1
    total: int = len(entries)
    logger.debug(
        "Extensions discovered: total={}, passed={}, rejected={} | not_unpacked={}",
        total,
        len(found),
        skipped,
        skipped,
    )
    return found


def build_extension_args(extension_paths: List[str]) -> List[str]:
    """Build Chromium flags that force-load the given unpacked extensions."""
    if not extension_paths:
        return []
    joined: str = ",".join(extension_paths)
    return [
        f"--disable-extensions-except={joined}",
        f"--load-extension={joined}",
    ]
