"""CLI entry point for the interactive Short Trade Margin Call trader.

Prompts for a USDT pair, runs the backtest/optimization pass, writes ``data/your/best_params.json``,
and then starts the live trading loop with the optimal parameters.

Usage:
    python -m your_short_trade_margin_call
"""

from .main_engine import run


def main() -> None:
    """Execute the orchestrator."""

    run()


if __name__ == "__main__":
    main()
