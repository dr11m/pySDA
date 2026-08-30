"""Pure helpers for unpacked Chromium extension packages."""

import io
import shutil
import zipfile
from pathlib import Path

DEFAULT_EXTENSION_DIR_NAME = "simple-proxy-switcher"


def is_extension_installed(extension_dir: Path) -> bool:
    """Return True when unpacked extension manifest exists."""
    return (extension_dir / "manifest.json").is_file()


def extract_zip_bytes_from_crx(crx_data: bytes) -> bytes:
    """Extract the ZIP payload from a CRX2/CRX3 package."""
    if crx_data[:4] != b"Cr24":
        return crx_data

    header_size = int.from_bytes(crx_data[8:12], byteorder="little")
    zip_start = 12 + header_size
    return crx_data[zip_start:]


def unpack_crx_archive(crx_data: bytes, extension_dir: Path) -> None:
    """Unpack a CRX archive into an extension directory."""
    prepare_extension_dir(extension_dir)
    zip_bytes = extract_zip_bytes_from_crx(crx_data)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        archive.extractall(extension_dir)


def unpack_crx_file(crx_path: Path, extension_dir: Path) -> None:
    """Unpack a CRX file from disk into an extension directory."""
    unpack_crx_archive(crx_path.read_bytes(), extension_dir)


def prepare_extension_dir(extension_dir: Path) -> None:
    """Create a clean extension directory."""
    if extension_dir.exists():
        shutil.rmtree(extension_dir)
    extension_dir.mkdir(parents=True, exist_ok=True)
