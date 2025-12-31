"""Interactive entry point for the Short Trader Multi Filter workflow.

Running this file will:
1) Prompt for a USDT pair symbol.
2) Backtest and optimize parameters for that symbol.
3) Save the best parameters to ``data/multi_filter/best_params.json``.

Usage (from repo root):
    PYTHONPATH=src python -m short_trader_multi_filter.start
    # or, when invoked directly:
    python src/short_trader_multi_filter/start.py
"""

from __future__ import annotations

import os
import sys

if __package__ is None or __package__ == "":
    # Allow execution as a script: python src/short_trader_multi_filter/start.py
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.append(repo_root)
    from short_trader_multi_filter.config import TraderConfig  # type: ignore
    from short_trader_multi_filter.main_engine import MainEngine  # type: ignore
    from short_trader_multi_filter.paths import DATA_DIR  # type: ignore
else:
    from .config import TraderConfig
    from .main_engine import MainEngine
    from .paths import DATA_DIR


def run():
    symbol = input("Enter USDT pair symbol (e.g., BTCUSDT): ").strip().upper()
    if symbol and not symbol.endswith("USDT"):
        symbol = f"{symbol}USDT"
    if not symbol:
        symbol = "BTCUSDT"

    config = TraderConfig(symbol=symbol)
    MainEngine(config=config, best_params_path=DATA_DIR / "best_params.json").run()


if __name__ == "__main__":
    run()
