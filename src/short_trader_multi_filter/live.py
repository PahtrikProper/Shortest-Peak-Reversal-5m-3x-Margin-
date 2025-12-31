from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from .backtest_engine import StrategyParams
from .config import TraderConfig
from .main_engine import LiveTradingEngine
from .paths import DATA_DIR


def load_saved_params(best_params_path: Optional[Path] = None) -> Optional[StrategyParams]:
    path = best_params_path or DATA_DIR / "best_params.json"
    if not path.exists():
        print(f"No saved parameters found at {path}.")
        return None

    payload = json.loads(path.read_text())
    params = payload.get("params", {})
    try:
        return StrategyParams(
            int(params["highest_high_lookback"]),
            str(params["exit_type"]),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Saved params missing fields: {exc}")
        return None


def run_live_trading(config: Optional[TraderConfig] = None, best_params_path: Optional[Path] = None) -> None:
    config = config or TraderConfig()
    params = load_saved_params(best_params_path)
    if params is None:
        raise SystemExit("Cannot start live trading without saved parameters. Run the optimizer first.")

    results = {"Total PnL": 1.0}  # allow trading if params exist; live equity will drive outcomes
    LiveTradingEngine(config, params, results).run()


if __name__ == "__main__":
    run_live_trading()
