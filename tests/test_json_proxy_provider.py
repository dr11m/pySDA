"""Tests for JSON proxy provider path resolution."""

import json
from pathlib import Path

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


def test_get_proxy_returns_none_for_missing_account(tmp_path: Path, monkeypatch) -> None:
    proxies_file = tmp_path / "proxies.json"
    proxies_file.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(
        "src.implementations.proxy_storage.json_proxy.provider.PROXIES_FILE",
        proxies_file,
    )

    provider = JsonProxyProvider()

    assert provider.get_proxy("missing_account") is None
