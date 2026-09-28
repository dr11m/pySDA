#!/usr/bin/env python3
"""
Реализация интерфейса ProxyProvider с использованием PostgreSQL и SQLAlchemy.
"""

import os
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv

from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

from src.interfaces.proxy_provider import ProxyProviderInterface
from src.utils.logger_setup import logger


env_path = Path(__file__).parent / '.env'
if not env_path.exists():
    # Если используется эта реализация, .env файл ОБЯЗАТЕЛЕН.
    raise FileNotFoundError(
        f"Файл .env не найден по пути {env_path}. "
        f"Для использования SqlAlchemyProxyProvider необходимо создать .env в папке implementations с переменной DB_CONNECTION_STRING. "
        f"Скопируйте env.example из этой же папки в корень проекта и переименуйте в .env."
    )
load_dotenv(dotenv_path=env_path)

DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")


Base = declarative_base()

class AccountProxy(Base):
    """Модель для таблицы, хранящей прокси для аккаунтов Steam."""
    __tablename__ = 'account_proxies'
    __table_args__ = {'schema': 'steam_accounts'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    proxy = Column(Text, nullable=True)  # Строка с прокси, JSON или спец. значение "no_proxy"
    update_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<AccountProxy(username='{self.username}')>"


class SqlAlchemyProxyProvider(ProxyProviderInterface):
    """
    Извлекает прокси для аккаунтов из PostgreSQL.
    Требует наличия переменной окружения DB_CONNECTION_STRING.
    """

    def __init__(self, **kwargs):
        """
        Инициализирует подключение к БД.
        Вызовет ошибку, если DB_CONNECTION_STRING не установлена.
        """
        if not DB_CONNECTION_STRING:
            raise ValueError(
                "Переменная окружения 'DB_CONNECTION_STRING' не установлена. "
                "Невозможно инициализировать SqlAlchemyProxyProvider. "
                "Добавьте ее в ваш .env файл."
            )
            
        logger.info("🚀 Инициализация SqlAlchemyProxyProvider...")
        self._setup_engine()
        
        # Создаем схему и таблицы
        self._create_schema_and_tables()
        
        self.Session = sessionmaker(bind=self.engine)
        logger.info("✅ SqlAlchemyProxyProvider успешно инициализирован.")

    def _create_schema_and_tables(self):
        """Создает схему steam_accounts и все необходимые таблицы."""
        try:
            # Создаем схему, если её нет
            with self.engine.connect() as connection:
                connection.execute(text("CREATE SCHEMA IF NOT EXISTS steam_accounts"))
                connection.commit()
                logger.info("✅ Схема 'steam_accounts' создана/проверена")
            
            # Создаем все таблицы
            Base.metadata.create_all(self.engine)
            logger.info("✅ Таблицы в схеме 'steam_accounts' созданы/проверены")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания схемы/таблиц: {e}")
            raise

    def _setup_engine(self):
        """Настройка SQLAlchemy engine с пулом соединений."""
        self.engine = create_engine(
            DB_CONNECTION_STRING,
            poolclass=QueuePool,
            pool_size=2,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )

    def get_proxy(self, account_name: str) -> dict[str, str] | None:
        """Load the account route; propagate missing settings and DB errors.

        Args:
            account_name: Account whose route is required.

        Returns:
            HTTP and HTTPS proxies, or None for the explicit no_proxy marker.

        Raises:
            ValueError: The account proxy is missing or empty.
        """
        with self.Session() as session:
            record: AccountProxy | None = session.query(AccountProxy).filter_by(username=account_name).first()
            if record is None or not record.proxy or not record.proxy.strip():
                raise ValueError(f"Proxy is not configured for account '{account_name}'; use 'no_proxy' for direct access")

            proxy_data: str = record.proxy.strip()
            if proxy_data.lower() == 'no_proxy':
                logger.info(f"Account '{account_name}' explicitly uses no_proxy")
                return None

            if "@" not in proxy_data and proxy_data.count(":") >= 3:
                if proxy_data.startswith('http://'):
                    proxy_data_: str = proxy_data[7:]
                    prefix: str = "http://"
                elif proxy_data.startswith('https://'):
                    proxy_data_ = proxy_data[8:]
                    prefix = 'https://'
                else:
                    proxy_data_ = proxy_data
                    prefix = 'http://'
                parts: list[str] = proxy_data_.split(":")
                if len(parts) >= 4:
                    host: str = parts[0]
                    port: str = parts[1]
                    username: str = parts[2]
                    password: str = parts[3]
                    formatted_proxy: str = f"{prefix}{username}:{password}@{host}:{port}"
                    return {
                        'http': formatted_proxy,
                        'https': formatted_proxy
                    }

            return {
                'http': proxy_data,
                'https': proxy_data 
            }
            


if __name__ == '__main__':
    """Скрипт для создания схемы и таблиц в базе данных."""
    import os
    from pathlib import Path
    from dotenv import load_dotenv
    
    # Загружаем .env файл
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        db_connection = os.getenv("DB_CONNECTION_STRING")
        
        if db_connection:
            print("🚀 Создание схемы и таблиц для proxy provider...")
            try:
                # Создаем engine
                engine = create_engine(db_connection)
                
                # Создаем схему
                with engine.connect() as connection:
                    connection.execute(text("CREATE SCHEMA IF NOT EXISTS steam_accounts"))
                    connection.commit()
                    print("✅ Схема 'steam_accounts' создана/проверена")
                
                # Создаем таблицы
                Base.metadata.create_all(engine)
                print("✅ Таблицы в схеме 'steam_accounts' созданы/проверены")
                print("🎉 Инициализация proxy provider завершена!")
                
            except Exception as e:
                print(f"❌ Ошибка: {e}")
        else:
            print("❌ DB_CONNECTION_STRING не найден в .env файле")
    else:
        print(f"❌ .env файл не найден по пути {env_path}")