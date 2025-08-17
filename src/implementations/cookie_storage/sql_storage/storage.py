#!/usr/bin/env python3
"""
Реализация интерфейса хранения cookies с использованием PostgreSQL и SQLAlchemy.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional

from dotenv import load_dotenv

from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

from src.interfaces.storage_interface import CookieStorageInterface
from src.utils.logger_setup import logger

env_path = Path(__file__).parent / '.env'
if not env_path.exists():
    # Если используется эта реализация, .env файл ОБЯЗАТЕЛЕН.
    raise FileNotFoundError(
        f"Файл .env не найден по пути {env_path}. "
        f"Для использования SqlAlchemyCookieStorage необходимо создать .env в папке implementations с переменной DB_CONNECTION_STRING. "
        f"Скопируйте env.example из этой же папки в корень проекта и переименуйте в .env."
    )
load_dotenv(dotenv_path=env_path)


DB_CONNECTION_STRING = os.getenv("DB_CONNECTION_STRING")

Base = declarative_base()

class SteamAccount(Base):
    """Модель для таблицы, хранящей cookies аккаунтов Steam."""
    __tablename__ = 'cookies'
    __table_args__ = {'schema': 'steam_accounts'}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    cookies = Column(Text, nullable=True)  # JSON строка с cookies
    update_time = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<SteamAccount(username='{self.username}')>"


class SqlAlchemyCookieStorage(CookieStorageInterface):
    """
    Хранит cookies в PostgreSQL.
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
                "Невозможно инициализировать SqlAlchemyCookieStorage. "
                "Добавьте ее в ваш .env файл."
            )
            
        logger.info("🚀 Инициализация SqlAlchemyCookieStorage...")
        self._setup_engine()
        
        # Создаем схему и таблицы
        self._create_schema_and_tables()
        
        self.Session = sessionmaker(bind=self.engine)
        logger.info("✅ SqlAlchemyCookieStorage успешно инициализирован.")

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
            pool_size=2,          # Начальное количество соединений в пуле
            max_overflow=5,      # Максимальное количество "дополнительных" соединений
            pool_pre_ping=True,   # Проверять соединение перед использованием
            pool_recycle=3600,    # Пересоздавать соединение каждые 3600 сек (1 час)
            echo=False,           # Не логировать SQL-запросы в консоль
        )

    def save_cookies(self, username: str, cookies: Dict[str, str]) -> bool:
        session = self.Session()
        try:
            # Ищем существующую запись
            existing_record = session.query(SteamAccount).filter_by(username=username).first()
            
            if existing_record:
                # Обновляем существующую запись
                existing_record.cookies = json.dumps(cookies)
                existing_record.update_time = datetime.now(timezone.utc)
                logger.info(f"✅ Cookies для {username} обновлены в БД")
            else:
                # Создаем новую запись
                new_record = SteamAccount(
                    username=username,
                    cookies=json.dumps(cookies),
                    update_time=datetime.now(timezone.utc)
                )
                session.add(new_record)
                logger.info(f"✅ Cookies для {username} созданы в БД")
            
            session.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения cookies в БД для {username}: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def load_cookies(self, username: str) -> Optional[Dict[str, str]]:
        session = self.Session()
        try:
            record = session.query(SteamAccount).filter_by(username=username).first()
            if record and record.cookies:
                return json.loads(record.cookies)
            return None
        except Exception as e:
            logger.error(f"Ошибка загрузки cookies из БД для {username}: {e}")
            return None
        finally:
            session.close()

    def delete_cookies(self, username: str) -> bool:
        session = self.Session()
        try:
            record = session.query(SteamAccount).filter_by(username=username).first()
            if record:
                session.delete(record)
                session.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления cookies из БД для {username}: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_last_update(self, username: str) -> Optional[datetime]:
        session = self.Session()
        try:
            record = session.query(SteamAccount).filter_by(username=username).first()
            if record and record.update_time:
                # Возвращаем время с timezone как есть
                return record.update_time
            return None
        except Exception as e:
            logger.error(f"Ошибка получения времени обновления из БД для {username}: {e}")
            return None
        finally:
            session.close() 


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
            print("🚀 Создание схемы и таблиц для cookie storage...")
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
                print("🎉 Инициализация cookie storage завершена!")
                
            except Exception as e:
                print(f"❌ Ошибка: {e}")
        else:
            print("❌ DB_CONNECTION_STRING не найден в .env файле")
    else:
        print(f"❌ .env файл не найден по пути {env_path}")