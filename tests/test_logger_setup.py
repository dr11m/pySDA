"""Tests for logger exception helper."""

from src.utils.logger_setup import logger, log_exception


def test_log_exception_writes_traceback() -> None:
    messages: list[str] = []
    sink_id = logger.add(
        lambda message: messages.append(str(message)),
        level="ERROR",
        format="{message}\n{exception}",
        backtrace=True,
        diagnose=False,
    )

    try:
        try:
            1 / 0
        except Exception:
            log_exception("Division failed")
    finally:
        logger.remove(sink_id)

    output = "\n".join(messages)
    assert "Division failed" in output
    assert "ZeroDivisionError" in output
