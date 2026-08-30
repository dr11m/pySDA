"""Bundled Chromium extensions for steam-browser."""

from pathlib import Path

from loguru import logger

from browser_launcher.extension_package import (
    DEFAULT_EXTENSION_DIR_NAME,
    is_extension_installed,
)

SIMPLE_PROXY_SWITCHER_ID = "pcboajngloecgmaailkmphmpbacmbcfb"
SIMPLE_PROXY_SWITCHER_STORE_URL = (
    "https://chromewebstore.google.com/detail/simple-proxy-switcher/"
    f"{SIMPLE_PROXY_SWITCHER_ID}"
)
BUNDLED_EXTENSIONS_DIR = Path(__file__).parent / "bundled_extensions"
DEFAULT_EXTENSION_DIR = BUNDLED_EXTENSIONS_DIR / DEFAULT_EXTENSION_DIR_NAME
UNPACK_SCRIPT_HINT = "uv run python scripts/unpack_browser_extension.py <path-to-extension.crx>"


def get_default_extension_path() -> Path | None:
    """Return bundled extension directory when unpacked files are present."""
    if is_extension_installed(DEFAULT_EXTENSION_DIR):
        logger.info("Using bundled extension: {}", DEFAULT_EXTENSION_DIR)
        return DEFAULT_EXTENSION_DIR

    logger.warning(
        "Bundled extension not found at {}. Install it with: {}",
        DEFAULT_EXTENSION_DIR,
        UNPACK_SCRIPT_HINT,
    )
    return None


def build_extension_launch_args(extension_dir: Path) -> list[str]:
    """Build Chromium args that load one unpacked extension."""
    resolved_path = str(extension_dir.resolve())
    return [
        f"--disable-extensions-except={resolved_path}",
        f"--load-extension={resolved_path}",
    ]
