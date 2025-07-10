from typing import Dict, Any
import requests


def extract_cookies_for_domain(cookies_dict: Dict[str, Any], domain: str) -> Dict[str, str]:
    """
    Собирает куки для указанного домена (и поддоменов, если есть) в виде dict для передачи в requests.get
    """
    result = {}
    for dom, paths in cookies_dict.items():
        # Проверяем точное совпадение или поддомен
        if dom == domain or dom.endswith('.' + domain) or (domain.startswith('.') and dom == domain[1:]):
            for path_cookies in paths.values():
                for name, attrs in path_cookies.items():
                    result[name] = attrs['value']
    return result

def session_to_dict(session: requests.Session) -> Dict[str, Any]:
    """
    Преобразует объект Session в словарь, сохраняя все атрибуты cookies.
    """
    cookies_dict = {}
    for cookie in session.cookies:
        domain = cookie.domain
        path = cookie.path
        if domain not in cookies_dict:
            cookies_dict[domain] = {}
        if path not in cookies_dict[domain]:
            cookies_dict[domain][path] = {}
        cookies_dict[domain][path][cookie.name] = {
            'version': cookie.version,
            'name': cookie.name,
            'value': cookie.value,
            'port': cookie.port,
            'port_specified': cookie.port_specified,
            'domain': cookie.domain,
            'domain_specified': cookie.domain_specified,
            'domain_initial_dot': cookie.domain_initial_dot,
            'path': cookie.path,
            'path_specified': cookie.path_specified,
            'secure': cookie.secure,
            'expires': cookie.expires,
            'discard': cookie.discard,
            'comment': cookie.comment,
            'comment_url': cookie.comment_url,
            'rfc2109': cookie.rfc2109,
            '_rest': cookie._rest
        }
    return {
        'cookies': cookies_dict,
        'headers': dict(session.headers)
    }