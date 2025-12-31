from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from .backtest_engine import BacktestEngine, StrategyParams, summarize_results
from .config import TraderConfig
from .data_client import DataClient
from .paths import DATA_DIR


class MainEngine:
    def __init__(self, config: Optional[TraderConfig] = None, best_params_path: Path | str | None = None):
        self.config = config or TraderConfig()
        self.data_client = DataClient(self.config)
        self.backtest_engine = BacktestEngine(self.config)
        self.best_params_path = Path(best_params_path) if best_params_path else DATA_DIR / "best_params.json"
        self.best_params_path.parent.mkdir(parents=True, exist_ok=True)

    def log_config(self):
        print("\n===== STRATEGY CONFIGURATION =====")
        print(self.config.as_log_string())
        print("==================================\n")

    def save_best_params(self, best: pd.Series, results: Dict[str, float]) -> None:
        payload = {
            "generated_at": pd.Timestamp.utcnow().isoformat() + "Z",
            "symbol": self.config.symbol,
            "category": self.config.category,
            "agg_minutes": self.config.agg_minutes,
            "params": {k: (v.item() if hasattr(v, "item") else v) for k, v in best.to_dict().items()},
            "results": results,
        }
        self.best_params_path.write_text(json.dumps(payload, indent=2))
        print(f"Saved optimal parameters to {self.best_params_path.resolve()}")

    def run_backtests(self) -> tuple[pd.DataFrame, pd.DataFrame, Dict[str, float]]:
        print(f"Fetching data and running optimizer on {self.config.agg_minutes}m bars...")
        df = self.data_client.fetch_bybit_bars(days=self.config.backtest_days, interval_minutes=self.config.agg_minutes)

        dfres = self.backtest_engine.grid_search_with_progress(df)
        best = dfres.sort_values("pnl_pct", ascending=False).head(1)
        results = summarize_results(best, self.config.starting_balance)

        print(f"\n==================== BEST PARAMETERS ({self.config.agg_minutes}m) ====================")
        print(best.to_string(index=False))
        print("\n============== BEST RESULTS ==============")
        for k, v in results.items():
            print(f"{k}: {v}")
        print("==================================================================\n")

        self.save_best_params(best.iloc[0], results)

        metrics_df, trades_df = self.backtest_engine.run_backtest_with_trades(
            df,
            StrategyParams(
                int(best.iloc[0]["sma_period"]),
                int(best.iloc[0]["stoch_period"]),
                int(best.iloc[0]["macd_fast"]),
                int(best.iloc[0]["macd_slow"]),
                int(best.iloc[0]["macd_signal"]),
                bool(best.iloc[0]["use_macd"]),
                bool(best.iloc[0]["use_signal"]),
                bool(best.iloc[0]["use_momentum_exit"]),
            ),
        )
        if not trades_df.empty:
            cols = ["entry_time", "exit_time", "entry_price", "exit_price", "pnl_value", "pnl_pct", "qty", "exit_type"]
            print("\n==== TRADES (BEST PARAMS) ====")
            print(trades_df[cols].to_string(index=False))
            print("====================================\n")
        else:
            print("\nNo trades recorded for best parameters.\n")

        return best, metrics_df, results

    def run(self):
        self.log_config()
        self.run_backtests()


def run():
    MainEngine().run()


if __name__ == "__main__":
    run()
