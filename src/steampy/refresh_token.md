# Steam Session Management - Python Implementation

Метод `_try_refresh_session()` предоставляет Python реализацию обновления Steam сессий, основанную на [node-steam-session](https://github.com/DoctorMcKay/node-steam-session).

## Обзор

Реализация воспроизводит ключевую функциональность оригинальной библиотеки для получения веб-куки Steam через refresh-токены. **Критическое исправление**: теперь корректно обрабатывает domain-specific токены для каждого домена Steam вместо использования одного токена для всех доменов.

## Основанные методы

Наша реализация базируется на следующих методах из [node-steam-session](https://github.com/DoctorMcKay/node-steam-session):

### 1. LoginSession.getWebCookies()
- **Оригинал**: [`src/LoginSession.js#getWebCookies`](https://github.com/DoctorMcKay/node-steam-session/blob/master/src/LoginSession.js)
- **Платформа**: `EAuthTokenPlatformType.WebBrowser`
- **Описание**: Получает веб-куки для всех доменов Steam после JWT-аутентификации

### 2. JWT Finalize Login Process
- **Эндпоинт**: `https://login.steampowered.com/jwt/finalizelogin`
- **Назначение**: Финализация JWT-аутентификации и получение transfer_info для куки

### 3. Transfer Info Processing
- **Оригинал**: [`src/LoginSession.js#_doTransferLogin`](https://github.com/DoctorMcKay/node-steam-session/blob/master/src/LoginSession.js)
- **Исправление**: Теперь выполняем **ВСЕ** transfer запросы для получения корректных токенов для каждого домена

## Ключевая проблема и её решение

### Проблема (версия 2.2.0)
```python
# НЕПРАВИЛЬНО: Один токен для всех доменов
steam_login_secure = get_first_token()  # Только store.steampowered.com
# Результат: {"aud": ["web:store"]} для steamcommunity.com - ОШИБКА!
```

### Решение (версия 2.2.1)
```python
# ПРАВИЛЬНО: Domain-specific токены
domain_tokens = {
    'steamcommunity.com': token_with_community_aud,    # {"aud": ["web:community"]}
    'store.steampowered.com': token_with_store_aud,    # {"aud": ["web:store"]}
    'help.steampowered.com': token_with_help_aud       # {"aud": ["web:help"]}
}
```

## Использование

```python
# Создание клиента с автоматическим обновлением сессии
client = SteamClient(username="your_username")

# Метод автоматически попробует обновить сессию через refresh токен
if client._try_refresh_session():
    print("✅ Сессия успешно обновлена через refresh токен")
    # Теперь все domain-specific токены корректны
else:
    print("❌ Требуется полная авторизация")
    client.login(username, password, two_factor_code)
```

## Архитектура метода

### 1. get_steam_login_cookies()
```python
def get_steam_login_cookies(self, refresh_token: str) -> dict:
    """
    Получает domain-specific токены для каждого Steam домена
    """
    # Шаг 1: Получение transfer_info
    result = self._session.post('/jwt/finalizelogin', ...)
    transfer_info = result['transfer_info']
    
    # Шаг 2: Выполнение ВСЕХ transfer запросов
    domain_tokens = {}
    for transfer in transfer_info:
        domain = extract_domain(transfer['url'])
        token = execute_transfer_request(transfer)
        domain_tokens[domain] = token  # Сохраняем по домену
    
    return {
        'domain_tokens': domain_tokens,
        'sessionid': generated_session_id
    }
```

### 2. _try_refresh_session()
```python
def _try_refresh_session(self) -> bool:
    """
    Обновляет сессию с корректными токенами для каждого домена
    """
    # Получаем domain-specific токены
    cookies_data = self.get_steam_login_cookies(self.refresh_token)
    domain_tokens = cookies_data['domain_tokens']
    
    # Обновляем существующие cookies правильными токенами
    for cookie in self._session.cookies:
        if cookie.name == 'steamLoginSecure':
            domain = cookie.domain
            if domain in domain_tokens:
                cookie.value = domain_tokens[domain]  # Правильный токен для домена
    
    # Проверяем валидность обновленной сессии
    return self.check_session_static(self.username, self._session)
```

## Ключевые отличия от оригинала

1. **Точная реализация transfer_info**: Выполнение всех transfer запросов как в оригинале
2. **Domain-specific токены**: Корректное сопоставление токенов с соответствующими доменами
3. **Детальное логирование**: Сохранение всех отладочных сообщений и проверок
4. **Валидация сессии**: Токены проходят проверку для всех Steam доменов

## Поддерживаемые домены

- `steamcommunity.com` - основной домен сообщества Steam
- `store.steampowered.com` - магазин Steam
- `help.steampowered.com` - служба поддержки
- `login.steampowered.com` - сервис аутентификации

## Диагностика проблем

### Проверка корректности токенов
```python
import base64, json

def decode_steam_token(token):
    """Декодирует JWT токен для проверки audience"""
    parts = token.split('.')
    payload = json.loads(base64.b64decode(parts[1] + '=='))
    return payload['aud']  # Показывает для какого домена токен

# Пример использования
for domain, token in domain_tokens.items():
    audience = decode_steam_token(token)
    print(f"Домен: {domain}, Audience: {audience}")
```

### Типичные ошибки
- `{"success":false,"needauth":true}` - неправильный токен для домена
- `ExpiredToken` - refresh токен истек, нужна полная авторизация
- `InvalidAudience` - токен с `web:store` используется для `steamcommunity.com`

## Интеграция с основной функциональностью

```python
# Автоматическое обновление при создании клиента
client = SteamClient(username="account_name")
# Клиент автоматически попробует обновить сессию через refresh токен

# Ручная проверка и обновление
if not client.check_session_static(username, session):
    if client._try_refresh_session():
        print("✅ Сессия обновлена через refresh токен")
    else:
        print("❌ Требуется полная авторизация")
        client.login(username, password, two_factor_code)
```

## Автоматическое обновление Refresh Token

### Проблема
Refresh-токены в Steam имеют ограниченный срок жизни (~90 дней) и требуют периодического обновления для поддержания сессии без повторного ввода логина и пароля.

### Как это работает в оригинале

В [node-steam-session](https://github.com/DoctorMcKay/node-steam-session) за обновление токенов отвечает метод [`renewRefreshToken()`](https://github.com/DoctorMcKay/node-steam-session/blob/master/src/LoginSession.js):

```javascript
// Пример из node-steam-session
let renewed = await session.renewRefreshToken();
if (renewed) {
    console.log('Refresh token обновлен:', session.refreshToken);
    // Событие refreshTokenUpdated также генерируется
}
```

**Логика оригинала**:
1. Отправляет запрос к `/IAuthenticationService/GenerateAccessTokenForApp/v1`
2. Если до истечения токена осталось менее 7 дней, сервер возвращает новый `refresh_token`
3. Библиотека автоматически заменяет старый токен и генерирует событие `refreshTokenUpdated`

### Python реализация (TODO)

```python
import requests
import json
import time
from datetime import datetime, timedelta
import threading

class SteamTokenManager:
    def __init__(self, refresh_token: str, on_token_updated=None):
        self.refresh_token = refresh_token
        self.on_token_updated = on_token_updated  # Callback при обновлении
        self.last_renewal_check = None
        self._stop_monitoring = False
        
    def renew_refresh_token(self) -> bool:
        """
        Попытка обновления refresh token.
        Возвращает True, если токен был обновлен.
        """
        session = requests.Session()
        
        try:
            resp = session.post(
                "https://login.steampowered.com/IAuthenticationService/GenerateAccessTokenForApp/v1",
                data={"refresh_token": self.refresh_token}
            )
            
            data = resp.json().get("response", {})
            
            if "refresh_token" in data:
                old_token = self.refresh_token
                self.refresh_token = data["refresh_token"]
                
                # Вызываем callback, если задан
                if self.on_token_updated:
                    self.on_token_updated(old_token, self.refresh_token)
                
                print(f"Refresh token обновлен: {self.refresh_token[:20]}...")
                return True
                
            return False  # Обновление пока не требуется
            
        except Exception as e:
            print(f"Ошибка при обновлении токена: {e}")
            return False
    
    def start_monitoring(self, check_interval_hours: int = 24):
        """
        Запускает фоновый мониторинг для автоматического обновления токена.
        """
        def monitor():
            while not self._stop_monitoring:
                try:
                    renewed = self.renew_refresh_token()
                    if renewed:
                        print("Токен автоматически обновлен")
                    else:
                        print("Обновление токена пока не требуется")
                        
                except Exception as e:
                    print(f"Ошибка в мониторинге токена: {e}")
                
                # Ждем до следующей проверки
                time.sleep(check_interval_hours * 3600)
        
        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()
        print(f"Запущен мониторинг токена (проверка каждые {check_interval_hours}ч)")
    
    def stop_monitoring(self):
        """Останавливает фоновый мониторинг."""
        self._stop_monitoring = True

# Пример использования
def on_token_update(old_token, new_token):
    """Callback для сохранения нового токена"""
    print(f"Сохраняем новый токен в базу данных...")
    # Здесь код для сохранения нового токена в файл/БД
    save_refresh_token_to_storage(new_token)

# Инициализация менеджера токенов
token_manager = SteamTokenManager(
    refresh_token="your_refresh_token_here",
    on_token_updated=on_token_update
)

# Запуск автоматического мониторинга
token_manager.start_monitoring(check_interval_hours=12)  # Проверка каждые 12 часов
```

### Рекомендации по реализации

1. **Частота проверки**: Проверять обновление токена каждые 12-24 часа
2. **Обработка ошибок**: При истечении токена требуется полная повторная аутентификация
3. **Сохранение**: Новый токен должен немедленно сохраняться в постоянное хранилище
4. **Логирование**: Отслеживать события обновления для диагностики

### Интеграция с основной функциональностью

```python
# Интеграция с получением куки
def get_steam_cookies_with_auto_renewal(token_manager: SteamTokenManager):
    try:
        # Попробуем получить куки с текущим токеном
        return get_steam_login_cookies(token_manager.refresh_token)
    except Exception as e:
        # Если токен недействителен, попробуем обновить
        if "expired" in str(e).lower():
            print("Токен истек, пытаемся обновить...")
            if token_manager.renew_refresh_token():
                return get_steam_login_cookies(token_manager.refresh_token)
        raise e
```

## Ссылки на оригинальную документацию

- [LoginSession.getWebCookies()](https://github.com/DoctorMcKay/node-steam-session#getwebcookies) - основной метод получения куки
- [LoginSession.renewRefreshToken()](https://github.com/DoctorMcKay/node-steam-session#renewrefreshtokenforcerenew) - метод обновления токенов
- [События refreshTokenUpdated](https://github.com/DoctorMcKay/node-steam-session#refreshtokenupdated) - событие при обновлении токена
- [Transfer Info Processing](https://github.com/DoctorMcKay/node-steam-session/blob/master/src/LoginSession.js) - обработка transfer_info
- [Управление токенами](https://github.com/DoctorMcKay/node-steam-session#token-management) - общая документация по токенам

## Лицензия

Данная реализация создана на основе публичного API Steam и документации [node-steam-session](https://github.com/DoctorMcKay/node-steam-session).