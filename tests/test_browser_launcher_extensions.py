"""Tests for browser extension package helpers."""

import io
import zipfile
from pathlib import Path

from browser_launcher.extension_package import extract_zip_bytes_from_crx, is_extension_installed


def test_extract_zip_bytes_from_crx_reads_crx3_payload() -> None:
    """CRX3 package should expose the embedded ZIP archive."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("manifest.json", '{"name": "test"}')

    zip_bytes = zip_buffer.getvalue()
    header_size = 0
    crx_data = b"Cr24" + (3).to_bytes(4, "little") + header_size.to_bytes(4, "little") + zip_bytes

    extracted = extract_zip_bytes_from_crx(crx_data)

    with zipfile.ZipFile(io.BytesIO(extracted)) as archive:
        assert archive.read("manifest.json") == b'{"name": "test"}'


def test_is_extension_installed_checks_manifest(tmp_path: Path) -> None:
    """Extension directory is valid only when manifest.json exists."""
    extension_dir = tmp_path / "simple-proxy-switcher"
    extension_dir.mkdir()

    assert is_extension_installed(extension_dir) is False

    (extension_dir / "manifest.json").write_text("{}", encoding="utf-8")

    assert is_extension_installed(extension_dir) is True
