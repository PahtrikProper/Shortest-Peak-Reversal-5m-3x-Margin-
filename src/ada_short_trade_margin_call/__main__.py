"""CLI entry point for the Short Trade Margin Call trader.

Runs the backtest/optimization pass, writes ``data/best_params.json``, and then
starts the live trading loop with the optimal parameters.

Usage:
    python -m short_trade_margin_call
"""

from .main_engine import run


def main() -> None:
    """Execute the orchestrator."""

    run()


if __name__ == "__main__":
    main()
