"""Playwright-based browser launcher for Steam accounts."""

from typing import Any, Dict, List

from loguru import logger

from browser_launcher.cookie_reader import load_playwright_cookies
from browser_launcher.models import AccountSettings, LaunchOptions
from browser_launcher.profile_store import ProfileStore
from browser_launcher.proxy_format import format_proxy_label
from browser_launcher.proxy_utils import to_playwright_proxy
from browser_launcher.session_check import context_has_steam_session
from browser_launcher.session_lock import SessionLock

BROWSER_TIMEOUT_MS = 90_000


class BrowserLauncher:
    """Launch isolated Chromium sessions for configured accounts."""

    def __init__(self, profile_store: ProfileStore | None = None):
        self.profile_store = profile_store or ProfileStore()

    def open_account(
        self,
        account: AccountSettings,
        options: LaunchOptions,
    ) -> None:
        """Open a persistent Chromium window for the given account."""
        from playwright.sync_api import sync_playwright

        proxy_mapping = options.proxy_mapping
        playwright_proxy = to_playwright_proxy(
            proxy_mapping,
            bypass_cs_deals=options.bypass_cs_deals,
        )
        proxy_label = format_proxy_label(proxy_mapping)
        profile_dir = self.profile_store.get_profile_dir(account.account_name)
        session_lock = SessionLock(profile_dir, account.account_name)

        if not session_lock.acquire():
            logger.error(
                "Browser for account '{}' is already open",
                account.account_name,
            )
            return

        cookies = load_playwright_cookies(
            account.cookie_storage_config,
            account.username,
        )

        logger.info("Opening browser for account '{}'", account.account_name)
        logger.info("Profile directory: {}", profile_dir)
        print(f"Proxy IP: {proxy_label}")
        if playwright_proxy:
            logger.info("Proxy endpoint: {}", proxy_label)
            if options.bypass_cs_deals:
                logger.info("cs.deals bypasses the proxy and uses a direct connection")
                print("Routing: Steam via proxy, cs.deals direct")
        else:
            logger.warning("No proxy configured for account '{}'", account.account_name)

        try:
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=False,
                    proxy=playwright_proxy,
                    no_viewport=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context.set_default_timeout(BROWSER_TIMEOUT_MS)
                context.set_default_navigation_timeout(BROWSER_TIMEOUT_MS)

                page = context.pages[0] if context.pages else context.new_page()
                self._prepare_browser_session(
                    context=context,
                    page=page,
                    cookies=cookies,
                    account_name=account.account_name,
                    username=account.username,
                    start_url=options.start_url,
                    verify_steam_session=options.verify_steam_session,
                    seed_cookies=options.seed_cookies,
                    force_refresh=options.refresh_cookies,
                )
                logger.info("Close the browser window to return to account menu")

                self._wait_until_closed(context)
        finally:
            session_lock.release()

    def _prepare_browser_session(
        self,
        context: Any,
        page: Any,
        cookies: List[Dict[str, Any]],
        account_name: str,
        username: str,
        start_url: str | None,
        verify_steam_session: bool,
        seed_cookies: bool,
        force_refresh: bool,
    ) -> None:
        """Seed cookies and open a start URL according to the selected mode."""
        if seed_cookies:
            should_seed = bool(
                cookies
                and (
                    force_refresh
                    or not self.profile_store.has_verified_session(account_name)
                )
            )
            if should_seed:
                self._seed_cookies(context, cookies)
                logger.info("Seeded {} cookies from storage", len(cookies))
            elif not cookies:
                logger.warning(
                    "No cookies found in storage for username '{}'", username
                )

        if start_url:
            self._open_start_url(page, start_url)

        if not verify_steam_session:
            return

        if context_has_steam_session(context):
            self.profile_store.mark_session_verified(account_name)
            logger.info("Steam session is active for '{}'", account_name)
            return

        if not cookies:
            self.profile_store.clear_session_verification(account_name)
            print(
                "Steam session is not active and no cookies are available in storage."
            )
            return

        logger.warning(
            "Steam session is not active for '{}', re-seeding cookies from storage",
            account_name,
        )
        print("Session not active. Applying cookies from storage...")

        self._seed_cookies(context, cookies)
        if start_url:
            self._open_start_url(page, start_url)

        if context_has_steam_session(context):
            self.profile_store.mark_session_verified(account_name)
            logger.info("Steam session restored from storage for '{}'", account_name)
            print("Steam session restored successfully.")
            return

        self.profile_store.clear_session_verification(account_name)
        print(
            "Steam session is still not active. "
            "Update cookies in pySDA and retry with --refresh-cookies."
        )

    def _open_start_url(self, page: Any, start_url: str) -> None:
        """Navigate the main page to the configured start URL."""
        page.goto(
            start_url,
            wait_until="domcontentloaded",
            timeout=BROWSER_TIMEOUT_MS,
        )
        logger.info("Navigated to {}", start_url)

    def _seed_cookies(self, context: Any, cookies: List[Dict[str, Any]]) -> None:
        """Inject cookies into a persistent browser context."""
        grouped = self._group_cookies_by_domain(cookies)
        for domain, domain_cookies in grouped.items():
            seed_page = context.new_page()
            seed_page.goto(
                self._domain_seed_url(domain),
                wait_until="domcontentloaded",
                timeout=BROWSER_TIMEOUT_MS,
            )
            context.add_cookies(domain_cookies)
            seed_page.close()

    def _group_cookies_by_domain(
        self,
        cookies: List[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group cookies by domain for safer seeding."""
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for cookie in cookies:
            domain = str(cookie.get("domain", "")).lstrip(".")
            grouped.setdefault(domain, []).append(cookie)
        return grouped

    def _wait_until_closed(self, context: Any) -> None:
        """Wait until the user closes the browser window."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        while context.pages:
            try:
                context.wait_for_event("close", timeout=BROWSER_TIMEOUT_MS)
                return
            except PlaywrightTimeoutError:
                logger.debug("Browser still open, waiting for close...")

    def _domain_seed_url(self, domain: str) -> str:
        """Build a URL used to attach cookies to a domain."""
        return f"https://{domain}/"
