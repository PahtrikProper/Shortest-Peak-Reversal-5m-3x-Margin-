"""CLI entry point for the Short Trader Multi Filter package.

Prompts for a USDT pair, runs the backtest/optimization pass, and writes ``data/multi_filter/best_params.json``.

Usage:
    python -m short_trader_multi_filter
"""

from .main_engine import run


def main() -> None:
    """Execute the orchestrator."""

    run()


if __name__ == "__main__":
    main()
