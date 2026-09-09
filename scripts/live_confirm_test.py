"""Live check: confirm pending trades for one account with the new retry logic.

Runs the real bootstrap path (same as CLI) and processes confirmation-needed
trades for the account passed on the command line. No account names live in
this file.
"""

import sys

from src.cli.account_context import build_account_context
from src.cli.config_manager import ConfigManager


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        raise SystemExit('Usage: python scripts/live_confirm_test.py <account_name>')

    account_name = sys.argv[1].strip()
    config_manager = ConfigManager()
    if not config_manager.load_config():
        raise SystemExit('Failed to load config.yaml')

    context = build_account_context(config_manager, account_name)
    if not context:
        raise SystemExit(f'Failed to build account context for {account_name}')

    stats = context.trade_manager.process_confirmation_needed_trades(auto_confirm=True)
    print('STATS:', stats)


if __name__ == '__main__':
    main()
