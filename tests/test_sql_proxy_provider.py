"""Offline checks for explicit proxy routing in SQL storage."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, NoReturn
from collections.abc import Callable
from unittest.mock import patch

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

_proxy_env_path: Path = Path(__file__).resolve().parents[1] / "src/implementations/proxy_storage/sql_proxy/.env"
_original_path_exists: Callable[[Path], bool] = Path.exists


def _offline_env_exists(path: Path) -> bool:
    """Allow provider imports without a real database configuration file."""
    return path == _proxy_env_path or _original_path_exists(path)


# These query tests use SQLite and must not require or load production credentials.
with patch.object(Path, "exists", _offline_env_exists), patch("dotenv.load_dotenv", return_value=False):
    from src.implementations.proxy_storage.sql_proxy.sqlalchemy_proxy_provider import AccountProxy, Base, SqlAlchemyProxyProvider


@pytest.fixture
def provider() -> Iterator[SqlAlchemyProxyProvider]:
    """Use the real provider query with an isolated in-memory database."""
    engine: Engine = create_engine("sqlite://").execution_options(schema_translate_map={"steam_accounts": None})
    Base.metadata.create_all(engine)
    instance: SqlAlchemyProxyProvider = SqlAlchemyProxyProvider.__new__(SqlAlchemyProxyProvider)
    instance.Session = sessionmaker(bind=engine)
    try:
        yield instance
    finally:
        engine.dispose()


@pytest.mark.parametrize("value", [None, "", " "])
def test_missing_or_empty_sql_proxy_is_rejected(provider: SqlAlchemyProxyProvider, value: str | None) -> None:
    """An empty database value must not be interpreted as no_proxy."""
    with provider.Session() as session, session.begin():
        session.add(AccountProxy(username="account", proxy=value))
    with pytest.raises(ValueError, match="no_proxy"):
        provider.get_proxy("account")


def test_missing_sql_account_is_rejected(provider: SqlAlchemyProxyProvider) -> None:
    """A missing row must prevent direct account access."""
    with pytest.raises(ValueError, match="no_proxy"):
        provider.get_proxy("missing")


def test_explicit_sql_no_proxy_is_allowed(provider: SqlAlchemyProxyProvider) -> None:
    """The explicit database marker permits a direct connection."""
    with provider.Session() as session, session.begin():
        session.add(AccountProxy(username="account", proxy=" no_proxy "))
    assert provider.get_proxy("account") is None


@pytest.mark.parametrize(
    "value,expected",
    [
        ("http://host:8080:user:pass", "http://user:pass@host:8080"),
        ("http://user:pass@host:8080", "http://user:pass@host:8080"),
        ("http://user:pa:ss@host:8080", "http://user:pa:ss@host:8080"),
    ],
)
def test_sql_proxy_preserves_account_endpoint(provider: SqlAlchemyProxyProvider, value: str, expected: str) -> None:
    """Legacy and standard URL formats must resolve to the configured host."""
    with provider.Session() as session, session.begin():
        session.add(AccountProxy(username="account", proxy=value))
    assert provider.get_proxy("account") == {"http": expected, "https": expected}


def test_sql_error_does_not_return_direct_route(provider: SqlAlchemyProxyProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    """Storage errors must reach the caller instead of returning None."""

    def fail_query(session: Session, *entities: Any, **kwargs: Any) -> NoReturn:
        raise SQLAlchemyError("Database unavailable")

    monkeypatch.setattr(Session, "query", fail_query)
    with pytest.raises(SQLAlchemyError):
        provider.get_proxy("account")
