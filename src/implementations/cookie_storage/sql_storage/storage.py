#!/usr/bin/env python3
"""SQLAlchemy storage implementation for Steam account cookies."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, Dict, Optional

from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, Engine, Integer, String, Text, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from src.interfaces.storage_interface import CookieStorageInterface
from src.utils.logger_setup import logger, log_exception


env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    raise FileNotFoundError(
        f"Missing .env file at {env_path}. "
        "SqlAlchemyCookieStorage requires DB_CONNECTION_STRING in this directory."
    )

load_dotenv(dotenv_path=env_path)
DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")

# Client keepalives hold NAT mappings open and drop dead links in ~60s, so a silently broken
# connection is not left behind as an idle server backend until the server's own 2h keepalive.
PG_CONNECT_ARGS: dict[str, int | str] = {
    "application_name": "pySDA",
    "connect_timeout": 10,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}

Base = declarative_base()


class SteamAccount(Base):
    """Table model for storing Steam account cookies."""

    __tablename__ = "cookies"
    __table_args__ = {"schema": "steam_accounts"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    cookies = Column(Text, nullable=True)
    update_time = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<SteamAccount(username='{self.username}')>"


class SqlAlchemyCookieStorage(CookieStorageInterface):
    """Persist account cookies in PostgreSQL via SQLAlchemy."""

    # A storage is built on every account check; one engine per process keeps the PG connection count bounded.
    _engine: ClassVar[Engine | None] = None

    def __init__(self, **kwargs):
        if not DB_CONNECTION_STRING:
            raise ValueError(
                "Environment variable 'DB_CONNECTION_STRING' is not set. "
                "Cannot initialize SqlAlchemyCookieStorage."
            )

        logger.info("Initializing SqlAlchemyCookieStorage...")
        if SqlAlchemyCookieStorage._engine is None:
            engine: Engine = self._create_engine()
            self._create_schema_and_tables(engine)
            # Cache only after the schema check succeeds so a failed first start is retried next time.
            SqlAlchemyCookieStorage._engine = engine
            logger.debug("Created shared SqlAlchemyCookieStorage engine")
        self.engine: Engine = SqlAlchemyCookieStorage._engine
        self.Session = sessionmaker(bind=self.engine)
        logger.info("SqlAlchemyCookieStorage initialized.")

    @staticmethod
    def _create_engine() -> Engine:
        """Configure SQLAlchemy engine and connection pool."""
        return create_engine(
            DB_CONNECTION_STRING,
            poolclass=QueuePool,
            pool_size=2,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
            connect_args=PG_CONNECT_ARGS,
        )

    @staticmethod
    def _create_schema_and_tables(engine: Engine) -> None:
        """Create schema and tables if they do not exist."""
        try:
            with engine.connect() as connection:
                connection.execute(text("CREATE SCHEMA IF NOT EXISTS steam_accounts"))
                connection.commit()
                logger.info("Schema 'steam_accounts' verified.")
            Base.metadata.create_all(engine)
            logger.info("Tables in schema 'steam_accounts' verified.")
        except Exception:
            log_exception("Failed to create SQL schema or tables for cookie storage.")
            raise

    def save_cookies(self, username: str, cookies: Dict[str, str]) -> bool:
        """Insert or update cookies for a specific account."""
        try:
            with self.Session() as session, session.begin():
                existing_record = session.query(SteamAccount).filter_by(username=username).first()
                if existing_record:
                    existing_record.cookies = json.dumps(cookies)
                    existing_record.update_time = datetime.now(timezone.utc)
                else:
                    session.add(
                        SteamAccount(
                            username=username,
                            cookies=json.dumps(cookies),
                            update_time=datetime.now(timezone.utc),
                        )
                    )
            return True
        except Exception:
            log_exception(f"Failed to save cookies in SQL storage for '{username}'.")
            return False

    def load_cookies(self, username: str) -> Optional[Dict[str, str]]:
        """Load cookies for a specific account."""
        try:
            with self.Session() as session:
                record = session.query(SteamAccount).filter_by(username=username).first()
                if record and record.cookies:
                    return json.loads(record.cookies)
            return None
        except Exception:
            log_exception(f"Failed to load cookies from SQL storage for '{username}'.")
            return None

    def delete_cookies(self, username: str) -> bool:
        """Delete cookie row for a specific account."""
        try:
            with self.Session() as session, session.begin():
                record = session.query(SteamAccount).filter_by(username=username).first()
                if record:
                    session.delete(record)
            return True
        except Exception:
            log_exception(f"Failed to delete cookies from SQL storage for '{username}'.")
            return False

    def get_last_update(self, username: str) -> Optional[datetime]:
        """Return last update timestamp for account cookies."""
        try:
            with self.Session() as session:
                record = session.query(SteamAccount).filter_by(username=username).first()
                if record and record.update_time:
                    return record.update_time
            return None
        except Exception:
            log_exception(f"Failed to read last update timestamp for '{username}'.")
            return None


if __name__ == "__main__":
    if not env_path.exists():
        print(f"❌ Missing .env file at {env_path}")
    elif not DB_CONNECTION_STRING:
        print("❌ DB_CONNECTION_STRING is not set in .env")
    else:
        try:
            storage = SqlAlchemyCookieStorage()
            print(f"✅ Cookie storage initialized: {storage.__class__.__name__}")
        except Exception as error:
            print(f"❌ Failed to initialize cookie storage: {error}")
