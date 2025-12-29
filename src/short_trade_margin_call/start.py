"""Entry point for the Short Trade Margin Call workflow.

Running this file will:
1) Backtest and optimize parameters for the short highest-high breakdown strategy.
2) Save the best parameters to ``data/best_params.json``.
3) Launch the live trading loop with those parameters.

Usage (from repo root):
    PYTHONPATH=src python -m short_trade_margin_call.start
    # or, when invoked directly:
    python src/short_trade_margin_call/start.py
"""

from __future__ import annotations

import os
import sys

try:
    if __package__:
        from .main_engine import run  # type: ignore
    else:
        raise ImportError
except ImportError:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.append(repo_root)
    from short_trade_margin_call.main_engine import run  # type: ignore


if __name__ == "__main__":
    run()
