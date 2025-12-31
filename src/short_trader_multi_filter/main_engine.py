from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from .backtest_engine import BacktestEngine, StrategyParams, summarize_results
from .config import TraderConfig
from .data_client import DataClient
from .paths import DATA_DIR


class LiveTradingEngine:
    def __init__(self, config: TraderConfig, params: StrategyParams, results: Dict[str, float]):
        self.config = config
        self.params = params
        self.results = results
        self.data_client = DataClient(config)
        self.position: Optional[Dict] = None
        self.equity = config.starting_balance

    def _prepare_dataframe(self) -> pd.DataFrame:
        bars = self.data_client.fetch_bybit_bars(days=self.config.live_history_days, interval_minutes=self.config.agg_minutes)
        data = bars.copy().sort_index()
        data["sma"] = data["Close"].rolling(self.params.sma_period).mean()

        lowest_low = data["Low"].rolling(self.params.stoch_period).min()
        highest_high = data["High"].rolling(self.params.stoch_period).max()
        raw_stoch = 100 * (data["Close"] - lowest_low) / (highest_high - lowest_low)
        raw_stoch = raw_stoch.replace([pd.NA, pd.NaT, float("inf"), float("-inf")], 0).fillna(0)
        data["k"] = raw_stoch.rolling(self.config.smooth_k).mean() - 50

        data["ema_fast"] = data["Close"].ewm(span=self.params.macd_fast, adjust=False).mean()
        data["ema_slow"] = data["Close"].ewm(span=self.params.macd_slow, adjust=False).mean()
        data["macd"] = data["ema_fast"] - data["ema_slow"]
        data["signal"] = data["macd"].ewm(span=self.params.macd_signal, adjust=False).mean()
        return data

    def _should_enter(self, data: pd.DataFrame) -> bool:
        if self.position is not None:
            return False
        row = data.iloc[-1]
        year, month = row.name.year, row.name.month
        in_date = (year > self.config.start_year) or (year == self.config.start_year and month >= self.config.start_month)
        if not in_date:
            return False
        lows_ok = data["Low"].iloc[-3] <= data["Low"].iloc[-2] and data["Low"].iloc[-1] < data["Low"].iloc[-2]
        sma_ok = row["sma"] < data["sma"].iloc[-2]
        macd_ok = (not self.params.use_macd) or (row["macd"] < data["macd"].iloc[-2])
        signal_ok = (not self.params.use_signal) or (row["signal"] < data["signal"].iloc[-2])
        return lows_ok and sma_ok and macd_ok and signal_ok and not pd.isna(row["sma"])

    def _enter(self, row: pd.Series):
        risk_fraction = self.config.risk_fraction
        margin_rate = self.config.margin_rate
        position_value = (self.equity * risk_fraction) / margin_rate
        qty = position_value / float(row["Close"])
        margin_used = self.equity * risk_fraction
        if margin_used <= 0 or qty <= 0:
            return
        self.equity -= margin_used
        tp_price = float(row["Close"]) * (1 - 0.004)
        # approximate liquidation similar to Bybit short: entry * (1 + margin_rate)
        liq_price = float(row["Close"]) * (1 + margin_rate)
        self.position = {
            "entry_price": float(row["Close"]),
            "tp_price": tp_price,
            "qty": qty,
            "margin_used": margin_used,
            "entry_time": row.name,
            "liq_price": liq_price,
        }
        print(f"ENTER SHORT @ {row['Close']:.6f} qty={qty:.4f} TP={tp_price:.6f} LIQ={liq_price:.6f} Equity={self.equity:.2f}")

    def _maybe_exit(self, data: pd.DataFrame):
        if self.position is None:
            return
        row = data.iloc[-1]
        tp_hit = row["Low"] <= self.position["tp_price"]
        mom_exit = self.params.use_momentum_exit and (row["k"] > data["k"].iloc[-2])
        margin_call = row["High"] >= self.position.get("liq_price", float("inf"))
        exit_price: Optional[float] = None
        exit_type = None
        if margin_call:
            exit_price = float(self.position.get("liq_price", row["High"]))
            exit_type = "margin_call"
        elif tp_hit:
            exit_price = float(self.position["tp_price"])
            exit_type = "tp"
        elif mom_exit:
            exit_price = float(row["Close"])
            exit_type = "momentum"
        if exit_price is None:
            return
        gross = (self.position["entry_price"] - exit_price) * self.position["qty"]
        self.equity += self.position["margin_used"] + gross
        print(
            f"EXIT @ {exit_price:.6f} type={exit_type} pnl={gross:.4f} equity={self.equity:.2f}"
        )
        self.position = None

    def _log_status(self, row: pd.Series):
        nowstr = row.name.strftime("%Y-%m-%d %H:%M")
        if self.position:
            print(
                f"{nowstr} | STATUS | pos=SHORT qty={self.position['qty']:.4f} "
                f"entry={self.position['entry_price']:.6f} tp={self.position['tp_price']:.6f} "
                f"liq={self.position.get('liq_price', float('nan')):.6f} "
                f"last={float(row['Close']):.6f} equity={self.equity:.2f}"
            )
        else:
            print(
                f"{nowstr} | STATUS | flat | last={float(row['Close']):.6f} "
                f"sma={float(row['sma']):.6f} k={float(row['k']):.3f} "
                f"macd={float(row['macd']):.6f} signal={float(row['signal']):.6f} "
                f"equity={self.equity:.2f}"
            )

    def run(self):
        print("\n--- Live Short Trader (multi-filter) ---\n")
        while True:
            try:
                data = self._prepare_dataframe()
                self._maybe_exit(data)
                if self._should_enter(data):
                    self._enter(data.iloc[-1])
                # Always provide a heartbeat so paper trading has useful updates.
                self._log_status(data.iloc[-1])
                time.sleep(60 * self.config.agg_minutes)
            except KeyboardInterrupt:
                print("Stopped by user.")
                break
            except Exception as exc:  # noqa: BLE001
                print("Exception in live loop:", exc)
                time.sleep(2)


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
        best, _, results = self.run_backtests()
        params = StrategyParams(
            int(best.iloc[0]["sma_period"]),
            int(best.iloc[0]["stoch_period"]),
            int(best.iloc[0]["macd_fast"]),
            int(best.iloc[0]["macd_slow"]),
            int(best.iloc[0]["macd_signal"]),
            bool(best.iloc[0]["use_macd"]),
            bool(best.iloc[0]["use_signal"]),
            bool(best.iloc[0]["use_momentum_exit"]),
        )
        LiveTradingEngine(self.config, params, results).run()


def run():
    MainEngine().run()


if __name__ == "__main__":
    run()
