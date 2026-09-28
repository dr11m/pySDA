"""Steam HTTP adapter with configured timeouts and safe progress logging."""

import time
from urllib.parse import SplitResult, urlsplit

from pydantic import BaseModel, ConfigDict, Field
from loguru import logger
from requests import PreparedRequest, Response
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException


class SteamHttpSettings(BaseModel):
    """Required Steam request settings from config.yaml."""

    model_config: ConfigDict = ConfigDict(allow_inf_nan=False, hide_input_in_errors=True)

    min_request_delay_ms: int = Field(ge=0)
    request_connect_timeout_seconds: float = Field(gt=0)
    request_read_timeout_seconds: float = Field(gt=0)
    check_ip_on_every_steam_request: bool

    @property
    def timeout(self) -> tuple[float, float]:
        """Return the connection and socket read timeouts."""
        return self.request_connect_timeout_seconds, self.request_read_timeout_seconds


class DelayedHTTPAdapter(HTTPAdapter):
    """Apply request timeouts and a delay after each Steam request."""

    __attrs__: list[str] = HTTPAdapter.__attrs__ + ["delay", "timeout", "username"]

    def __init__(self, *, delay: float, timeout: tuple[float, float], username: str | None = None) -> None:
        """Initialize explicitly configured request timing."""
        self.delay: float = delay
        self.timeout: tuple[float, float] = timeout
        self.username: str | None = username
        super().__init__()

    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: float | tuple[float, float] | None = None,
        verify: bool | str = True,
        cert: str | tuple[str, str] | None = None,
        proxies: dict[str, str] | None = None,
    ) -> Response:
        """Send a request and log timing without query parameters or payloads."""
        effective_timeout: float | tuple[float, float] = self.timeout if timeout is None else timeout
        parsed: SplitResult = urlsplit(request.url)
        endpoint: str = parsed._replace(query="", fragment="", netloc=parsed.hostname or "").geturl()
        route: str = "proxy" if proxies else "direct"
        started: float = time.monotonic()
        logger.debug(
            f"Steam HTTP request started: account={self.username} method={request.method} endpoint={endpoint} "
            f"route={route} timeout={effective_timeout}"
        )
        try:
            response: Response = super().send(request, stream=stream, timeout=effective_timeout, verify=verify, cert=cert, proxies=proxies)
            if not stream:
                # Include response body reads in completion timing and error logs.
                response.content
            phase: str = "headers received" if stream else "completed"
            logger.debug(
                f"Steam HTTP request {phase}: account={self.username} method={request.method} endpoint={endpoint} "
                f"status={response.status_code} elapsed={time.monotonic() - started:.3f}s"
            )
            return response
        except RequestException as error:
            logger.warning(
                f"Steam HTTP request failed: account={self.username} method={request.method} endpoint={endpoint} "
                f"error={type(error).__name__} elapsed={time.monotonic() - started:.3f}s"
            )
            raise
        finally:
            if self.delay > 0:
                logger.debug(f"Steam HTTP request delay: account={self.username} seconds={self.delay:.2f} endpoint={endpoint}")
                time.sleep(self.delay)
