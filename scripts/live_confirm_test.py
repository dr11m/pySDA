"""Live check: confirm pending trades for one account with the new retry logic.

Runs the real bootstrap path (same as CLI) and processes confirmation-needed
trades for ACCOUNT_NAME. Observe logs for rate-limit retries.
"""

from src.cli.account_context import build_account_context
from src.cli.config_manager import ConfigManager

ACCOUNT_NAME = 'huozkuf3hu'


def main() -> None:
    config_manager = ConfigManager()
    if not config_manager.load_config():
        raise SystemExit('Failed to load config.yaml')

    context = build_account_context(config_manager, ACCOUNT_NAME)
    if not context:
        raise SystemExit(f'Failed to build account context for {ACCOUNT_NAME}')

    stats = context.trade_manager.process_confirmation_needed_trades(auto_confirm=True)
    print('STATS:', stats)


if __name__ == '__main__':
    main()
