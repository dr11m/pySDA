#!/usr/bin/env python3
"""
Константы для CLI интерфейса
"""

from enum import Enum


class MenuChoice(Enum):
    """Варианты выбора в главном меню"""
    UPDATE_COOKIES = "1"
    MANAGE_TRADES = "2"
    CONFIRM_MARKET = "3"
    GET_GUARD_CODE = "4"
    SETTINGS = "5"
    AUTO_ACCEPT = "6"
    EXIT = "0"


class TradeMenuChoice(Enum):
    """Варианты выбора в меню управления трейдами"""
    ACCEPT_GIFTS = "1"
    CONFIRM_ALL = "2"
    ACCEPT_SPECIFIC = "3"
    CONFIRM_SPECIFIC = "4"
    BACK = "0"


class SettingsMenuChoice(Enum):
    """Варианты выбора в меню настроек"""
    ADD_MAFILE = "1"
    GET_API_KEY = "2"
    BACK = "0"


class AutoMenuChoice(Enum):
    """Варианты выбора в меню автоматизации"""
    AUTO_SETTINGS = "1"
    START_AUTO = "2"
    BACK = "0"


class Messages:
    """Сообщения для пользователя"""
    
    # Заголовки
    MAIN_TITLE = "🤖 STEAM BOT CLI"
    TRADES_TITLE = "📋 УПРАВЛЕНИЕ ТРЕЙДАМИ"
    SETTINGS_TITLE = "⚙️  НАСТРОЙКИ"
    AUTO_TITLE = "🔄 АВТОМАТИЗАЦИЯ"
    
    # Основные действия
    UPDATE_COOKIES = "🍪 Принудительно обновить cookies"
    GET_TRADES = "📋 Получить активные трейды"
    MANAGE_TRADES = "🔄 Управление трейдами"
    CONFIRM_MARKET = "🏪 Принять все buy/sell ордера"
    GET_GUARD_CODE = "🔑 Получить Guard код"
    SETTINGS = "⚙️  Настройки"
    AUTO_ACCEPT = "🤖 Авто принятие"
    EXIT = "🚪 Выход"
    BACK = "⬅️  Назад"
    
    # Трейд действия
    ACCEPT_GIFTS = "🎁 Принять все подарки"
    CONFIRM_ALL = "🔑 Подтвердить все через Guard"
    ACCEPT_SPECIFIC = "✅ Принять конкретный трейд"
    CONFIRM_SPECIFIC = "🔑 Подтвердить конкретный трейд через Guard"
    
    # Настройки
    ADD_MAFILE = "📁 Добавить mafile"
    GET_API_KEY = "🔑 Получение API ключа"
    
    # Автоматизация
    AUTO_SETTINGS = "⚙️  Настройки автоматизации"
    START_AUTO_ACCEPT = "▶️  Включить авто принятие"
    STOP_AUTO_ACCEPT = "⏹️  Остановить авто принятие"
    
    # Статусы
    SUCCESS = "✅"
    ERROR = "❌"
    INFO = "ℹ️"
    WARNING = "⚠️"
    
    # Ошибки
    INVALID_CHOICE = "❌ Неверный выбор"
    INVALID_NUMBER = "❌ Введите корректный номер"
    NO_TRADES = "❌ Сначала получите список активных трейдов"
    NO_TRADES_FROM_MENU = "❌ Сначала получите список трейдов из главного меню"
    INIT_ERROR = "❌ Не удалось инициализировать бота"
    CONFIG_NOT_FOUND = "❌ Файл конфигурации не найден"
    COOKIES_ERROR = "❌ Не удалось получить актуальные cookies"
    MAFILE_NOT_FOUND = "❌ Указанный mafile не найден"
    MAFILE_INVALID = "❌ Некорректный mafile: {error}"
    MAFILE_COPY_ERROR = "❌ Ошибка копирования mafile: {error}"
    
    # Успешные операции
    INIT_SUCCESS = "✅ Инициализация завершена для пользователя"
    COOKIES_UPDATED = "✅ Cookies успешно обновлены! Получено {count} cookies"
    COOKIES_VALID = "✅ Cookies актуальны"
    COOKIES_AUTO_UPDATED = "🔄 Cookies автоматически обновлены"
    TRADE_ACCEPTED = "✅ Трейд {trade_id} успешно принят в веб-интерфейсе"
    TRADE_CONFIRMED = "✅ Трейд {trade_id} успешно подтвержден через Guard"
    GUARD_CODE_GENERATED = "🔑 Guard код сгенерирован:\n{code}"
    MAFILE_COPIED = "✅ Mafile успешно скопирован в {destination}"
    MAFILE_UPDATED = "✅ Mafile для аккаунта {username} обновлен"
    API_KEY_FOUND = "✅ API ключ найден: {key}"
    API_KEY_CREATED = "✅ API ключ успешно создан: {key}"
    API_KEY_CREATION_PENDING = "⏳ Запрос на создание API ключа отправлен"
    API_KEY_CONFIRMED = "✅ API ключ подтвержден через Guard"
    MARKET_CONFIRMATIONS_SUCCESS = "✅ Подтверждено {count} market ордеров"
    MARKET_CONFIRMATION_SUCCESS = "✅ Market ордер {id} подтвержден"
    
    # Информационные сообщения
    NO_CONFIRMATION_TRADES = "ℹ️ Нет трейдов, требующих подтверждения через Guard"
    NO_CONFIRMATION_TRADES_HINT = "💡 Все трейды либо уже подтверждены, либо не требуют Guard подтверждения"
    API_KEY_NOT_FOUND = "ℹ️ API ключ не найден на аккаунте"
    API_KEY_REQUIRES_EMAIL = "⚠️ Для получения API ключа необходимо подтвердить email адрес"
    API_KEY_ERROR = "❌ Ошибка получения API ключа: {error}"
    API_KEY_CREATION_FAILED = "❌ Не удалось создать API ключ"
    API_KEY_CONFIRMATION_NEEDED = "🔑 Требуется подтверждение через Steam Guard"
    NO_MARKET_CONFIRMATIONS = "ℹ️ Нет market ордеров, требующих подтверждения"
    MARKET_CONFIRMATIONS_FOUND = "🏪 Найдено {count} market ордеров для подтверждения"
    MARKET_CONFIRMATION_ERROR = "❌ Ошибка подтверждения market ордера: {error}"
    
    # Промпты
    CHOOSE_ACTION = "Выберите действие: "
    ENTER_TRADE_NUMBER = "Введите номер трейда (1-{max_num}): "
    CONFIRM_GUARD = "🔑 Подтвердить трейд через Guard? (y/n): "
    PRESS_ENTER = "Нажмите Enter для продолжения..."
    ENTER_MAFILE_PATH = "Введите полный путь к mafile: "
    MAFILE_PATH_HINT = "💡 Пример: C:\\Users\\Username\\Desktop\\myfile.maFile"
    MAFILE_PATH_HINT_LINUX = "💡 Пример: /home/username/Desktop/myfile.maFile"
    
    # Прощание
    GOODBYE = "👋 До свидания!"
    INTERRUPTED = "👋 Программа завершена пользователем"
    CRITICAL_ERROR = "💥 Критическая ошибка: {error}"


class Formatting:
    """Константы для форматирования"""
    
    SEPARATOR = "=" * 50
    LINE = "-" * 50
    SHORT_LINE = "-" * 30
    
    # Эмодзи для типов трейдов
    INCOMING = "📥"
    OUTGOING = "📤"
    EXCHANGE = "🔄"
    GIFT = "🎁"
    GIVE_AWAY = "💸"
    
    # Эмодзи для статусов
    LOADING = "🔄"
    COOKIE = "🍪"
    KEY = "🔑"
    WEB = "🌐"


class Config:
    """Конфигурационные константы"""
    
    DEFAULT_CONFIG_PATH = "config.yaml"
    ACCOUNTS_DIR = "accounts_info"
    
    # Обязательные поля конфигурации
    REQUIRED_FIELDS = ['username', 'password', 'mafile_path', 'steam_id']
    
    # Важные cookies
    IMPORTANT_COOKIES = ['sessionid', 'steamLoginSecure'] 