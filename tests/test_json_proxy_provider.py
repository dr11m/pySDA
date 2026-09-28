"""Tests for JSON proxy provider path resolution."""

import json
from pathlib import Path

import pytest

from src.implementations.proxy_storage.json_proxy.provider import PROXIES_FILE, JsonProxyProvider


def test_proxies_file_path_points_to_json_proxy_directory() -> None:
    assert PROXIES_FILE == Path(__file__).resolve().parents[1] / (
        "src/implementations/proxy_storage/json_proxy/proxies.json"
    )


def test_get_proxy_converts_host_port_user_password_format(tmp_path: Path, monkeypatch) -> None:
    proxies_file = tmp_path / "proxies.json"
    proxies_file.write_text(
        json.dumps({"account_a": "http://host:8080:user:pass"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.implementations.proxy_storage.json_proxy.provider.PROXIES_FILE",
        proxies_file,
    )

    provider = JsonProxyProvider()
    proxy = provider.get_proxy("account_a")

    assert proxy == {
        "http": "http://user:pass@host:8080",
        "https": "http://user:pass@host:8080",
    }


def test_get_proxy_keeps_standard_url_format(tmp_path: Path, monkeypatch) -> None:
    proxies_file = tmp_path / "proxies.json"
    proxies_file.write_text(
        json.dumps({"account_a": "http://user:pass@host:8080"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.implementations.proxy_storage.json_proxy.provider.PROXIES_FILE",
        proxies_file,
    )

    provider = JsonProxyProvider()
    proxy = provider.get_proxy("account_a")

    assert proxy == {
        "http": "http://user:pass@host:8080",
        "https": "http://user:pass@host:8080",
    }


def test_get_proxy_rejects_missing_account(tmp_path: Path, monkeypatch) -> None:
    proxies_file = tmp_path / "proxies.json"
    proxies_file.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(
        "src.implementations.proxy_storage.json_proxy.provider.PROXIES_FILE",
        proxies_file,
    )

    provider = JsonProxyProvider()

    with pytest.raises(ValueError, match="no_proxy"):
        provider.get_proxy("missing_account")


@pytest.mark.parametrize("value", ["", "   "])
def test_get_proxy_rejects_empty_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """An empty mapping must not silently allow direct access."""
    proxies_file: Path = tmp_path / "proxies.json"
    proxies_file.write_text(json.dumps({"account_a": value}), encoding="utf-8")
    monkeypatch.setattr("src.implementations.proxy_storage.json_proxy.provider.PROXIES_FILE", proxies_file)
    provider: JsonProxyProvider = JsonProxyProvider()
    with pytest.raises(ValueError, match="no_proxy"):
        provider.get_proxy("account_a")


def test_get_proxy_allows_explicit_no_proxy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only an explicit no_proxy entry allows the direct account route."""
    proxies_file: Path = tmp_path / "proxies.json"
    proxies_file.write_text(json.dumps({"account_a": " no_proxy "}), encoding="utf-8")
    monkeypatch.setattr("src.implementations.proxy_storage.json_proxy.provider.PROXIES_FILE", proxies_file)
    provider: JsonProxyProvider = JsonProxyProvider()
    assert provider.get_proxy("account_a") is None


def test_missing_proxy_file_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing proxy file must fail instead of producing direct routes."""
    monkeypatch.setattr("src.implementations.proxy_storage.json_proxy.provider.PROXIES_FILE", tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        JsonProxyProvider()
