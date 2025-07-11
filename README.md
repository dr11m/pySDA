# 🤖 pySDA - CLI Steam Bot

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Status](https://img.shields.io/badge/status-active-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

> **pySDA - CLI бот для автоматизации Steam подтверждений. Автоматически принимает бесплатные трейды и подарки, подтверждает операции через Steam Guard (весь функционал классического SDA и больше), обрабатывает market ордера, управляет сессиями с автообновлением cookies.**

## ✨ Основные возможности

- 📋 **Управление трейдами**: Получение, принятие в веб-интерфейсе и подтверждение через Steam Guard
- 🎁 **Автоматическое принятие подарков**: Принятие в веб-интерфейсе когда вам дают предметы бесплатно
- 🔑 **Steam Guard интеграция**: Автоматическое подтверждение принятых трейдов через SDA
- 🍪 **Управление сессией**: Автоматическое обновление cookies
- 🏪 **Работа с маркетом**: Подтверждение покупок/продаж
- 🤖 **Автоматизация**: Непрерывная работа с настраиваемыми параметрами
- ⚙️ **Настройки**: Управление .maFile и API ключами
- 👥 **Множественные аккаунты**: Поддержка нескольких Steam аккаунтов одновременно
- 🌐 **Прокси система**: Поддержка HTTP/SOCKS прокси для каждого аккаунта
- 🎨 **Улучшенный UI**: Эмодзи в меню и информативные сообщения

---

## 🚀 Быстрый старт

### 1️⃣ **Установка UV**

UV - современный и быстрый пакетный менеджер для Python:

```bash
# Установка UV (если не знаете, то рекомендую ознакомится подробнее: https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh  # Linux/macOS
# или
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"  # Windows
```

⚠️ **Важно**: После установки UV **обязательно перезапустите терминал**, чтобы переменные окружения обновились и команда `uv` стала доступна.

### 2️⃣ **Клонирование и установка**

```bash
git clone https://github.com/dr11m/pySDA
cd pySDA
uv sync --python 3.10.8
```

💡 **Проверка установки**: Если команда `uv` не найдена, убедитесь что вы перезапустили терминал после установки UV.

### 3️⃣ **Настройка конфигурации**

Скопируйте файл `config.example.yaml` и переименуйте в `config.yaml`:

```bash
cp config.example.yaml config.yaml
```

Затем заполните ваши данные в `config.yaml`:

```yaml
# Отладочные настройки
debug_console_output: true  # Вывод логов в консоль

# Минимальная задержка между запросами (в миллисекундах)
min_request_delay_ms: 1000

# Настройки аккаунтов
accounts:
  default:
    username: "ваш_steam_логин"
    password: "ваш_пароль"
    mafile_path: "accounts_info/ваш_логин.maFile"
    steam_id: "ваш_steam_id_64"
    api_key: ""  # можете оставить пустым (более не использется для работы)
```

### 4️⃣ **Добавление .maFile**

**Вариант 1 - Ручное добавление:**
1. Поместите ваш `.maFile` в папку `accounts_info/`
2. Переименуйте в формат `ваш_логин.maFile`

**Вариант 2 - Через бот:**
1. Запустите бот: `uv run python cli.py`
2. Перейдите в `⚙️ Настройки` → `📁 Добавить mafile`
3. Укажите путь к вашему .maFile

### 5️⃣ **Запуск**

```bash
uv run python cli.py
```

> **💡 Примечание о эмодзи**: Приложение использует эмодзи в интерфейсе для лучшего восприятия. Если на вашей системе эмодзи отображаются как квадратики или символы, рекомендуется:
> - **Windows**: Использовать Windows Terminal или PowerShell 7+
> - **macOS/Linux**: Обычно поддерживаются из коробки
> - **Серверы**: Эмодзи автоматически отключаются на серверах без поддержки Unicode

> **🔍 Отладка**: Если что-то не работает, подробные логи находятся в папке `logs/`. Также можно включить дебаг-режим в `config.yaml` установив `debug_console_output: true`

---

## 📖 Полный гид по меню

### 🏠 **Главное меню**

```
🤖 STEAM BOT CLI - ваш_логин
==================================================
1. 👤 Выбрать аккаунт
2. 🍪 Принудительно обновить cookies
3. 📋 Управление трейдами (получить + управлять)
4. 🏪 Подтвердить лоты на ТП
5. 🔑 Получить Guard код
6. ⚙️  Настройки
7. 🤖 Авто принятие
0. 🚪 Выход
```

#### **1. 👤 Выбрать аккаунт**
- **Назначение**: Выбор аккаунта для работы (для множественных аккаунтов)
- **Когда использовать**: При настройке нескольких аккаунтов
- **Результат**: Инициализация выбранного аккаунта

#### **2. 🍪 Принудительно обновить cookies**
- **Назначение**: Обновление Steam сессии при проблемах с доступом
- **Когда использовать**: При ошибках авторизации или истечении сессии
- **Результат**: Получение новых актуальных cookies для работы со Steam

#### **3. 📋 Управление трейдами**
Самый важный раздел для работы с трейдами:

**Что показывает:**
- 📥 **Входящие активные** - ожидают вашего принятия в веб-интерфейсе
- 📤 **Исходящие активные** - отправлены вами, ожидают ответа
- 📥 **Входящие (нужен Guard)** - уже приняты в вебе, требуют подтверждения через Steam Guard
- 📤 **Исходящие (нужен Guard)** - ваши трейды, требующие подтверждения

**Доступные действия:**
- 🎁 **Принять все подарки** - автоматически принимает в веб-интерфейсе трейды где вы ничего не отдаете
- 🔑 **Подтвердить все через Guard** - подтверждает через Steam Guard уже принятые трейды
- ✅ **Принять конкретный трейд** - выбор конкретного трейда для принятия в веб-интерфейсе
- 🔑 **Подтвердить конкретный трейд** - подтверждение через Steam Guard выбранного трейда

**Новые возможности:**
- ℹ️ **Информативные сообщения** - показывается когда нет активных трейдов
- 📝 **Улучшенное логирование** - все действия записываются в файл и выводятся в консоль

#### **4. 🏪 Подтвердить лоты на ТП**
- **Назначение**: Подтверждение всех ожидающих операций на торговой площадке Steam
- **Когда использовать**: После покупки/продажи предметов на маркете
- **Результат**: Автоматическое подтверждение всех маркет-операций
- **Новое**: Показывает сообщение когда нет market ордеров для подтверждения

#### **5. 🔑 Получить Guard код**
- **Назначение**: Генерация кода Steam Guard для ручного использования
- **Когда использовать**: Для подтверждения действий вне бота
- **Результат**: 5-значный код, действующий 30 секунд

#### **6. ⚙️ Настройки**
- **📁 Добавить mafile** - помощник для добавления новых .maFile
- **🔑 Получение API ключа** - автоматическое создание Steam API ключа

#### **7. 🤖 Авто принятие**
Переход к настройкам автоматизации (подробнее в следующем разделе)

---

## 🤖 Автоматизация - главная фича

> **Это основная причина создания бота** - автоматическая обработка трейдов без вашего участия. Бот принимает трейды в веб-интерфейсе Steam, а затем автоматически подтверждает их через Steam Guard.

### ⚙️ **Настройки автоматизации**

При выборе `🤖 Авто принятие` → `⚙️ Настройки автоматизации` вы можете настроить:

**🕐 Временные интервалы:**
- Интервал проверки трейдов (рекомендуется 60-300 секунд)

**🎁 Автоматическое принятие:**
- Принимать подарки в веб-интерфейсе (когда вам дают предметы бесплатно)

**🔑 Автоподтверждение:**
- Подтверждать через Steam Guard трейды, уже принятые в веб-интерфейсе или отправленные трейды
- Подтверждать маркет-операции


**📊 Статистика и логи:**
- Ведение подробных логов всех операций
- Счетчики принятых/подтвержденных трейдов
- **Новое**: Улучшенное логирование с `print_and_log` утилитой

### ▶️ **Запуск автоматизации**

После настройки выберите `▶️ Включить авто принятие`:

**Что происходит в автоматическом режиме:**
1. **Проверка сессии** - каждые N секунд проверяется валидность cookies
2. **Поиск новых трейдов** - регулярная проверка активных трейдов
3. **Анализ трейдов** - определение типа (подарок/обмен/отдача)
4. **Принятие в веб-интерфейсе** - автоматическое принятие подарков
5. **Подтверждение через Steam Guard** - автоматическое подтверждение уже принятых трейдов (принятых или отправленных вами)
6. **Логирование** - запись всех действий в файлы логов

**Типы автоматически обрабатываемых трейдов:**
- 🎁 **Подарки** - трейды где вы получаете предметы бесплатно (принимаются в веб-интерфейсе)
- ✅ **Разрешенные обмены** - согласно вашим настройкам (принимаются в веб-интерфейсе)
- 🔑 **Ожидающие подтверждения** - автоматическое подтверждение через Steam Guard уже принятых трейдов

**Новые возможности:**
- ℹ️ **Информативные сообщения** - показывается когда нет трейдов для обработки
- 📝 **Улучшенное логирование** - все действия записываются в файл и выводятся в консоль
- 🔧 **Множественные аккаунты** - поддержка нескольких аккаунтов одновременно

**Безопасность:**
- Бот НЕ принимает трейды где вы что-то отдаете (кроме настроенных исключений)
- Все действия логируются для контроля
- Возможность остановки в любой момент

### 📊 **Мониторинг работы**

Во время работы автоматизации вы увидите:
- Статус текущих операций
- Количество обработанных трейдов
- Время последней проверки
- Ошибки и предупреждения
- Возможность остановки процесса
- **Новое**: Информативные сообщения о состоянии системы

---

## 🔧 Структура проекта

```
pySDA/
├── 🚀 cli.py                    # Точка входа приложения
├── ⚙️ config.yaml               # Конфигурация аккаунта
├── 📁 accounts_info/            # Данные аккаунтов
│   ├── username.maFile          # Steam Guard файл
│   ├── username_cookies.json    # Cookies сессии
│   └── auto_settings.json       # Настройки автоматизации
├── 📂 src/                      # Исходный код
│   ├── 🖥️ cli_interface.py      # Основной CLI интерфейс
│   ├── 🍪 cookie_manager.py     # Управление cookies
│   ├── 🤝 trade_confirmation_manager.py # Управление трейдами
│   ├── 📊 models.py             # Модели данных
│   ├── 🔧 cli/                  # CLI модули
│   ├── 🔌 interfaces/           # Интерфейсы хранения
│   ├── 🏗️ implementations/     # Реализации (новое!)
│   │   ├── cookie_storage/      # Хранение cookies
│   │   ├── proxy_storage/       # Управление прокси
│   │   └── notifications/       # Система уведомлений
│   └── 🔥 steampy/              # Steam API библиотека
├── 🧪 tests/                    # Новые тесты
│   ├── test_error_tracking.py   # Тестирование системы ошибок
│   ├── test_proxy_connection.py # Тестирование прокси
│   └── demo_error_tracking.py   # Демо системы ошибок
├── 🔥 tests_steampy/            # Тесты Steam API
│   ├── test_client.py           # Тесты клиента
│   ├── test_guard.py            # Тесты Guard
│   ├── test_market.py           # Тесты маркета
│   └── test_utils.py            # Тесты утилит
└── 📋 pyproject.toml            # Конфигурация проекта
```

---

## 🆕 Новые возможности v2.0.0

### 🎨 **Улучшенный пользовательский интерфейс**
- ✨ **Эмодзи в меню**: Все пункты меню теперь содержат эмодзи для лучшего восприятия
- 📝 **Улучшенное логирование**: Новая утилита `print_and_log` для одновременного вывода в консоль и файл
- ⚙️ **Настройка вывода**: Опция `debug_console_output` в конфигурации для контроля вывода логов

### 🎯 **Информативные сообщения**
- ℹ️ **Сообщения о трейдах**: Показывается когда нет активных трейдов для управления
- 🏪 **Сообщения о маркете**: Показывается когда нет market ордеров для подтверждения
- 📊 **Улучшенная обратная связь**: Более информативные сообщения о состоянии системы

### 🔧 **Технические улучшения**
- 🏗️ **Реструктуризация проекта**: Разделение на отдельные папки для реализаций
- 🔓 **Улучшенная поддержка множественных аккаунтов**: Удален singleton pattern из CookieManager
- 🔑 **Улучшенная работа с API ключами**: Приоритет API ключей из конфигурации
- 🌍 **Исправление timezone**: Корректная обработка временных зон в cookies

### 🌐 **Прокси система**
- 🌐 **Поддержка прокси**: Настройка прокси для каждого аккаунта отдельно
- 🔄 **Гибкая архитектура**: Возможность использования различных провайдеров прокси
- ⚡ **Улучшенная производительность**: Оптимизированная работа с множественными аккаунтами

---

## 📋 TODO - Планы развития

### 🎯 **Ближайшие цели**

#### 👥 **Множество аккаунтов** ✅
- [x] Поддержка нескольких Steam аккаунтов одновременно
- [x] Переключение между аккаунтами в интерфейсе
- [x] Отдельные настройки автоматизации для каждого аккаунта

#### 🌐 **Прокси система** ✅
- [x] Поддержка HTTP/SOCKS прокси
- [x] Привязка отдельного прокси к каждому аккаунту
- [x] Автоматическое переключение при блокировке
- [x] Проверка работоспособности прокси
- [ ] Внести настройку проксей в основное меню настроек

#### ⚙️ **Индивидуальные настройки** ✅
- [x] Персональные правила автоматизации для каждого аккаунта

### 🛠️ **Техническая часть**

#### 💾 **Интерфейс хранения cookies** ✅
- [x] Улучшить логирование (обычное + ошибки), внедрить везде loguru, не сломав print для работы через cli.py
- [x] Абстрактный интерфейс для различных storage систем
- [x] Реализация SQLite storage для интеграции
- [x] Пример интеграции с внешними проектами
- [ ] Шифрование cookies в базе данных

```python
# Пример будущего SQLite storage
class SQLiteCookieStorage(CookieStorageInterface):
    """Хранение cookies в SQLite для интеграции с другими проектами"""
    
    def save_cookies(self, username: str, cookies: dict) -> bool:
        # Сохранение зашифрованных cookies в БД
        pass
    
    def load_cookies(self, username: str) -> dict:
        # Загрузка и расшифровка cookies из БД
        pass
```

#### 📡 **Message Queue система**
- [ ] Интеграция с Redis/RabbitMQ для внешних запросов
- [ ] Индивидуальные настройки для этой интеграции для каждого аккаунта

---

## 🙏 Благодарности

Проект использует функционал из [bukson/steampy](https://github.com/bukson/steampy) (MIT License) для работы с Steam API.

---
---

## 🧪 Тестирование

### 🚀 **Запуск тестов**

Проект включает набор unit-тестов для проверки основного функционала:

```bash
# Запуск всех тестов (включая новые тесты)
uv run python -m pytest tests/ tests_steampy/

# Запуск только новых тестов
uv run python -m pytest tests/

# Запуск только тестов steampy
uv run python -m pytest tests_steampy/

# Запуск конкретного теста
uv run python -m pytest tests_steampy/test_client.py

# Запуск с детальным выводом
uv run python -m pytest tests/ tests_steampy/ -v

# Запуск с покрытием кода
uv run python -m pytest tests/ tests_steampy/ --cov=src
```

### 📋 **Доступные тесты**

#### 🆕 **Новые тесты** (`tests/`)
- **`test_error_tracking.py`** - Тестирование системы отслеживания ошибок
- **`test_proxy_connection.py`** - Тестирование подключения к прокси
- **`demo_error_tracking.py`** - Демонстрация системы отслеживания ошибок

#### 🔥 **Тесты Steam API** (`tests_steampy/`)
- **`test_client.py`** - Тестирование основного Steam клиента
- **`test_guard.py`** - Тестирование Steam Guard функционала
- **`test_market.py`** - Тестирование работы с торговой площадкой
- **`test_utils.py`** - Тестирование вспомогательных функций

### 🔧 **Запуск отдельных тест-модулей**

```bash
# Тестирование новых функций
uv run python -m pytest tests/test_error_tracking.py -v
uv run python -m pytest tests/test_proxy_connection.py -v

# Тестирование Steam API
uv run python -m pytest tests_steampy/test_guard.py -v
uv run python -m pytest tests_steampy/test_market.py -v
uv run python -m pytest tests_steampy/test_utils.py -v
```

### 📊 **Покрытие кода**

Для проверки покрытия кода тестами:

```bash
# Установка coverage (если нужно)
uv add --dev pytest-cov

# Запуск с отчетом покрытия
uv run python -m pytest tests/ tests_steampy/ --cov=src --cov-report=html

# Просмотр отчета (создается папка htmlcov/)
# Откройте htmlcov/index.html в браузере
```

### ⚠️ **Важные замечания**

- Тесты работают с mock-данными и не требуют реального Steam аккаунта
- Перед коммитом рекомендуется запускать все тесты
- При добавлении нового функционала желательно покрывать его тестами

---

<div align="center">

**🎯 Сделано с ❤️ для автоматизации Steam трейдинга**

[🐛 Сообщить об ошибке](../../issues) • [💡 Предложить улучшение](../../issues) • [📖 Документация](../../wiki)

</div> 