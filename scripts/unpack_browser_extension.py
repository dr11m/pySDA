"""Unpack a Chrome extension CRX into the bundled browser_launcher folder."""

import sys
from pathlib import Path

from browser_launcher.extension_package import unpack_crx_file
from browser_launcher.extensions import DEFAULT_EXTENSION_DIR


def main() -> None:
    """Unpack CRX file for Simple Proxy Switcher."""
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: uv run python scripts/unpack_browser_extension.py <path-to-extension.crx>"
        )

    crx_path = Path(sys.argv[1])
    if not crx_path.is_file():
        raise SystemExit(f"CRX file not found: {crx_path}")

    unpack_crx_file(crx_path, DEFAULT_EXTENSION_DIR)
    print(f"Extension unpacked to: {DEFAULT_EXTENSION_DIR}")


if __name__ == "__main__":
    main()
