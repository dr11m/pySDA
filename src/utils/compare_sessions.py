import requests
from loguru import logger


def compare_sessions_and_log_diff(old_session: requests.Session, new_session: requests.Session) -> None:
    try:
        changes = compare_session_cookies(old_session, new_session)
        log_cookie_changes(changes)
        print_cookie_summary(changes)
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка при сравнении сессий: {e}")
        return None


def compare_session_cookies(old_session: requests.Session, new_session: requests.Session) -> dict:
    """
    Сравнивает cookies между старой и новой сессией для каждого домена
    
    Args:
        old_session: Старая сессия
        new_session: Новая сессия
        
    Returns:
        Словарь с изменениями по доменам:
        {
            'domain.com': {
                'changed': {'cookie_name': {'old': 'old_value', 'new': 'new_value'}},
                'added': {'new_cookie': 'new_value'},
                'removed': {'removed_cookie': 'old_value'},
                'unchanged': {'same_cookie': 'same_value'}
            }
        }
    """
    result = {}
    
    # Получаем все домены из обеих сессий
    old_domains = set()
    new_domains = set()
    
    for cookie in old_session.cookies:
        old_domains.add(cookie.domain)
    
    for cookie in new_session.cookies:
        new_domains.add(cookie.domain)
    
    all_domains = old_domains.union(new_domains)
    
    # Анализируем каждый домен
    for domain in all_domains:
        domain_result = {
            'changed': {},
            'added': {},
            'removed': {},
            'unchanged': {}
        }
        
        # Получаем cookies для конкретного домена
        old_domain_cookies = {}
        new_domain_cookies = {}
        
        for cookie in old_session.cookies:
            if cookie.domain == domain:
                old_domain_cookies[cookie.name] = cookie.value
        
        for cookie in new_session.cookies:
            if cookie.domain == domain:
                new_domain_cookies[cookie.name] = cookie.value
        
        # Находим все уникальные имена cookies
        all_cookie_names = set(old_domain_cookies.keys()).union(set(new_domain_cookies.keys()))
        
        for cookie_name in all_cookie_names:
            old_value = old_domain_cookies.get(cookie_name)
            new_value = new_domain_cookies.get(cookie_name)
            
            if old_value is None and new_value is not None:
                # Новый cookie
                domain_result['added'][cookie_name] = new_value
                
            elif old_value is not None and new_value is None:
                # Удаленный cookie
                domain_result['removed'][cookie_name] = old_value
                
            elif old_value != new_value:
                # Измененный cookie
                domain_result['changed'][cookie_name] = {
                    'old': old_value,
                    'new': new_value
                }
                
            else:
                # Неизмененный cookie
                domain_result['unchanged'][cookie_name] = old_value
        
        # Добавляем результат только если есть cookies для этого домена
        if any([domain_result['changed'], domain_result['added'], 
               domain_result['removed'], domain_result['unchanged']]):
            result[domain] = domain_result
    
    return result


def log_cookie_changes(changes: dict, username: str = None):
    """
    Логирует изменения cookies в удобном формате
    
    Args:
        changes: Результат от compare_session_cookies
        username: Имя пользователя для логов
    """
    user_prefix = f"[{username}] " if username else ""
    
    logger.info(f"{user_prefix}🔍 Сравнение cookies между сессиями:")
    
    for domain, domain_changes in changes.items():
        logger.info(f"{user_prefix}📍 Домен: {domain}")
        
        # Измененные cookies
        if domain_changes['changed']:
            logger.info(f"{user_prefix}  🔄 Изменены:")
            for name, values in domain_changes['changed'].items():
                old_short = values['old'][:20] + '...' if len(values['old']) > 20 else values['old']
                new_short = values['new'][:20] + '...' if len(values['new']) > 20 else values['new']
                logger.info(f"{user_prefix}    {name}: {old_short} → {new_short}")
        
        # Добавленные cookies
        if domain_changes['added']:
            logger.info(f"{user_prefix}  ➕ Добавлены:")
            for name, value in domain_changes['added'].items():
                value_short = value[:20] + '...' if len(value) > 20 else value
                logger.info(f"{user_prefix}    {name}: {value_short}")
        
        # Удаленные cookies
        if domain_changes['removed']:
            logger.info(f"{user_prefix}  ➖ Удалены:")
            for name, value in domain_changes['removed'].items():
                value_short = value[:20] + '...' if len(value) > 20 else value
                logger.info(f"{user_prefix}    {name}: {value_short}")
        
        # Неизмененные cookies (опционально, для детального анализа)
        if domain_changes['unchanged']:
            logger.debug(f"{user_prefix}  ✅ Без изменений: {len(domain_changes['unchanged'])} cookies")

def print_cookie_summary(changes: dict, username: str = None):
    """
    Выводит краткую сводку изменений
    
    Args:
        changes: Результат от compare_session_cookies
        username: Имя пользователя для логов
    """
    user_prefix = f"[{username}] " if username else ""
    
    total_changed = sum(len(d['changed']) for d in changes.values())
    total_added = sum(len(d['added']) for d in changes.values())
    total_removed = sum(len(d['removed']) for d in changes.values())
    total_domains = len(changes)
    
    logger.info(f"{user_prefix}📊 Сводка изменений cookies:")
    logger.info(f"{user_prefix}  Доменов: {total_domains}")
    logger.info(f"{user_prefix}  Изменено: {total_changed} cookies")
    logger.info(f"{user_prefix}  Добавлено: {total_added} cookies")
    logger.info(f"{user_prefix}  Удалено: {total_removed} cookies")



if __name__ == "__main__":
    # Создаем тестовые сессии с cookies
    old_session = requests.Session()
    new_session = requests.Session()
    
    # Добавляем тестовые cookies к старой сессии
    old_session.cookies.set('sessionid', 'old_session_123', domain='steamcommunity.com')
    old_session.cookies.set('steamLoginSecure', 'old_steam_login_456', domain='steamcommunity.com')
    old_session.cookies.set('browserid', 'old_browser_789', domain='steamcommunity.com')
    old_session.cookies.set('steamCountry', 'RU', domain='steamcommunity.com')
    
    # Добавляем тестовые cookies к новой сессии (с изменениями)
    new_session.cookies.set('sessionid', 'new_session_456', domain='steamcommunity.com')  # изменен
    new_session.cookies.set('steamLoginSecure', 'new_steam_login_789', domain='steamcommunity.com')  # изменен
    new_session.cookies.set('browserid', 'old_browser_789', domain='steamcommunity.com')  # без изменений
    new_session.cookies.set('steamCountry', 'RU', domain='steamcommunity.com')  # без изменений
    new_session.cookies.set('newCookie', 'new_value_123', domain='steamcommunity.com')  # добавлен
    
    # Добавляем cookies для другого домена
    old_session.cookies.set('store_sessionid', 'old_store_123', domain='store.steampowered.com')
    new_session.cookies.set('store_sessionid', 'new_store_456', domain='store.steampowered.com')
    new_session.cookies.set('store_new_cookie', 'store_new_value', domain='store.steampowered.com')
    
    print("🔍 Тестирование сравнения сессий с cookies...")
    compare_sessions_and_log_diff(old_session, new_session)