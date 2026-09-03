"""Tests for browser launcher start-page session preparation."""

from pathlib import Path

from browser_launcher.launcher import BrowserLauncher
from browser_launcher.profile_store import ProfileStore

STEAM_COOKIE = {
    "name": "steamLoginSecure",
    "value": "abc",
    "domain": "steamcommunity.com",
    "path": "/",
}


class FakePage:
    """Minimal page double that records navigation."""

    def __init__(self) -> None:
        self.goto_urls: list[str] = []

    def goto(self, url: str, **kwargs) -> None:
        self.goto_urls.append(url)

    def close(self) -> None:
        return None


class FakeContext:
    """Minimal context double for cookie seeding and session checks."""

    def __init__(self, has_login: bool = True) -> None:
        self.has_login = has_login
        self.seed_pages: list[FakePage] = []
        self.added_cookies: list[dict] = []

    def new_page(self) -> FakePage:
        page = FakePage()
        self.seed_pages.append(page)
        return page

    def add_cookies(self, cookies: list[dict]) -> None:
        self.added_cookies.extend(cookies)
        self.has_login = True

    def cookies(self, url: str | None = None) -> list[dict]:
        if self.has_login:
            return [{"name": "steamLoginSecure", "value": "abc"}]
        return []


def _launcher(tmp_path: Path) -> BrowserLauncher:
    return BrowserLauncher(profile_store=ProfileStore(root_dir=tmp_path))


def test_prepare_does_nothing_when_nothing_selected(tmp_path: Path) -> None:
    """Nothing mode should not navigate, seed cookies, or check login."""
    launcher = _launcher(tmp_path)
    page = FakePage()
    context = FakeContext(has_login=False)

    launcher._prepare_browser_session(
        context=context,
        page=page,
        cookies=[STEAM_COOKIE],
        account_name="acc1",
        username="acc1",
        start_url=None,
        verify_steam_session=False,
        seed_cookies=False,
        force_refresh=True,
    )

    assert page.goto_urls == []
    assert context.seed_pages == []
    assert context.added_cookies == []


def test_prepare_opens_cs_deals_without_steam_login_check(tmp_path: Path) -> None:
    """CS.DEALS mode should seed cookies and open cs.deals without Steam verify."""
    launcher = _launcher(tmp_path)
    page = FakePage()
    context = FakeContext(has_login=False)

    launcher._prepare_browser_session(
        context=context,
        page=page,
        cookies=[STEAM_COOKIE],
        account_name="acc1",
        username="acc1",
        start_url="https://cs.deals/",
        verify_steam_session=False,
        seed_cookies=True,
        force_refresh=True,
    )

    assert page.goto_urls == ["https://cs.deals/"]
    assert context.added_cookies == [STEAM_COOKIE]
    assert launcher.profile_store.has_verified_session("acc1") is False


def test_prepare_steam_community_verifies_login(tmp_path: Path) -> None:
    """Steam Community mode should open community and mark a live session."""
    launcher = _launcher(tmp_path)
    page = FakePage()
    context = FakeContext(has_login=True)

    launcher._prepare_browser_session(
        context=context,
        page=page,
        cookies=[STEAM_COOKIE],
        account_name="acc1",
        username="acc1",
        start_url="https://steamcommunity.com/",
        verify_steam_session=True,
        seed_cookies=True,
        force_refresh=False,
    )

    assert page.goto_urls == ["https://steamcommunity.com/"]
    assert launcher.profile_store.has_verified_session("acc1") is True
