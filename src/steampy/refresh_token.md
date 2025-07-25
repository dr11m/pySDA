# Steam Session Management - Python Implementation

_try_refresh_session() метод предоставляет Python реализацию обновления Steam сессий, основанную на [node-steam-session](https://github.com/DoctorMcKay/node-steam-session).

## Обзор

Реализация воспроизводит ключевую функциональность оригинальной библиотеки для получения веб-куки Steam через refresh-токены, используя минималистичный подход с оптимизированным количеством HTTP-запросов.

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
- **Оптимизация**: Используем только первый transfer запрос для получения `steamLoginSecure`

## Использование

```python
from steam_session import get_steam_login_cookies, format_cookies_for_domain

# Получение куки из refresh-токена
cookies = get_steam_login_cookies(refresh_token)
print(f"steamLoginSecure: {cookies['steamLoginSecure']}")
print(f"sessionid: {cookies['sessionid']}")

# Форматирование для конкретного домена
formatted = format_cookies_for_domain(cookies, 'steamcommunity.com')
```

## Ключевые отличия от оригинала

1. **Упрощенный подход**: Один transfer запрос вместо обработки всех
2. **Фокус на основном**: Только `steamLoginSecure` и `sessionid`
3. **Минимальные зависимости**: Только `requests` и стандартные библиотеки

## Задача: Автоматическое обновление Refresh Token

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

### Ссылки на оригинальную документацию

- [LoginSession.renewRefreshToken()](https://github.com/DoctorMcKay/node-steam-session#renewrefreshtokenforcerenew) - основной метод обновления
- [События refreshTokenUpdated](https://github.com/DoctorMcKay/node-steam-session#refreshtokenupdated) - событие при обновлении токена
- [Управление токенами](https://github.com/DoctorMcKay/node-steam-session#token-management) - общая документация по токенам

## Лицензия

Данная реализация создана на основе публичного API Steam и документации [node-steam-session](https://github.com/DoctorMcKay/node-steam-session).