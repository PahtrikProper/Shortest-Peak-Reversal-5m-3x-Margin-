"""CLI entry point for the Short Trader Multi Filter package.

Prompts for a USDT pair, runs the backtest/optimization pass, and writes ``data/multi_filter/best_params.json``.

Usage:
    python -m short_trader_multi_filter
"""

from .config import TraderConfig
from .main_engine import MainEngine


def main() -> None:
    """Execute the orchestrator."""
    MainEngine(config=TraderConfig()).run()


if __name__ == "__main__":
    main()
