import requests
import json
import secrets
import base64

STEAM_LOGIN_BASE = 'https://login.steampowered.com'
STEAM_COMMUNITY = 'https://steamcommunity.com'

def extract_steam_id(refresh_token: str) -> str:
    """Извлекает SteamID из JWT токена"""
    parts = refresh_token.split('.')
    payload = json.loads(base64.b64decode(parts[1] + '=='))
    return payload['sub']

def get_steam_login_cookies(refresh_token: str) -> dict:
    """
    Получает только steamLoginSecure и sessionid - минимум для работы со Steam
    """
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    session_id = secrets.token_hex(12)
    
    # Шаг 1: finalizelogin для получения transfer_info
    resp = session.post(
        f'{STEAM_LOGIN_BASE}/jwt/finalizelogin',
        data={
            'nonce': refresh_token,
            'sessionid': session_id,
            'redir': f'{STEAM_COMMUNITY}/login/home/?goto='
        },
        headers={
            'Origin': STEAM_COMMUNITY,
            'Referer': f'{STEAM_COMMUNITY}/',
        }
    )
    
    result = resp.json()
    if 'error' in result or 'transfer_info' not in result:
        raise Exception(f"Login failed: {result}")
    
    # Шаг 2: Один transfer запрос для получения steamLoginSecure
    steam_id = extract_steam_id(refresh_token)
    transfer = result['transfer_info'][0]  # Берем первый
    
    tr_resp = session.post(
        transfer['url'],
        data={'steamID': steam_id, **transfer['params']}
    )
    
    # Шаг 3: Извлекаем steamLoginSecure из Set-Cookie
    steam_login_secure = None
    try:
        cookies = tr_resp.raw._original_response.msg.get_all('Set-Cookie') or []
        for cookie in cookies:
            if 'steamLoginSecure=' in cookie:
                steam_login_secure = cookie.split('steamLoginSecure=')[1].split(';')[0]
                break
    except:
        raise Exception("Не удалось получить steamLoginSecure")
    
    if not steam_login_secure:
        raise Exception("steamLoginSecure не найден в ответе")
    
    return {
        'steamLoginSecure': steam_login_secure,
        'sessionid': session_id
    }

def format_cookies_for_domain(cookies_dict: dict, domain: str) -> list[str]:
    """Форматирует куки для конкретного домена"""
    return [
        f"steamLoginSecure={cookies_dict['steamLoginSecure']}; Path=/; Secure; HttpOnly; Domain={domain}",
        f"sessionid={cookies_dict['sessionid']}; Path=/; Secure; Domain={domain}"
    ]

# Пример использования
if __name__ == '__main__':
    refresh_token = "eyAidHlwIjogIkpXVCIsICJhbGciOiAiRWREU0EiIH0.eyAiaXNzIjogInN0ZWFtIiwgInN1YiI6ICI3NjU2MTE5OTU0MjcxMjczNCIsICJhdWQiOiBbICJ3ZWIiLCAicmVuZXciLCAiZGVyaXZlIiBdLCAiZXhwIjogMTc3MTY1NTAyNiwgIm5iZiI6IDE3NDQ3NjE2NjAsICJpYXQiOiAxNzUzNDAxNjYwLCAianRpIjogIjAwMEZfMjZBQzRBQ0JfMTcxRDQiLCAib2F0IjogMTc1MzQwMTY2MCwgInBlciI6IDEsICJpcF9zdWJqZWN0IjogIjIwOS45OS4xMjkuMjU0IiwgImlwX2NvbmZpcm1lciI6ICIyMDkuOTkuMTI5LjI1NCIgfQ.DuP4TosLAHdJH37LL9e-qw8t0c0HUIaub43mlj189Q28mI92pWgVASkDPhFa22Jxcq7f4hHgpi-9lDqiqR2AAw"

    
    try:
        # Получаем только нужные значения
        cookies = get_steam_login_cookies(refresh_token)
        
        print("Получены куки:")
        print(f"steamLoginSecure: {cookies['steamLoginSecure'][:20]}...")
        print(f"sessionid: {cookies['sessionid']}")
        
        
    except Exception as e:
        print(f"Ошибка: {e}")

