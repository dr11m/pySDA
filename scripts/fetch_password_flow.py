"""Capture the password wizard entry with saved cookies using GET requests only."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import ParseResult, parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup
from loguru import logger
import requests

from src.cli.config_manager import ConfigManager
from src.factories import create_instance_from_config
from src.password_changer import HttpRequestHelper, SteamUrls
from src.steampy.client import SteamClient
from src.steampy.security import account_session_id


def fetch_password_flow(account_name: str, session_path: Path, output_dir: Path) -> Path:
    """Save an unmodified private response and print link paths without recovery tokens.

    Args:
        account_name: Configured account whose saved session should be inspected.
        session_path: Existing session file for the configured Steam login.
        output_dir: Private directory outside the repository for the raw HTML.

    Returns:
        Path to the original response bytes.
    """
    repository_root: Path = Path(__file__).resolve().parents[1]
    if output_dir.resolve().is_relative_to(repository_root):
        raise ValueError("Raw authenticated responses must be saved outside the repository")
    config: ConfigManager = ConfigManager()
    if not config.load_config() or not config.select_account(account_name):
        raise ValueError("The requested account is not configured")
    if session_path.stem != config.get("username"):
        raise ValueError("The session file does not match the configured account")
    if not session_path.is_file():
        raise ValueError("An existing saved session is required")
    proxy_config: dict[str, object] = config.get("proxy_provider")
    if not proxy_config or not proxy_config.get("module_path") or not proxy_config.get("class_name"):
        raise ValueError("An explicit account proxy provider is required")
    proxy: dict[str, str] | None = create_instance_from_config(proxy_config).get_proxy(account_name)
    client: SteamClient = SteamClient(
        username=config.get("username"),
        steam_id=config.get("steam_id"),
        session_path=str(session_path),
        proxies=proxy,
    )
    session: requests.Session = client._session
    if account_session_id(session, client.steam_id, SteamUrls.HELP_CHANGE_PASSWORD) is None:
        session.close()
        raise ValueError("The saved session does not authenticate the configured account on Steam Help")
    response: requests.Response = session.get(
        SteamUrls.HELP_CHANGE_PASSWORD,
        headers=HttpRequestHelper.get_common_headers(),
        timeout=client.request_timeout,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp: str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    raw_path: Path = output_dir / f"steam_password_entry_{timestamp}.html"
    raw_path.write_bytes(response.content)
    logger.info(f"Password entry captured: status={response.status_code} path={urlparse(response.url).path} raw_file={raw_path}")
    page: BeautifulSoup = BeautifulSoup(response.text, "html.parser")
    for anchor in page.find_all("a", href=True):
        link: ParseResult = urlparse(urljoin(response.url, anchor["href"]))
        if "HelpWithLoginInfo" not in link.path:
            continue
        query: dict[str, list[str]] = parse_qs(link.query)
        modes: dict[str, list[str]] = {key: query[key] for key in ("reset", "lost", "issueid") if key in query}
        logger.info(f"Password entry link: host={link.hostname} path={link.path} query_keys={sorted(query)} modes={modes}")
    session.close()
    return raw_path


def main() -> None:
    """Run the read-only capture without printing sensitive exception details."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("account_name")
    parser.add_argument("session_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    arguments: argparse.Namespace = parser.parse_args()
    try:
        fetch_password_flow(arguments.account_name, arguments.session_path, arguments.output_dir)
    except Exception as error:
        logger.error(f"Password entry capture failed: {type(error).__name__}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
