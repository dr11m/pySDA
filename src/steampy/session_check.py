"""Steam session liveness probe used before treating cookies as valid."""

from src.steampy.models import SteamUrl
from src.utils.logger_setup import logger

MARKET_LISTINGS_URL = f"{SteamUrl.COMMUNITY_URL}/market/mylistings?start=0&count=100"


def check_session_static(username: str, session) -> bool:
    """Return True when market/mylistings accepts the current cookies.

    Args:
        username: Steam account name used in logs.
        session: Requests session that already carries Steam cookies.

    Returns:
        True if the listings endpoint returns HTTP 200 without a login redirect.
    """
    response = session.get(MARKET_LISTINGS_URL)
    logger.info(
        f"Market listings session check for {username}: status {response.status_code}"
    )
    if response.status_code != 200:
        return False
    if "login" in response.url.lower():
        return False
    return True
