from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from .backtest_engine import BacktestEngine, StrategyParams, summarize_results
from .config import TraderConfig
from .data_client import DataClient
from .optimization_queue import OptimizationQueue
from .order_utils import PositionState, bybit_fee_fn, calc_liq_price_short, mark_to_market_equity, resolve_leverage
from .paths import DATA_DIR
from .sell_order_engine import SellOrderEngine


class LiveTradingEngine:
    def __init__(self, config: TraderConfig, params: StrategyParams, results: Dict[str, float]):
        self.config = config
        self.params = params
        self.results = results
        self.data_client = DataClient(config)
        self.sell_engine = SellOrderEngine(config)
        self.position: Optional[PositionState] = None
        self.tradelog = []
        self.equity = config.starting_balance
        self._last_signal_ts: Optional[pd.Timestamp] = None

    @staticmethod
    def _exit_target_for_row(row: pd.Series, exit_type: str) -> float:
        highest_low = row.get("highest_low", np.nan)
        lowest_high = row.get("lowest_high", np.nan)
        if exit_type == "highest_low":
            return float(highest_low)
        if exit_type == "lowest_high":
            return float(lowest_high)
        if exit_type == "midpoint" and not (np.isnan(highest_low) or np.isnan(lowest_high)):
            return float((highest_low + lowest_high) / 2)
        return float("nan")

    def _prepare_live_dataframe(self) -> pd.DataFrame:
        df_1m = self.data_client.fetch_bybit_bars(days=self.config.live_history_days, interval_minutes=self.config.agg_minutes)
        data = df_1m.copy().sort_index()
        lookback = self.params.highest_high_lookback
        data["prev_highest_high"] = data["High"].rolling(lookback).max().shift(1)
        data["highest_low"] = data["Low"].rolling(lookback).max().shift(1)
        data["lowest_high"] = data["High"].rolling(lookback).min().shift(1)
        data["entry_signal"] = (data["High"] >= data["prev_highest_high"]) & (data["Close"] < data["Open"])
        data["tradable"] = data["entry_signal"].notna()
        return data

    def _log_live_summary(self):
        trades_df = pd.DataFrame(self.tradelog)
        total_pnl = trades_df["pnl"].sum()
        total_trades = len(trades_df)
        wins = trades_df[trades_df["pnl"] > 0]
        losses = trades_df[trades_df["pnl"] <= 0]
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
        avg_win = wins["pnl"].mean() if len(wins) > 0 else 0
        avg_loss = losses["pnl"].mean() if len(losses) > 0 else 0
        print("\n==== LIVE SUMMARY (SHORT) ====")
        print(f"Total trades: {total_trades}")
        print(f"Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"Win rate: {win_rate:.2f}%")
        print(f"Total PnL: {total_pnl:.2f}")
        print(f"Average win: {avg_win:.2f}")
        print(f"Average loss: {avg_loss:.2f}")
        print("=====================================\n")

    def _print_entry(self, nowstr: str, position: PositionState):
        print(
            f"{nowstr} | ENTRY (SHORT) @ {position.entry_price:.4f} | "
            f"qty={position.qty:.4f} | LIQ={position.liq_price:.4f} | leverage={position.leverage:.2f}x"
        )

    def _handle_exit(self, row: pd.Series, nowstr: str):
        if not self.position:
            return

        margin_call = row["High"] >= (self.position.liq_price or 0)
        tp_hit = self.position.exit_target is not None and row["Low"] <= self.position.exit_target
        exit_cond = margin_call or tp_hit
        if not exit_cond or not self.position:
            return

        if margin_call:
            exit_price = float(self.position.liq_price or row["High"])
            net_pnl = -self.position.margin_used
            status = "MARGIN CALL"
        else:
            exit_price = float(self.position.exit_target if tp_hit and self.position.exit_target else row["Close"])
            gross = (self.position.entry_price - exit_price) * self.position.qty  # type: ignore[operator]
            exit_fee = bybit_fee_fn(self.position.qty * exit_price, self.config)  # type: ignore[arg-type]
            net_pnl = gross - exit_fee
            self.equity += self.position.margin_used + net_pnl
            status = "TARGET"

        self.tradelog.append(
            {
                "entry_time": self.position.entry_bar_time,
                "exit_time": row.name,
                "side": self.position.side.upper(),
                "entry_price": self.position.entry_price,
                "exit_price": exit_price,
                "qty": self.position.qty,
                "pnl": net_pnl,
                "status": status,
                "equity": self.equity,
                "margin_used": self.position.margin_used,
                "exit_type": self.position.exit_type,
            }
        )
        print(f"{nowstr} | EXIT @ {exit_price:.4f} | {status} | NetPnL={net_pnl:.2f} | Equity={self.equity:.2f}")
        self.position = None

    def run(self):
        print(
            "\n--- Live Short Trader (HH breakdown → structured exits) "
            f"lookback={self.params.highest_high_lookback}, exit={self.params.exit_type}, "
            f"agg={self.config.agg_minutes}m ---\n"
        )

        while True:
            try:
                data = self._prepare_live_dataframe()
                min_required = self.params.highest_high_lookback + self.config.min_history_padding
                if len(data) < min_required:
                    print("Waiting for enough bars...")
                    time.sleep(2)
                    continue

                row = data.iloc[-1]
                nowstr = time.strftime("%Y-%m-%d %H:%M", time.gmtime())

                if self.results.get("Total PnL", 0) <= 0:
                    print(f"{nowstr} | NO EDGE detected by optimizer – standing aside.")
                    time.sleep(60 * self.config.agg_minutes)
                    continue

                if not self.position:
                    if self.sell_engine.should_enter(row, None) and row.name != self._last_signal_ts:
                        position, status, entry_fee, _, margin_used = self.sell_engine.open_position(
                            row,
                            available_usdt=self.equity,
                        )
                        if status in {"rejected", "min_notional_not_met"} or not position:
                            print(f"{nowstr} | ENTRY (SHORT) rejected – simulated failure (no trade)")
                        elif status == "insufficient_funds":
                            print(f"{nowstr} | ENTRY (SHORT) skipped – insufficient USDT balance")
                        else:
                            position.exit_type = self.params.exit_type
                            position.exit_target = self._exit_target_for_row(row, self.params.exit_type)
                            if np.isnan(position.exit_target):
                                position.exit_target = position.entry_price * (1 - self.config.take_profit_pct)  # type: ignore[operator]
                            position.liq_price = calc_liq_price_short(position.entry_price, int(position.leverage))
                            self.equity -= (entry_fee + margin_used)
                            self.position = position
                            self._print_entry(nowstr, position)
                            self._last_signal_ts = row.name
                    else:
                        print(f"{nowstr} | NO TRADE – waiting for a new signal.")

                self._handle_exit(row, nowstr)

                marked_equity = mark_to_market_equity(
                    self.equity,
                    -1 if self.position and self.position.side == "short" else 0,
                    self.position.entry_price if self.position else None,
                    self.position.qty if self.position else 0,
                    row["Close"],
                    self.position.margin_used if self.position else 0.0,
                )
                if self.position:
                    print(
                        f"{nowstr} | Equity (realized/unrealized): {self.equity:.2f} / {marked_equity:.2f} | Trades: {len(self.tradelog)}"
                    )
                else:
                    print(f"{nowstr} | Equity: {self.equity:.2f} | Trades: {len(self.tradelog)}")

                if len(self.tradelog) > 0:
                    self._log_live_summary()

                time.sleep(60 * self.config.agg_minutes)

            except KeyboardInterrupt:
                print("\nStopped by user.")
                break
            except Exception as exc:  # noqa: BLE001
                print("Exception:", exc)
                time.sleep(2)


class MainEngine:
    def __init__(self, config: Optional[TraderConfig] = None, best_params_path: Path | str | None = None):
        self.config = config or TraderConfig()
        self.data_client = DataClient(self.config)
        self.backtest_engine = BacktestEngine(self.config)
        self.best_params_path = Path(best_params_path) if best_params_path else DATA_DIR / "best_params.json"
        self.best_params_path.parent.mkdir(parents=True, exist_ok=True)
        self.optimization_queue = OptimizationQueue()

    def log_config(self):
        print("\n===== LIVE TRADER CONFIGURATION =====")
        print(self.config.as_log_string())
        print("======================================\n")

    def _normalize_row(self, row: pd.Series) -> Dict:
        normalized: Dict[str, float | int | str] = {}
        for key, value in row.to_dict().items():
            if isinstance(value, (np.floating, np.integer)):
                normalized[key] = value.item()
            else:
                normalized[key] = value
        return normalized

    def save_best_params(self, best: pd.Series, results: Dict[str, float]) -> None:
        payload = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "symbol": self.config.symbol,
            "category": self.config.category,
            "agg_minutes": self.config.agg_minutes,
            "leverage": self.config.desired_leverage,
            "spread_bps": self.config.spread_bps,
            "slippage_bps": self.config.slippage_bps,
            "order_reject_prob": self.config.order_reject_prob,
            "max_fill_latency": self.config.max_fill_latency,
            "params": self._normalize_row(best),
            "results": results,
        }
        self.best_params_path.write_text(json.dumps(payload, indent=2))
        print(f"Saved optimal parameters to {self.best_params_path.resolve()}")

    def queue_best_params(self, best: pd.Series, results: Dict[str, float], elapsed_seconds: float) -> Dict:
        queued_at = datetime.utcnow()
        ready_at = queued_at + timedelta(days=2)
        payload = {
            "symbol": self.config.symbol,
            "category": self.config.category,
            "agg_minutes": self.config.agg_minutes,
            "backtest_days": self.config.backtest_days,
            "starting_balance": self.config.starting_balance,
            "params": self._normalize_row(best),
            "results": results,
        }
        queued_item = self.optimization_queue.enqueue(
            queued_at=queued_at,
            ready_at=ready_at,
            elapsed_seconds=elapsed_seconds,
            payload=payload,
        )
        print(f"Queued next optimization run for ~{ready_at.isoformat()}Z (elapsed {elapsed_seconds:.2f}s; cadence=2d).")
        print(f"Queue file: {self.optimization_queue.queue_path.resolve()}")
        return queued_item

    def run_backtests(self) -> tuple[pd.DataFrame, pd.DataFrame, Dict[str, float]]:
        print(f"Fetching data and running optimizer on {self.config.agg_minutes}m bars...")
        start_time = time.monotonic()
        df_1m = self.data_client.fetch_bybit_bars(interval_minutes=self.config.agg_minutes, days=self.config.backtest_days)
        required_bars = max(self.config.highest_high_lookback_range) + self.config.min_history_padding
        if len(df_1m) < required_bars:
            raise ValueError(f"Not enough candles fetched for optimizer warmup: need {required_bars}, got {len(df_1m)}")

        dfres = self.backtest_engine.grid_search_with_progress(df_1m)
        best = dfres.sort_values("pnl_pct", ascending=False).head(1)
        results = summarize_results(best, self.config.starting_balance)

        print(f"\n==================== BEST SHORT PARAMETERS ({self.config.agg_minutes}m) ====================")
        print(best.to_string(index=False))
        print("\n============== BEST RESULTS (SHORT) ==============")
        for k, v in results.items():
            print(f"{k}: {v}")
        print("==================================================================\n")

        self.save_best_params(best.iloc[0], results)
        elapsed_seconds = time.monotonic() - start_time
        self.queue_best_params(best.iloc[0], results, elapsed_seconds)

        metrics_df, trades_df = self.backtest_engine.run_backtest_with_trades(
            df_1m,
            StrategyParams(
                int(best.iloc[0]["highest_high_lookback"]),
                str(best.iloc[0]["exit_type"]),
            ),
        )
        if not trades_df.empty:
            cols = ["entry_time", "exit_time", "entry_price", "exit_price", "pnl_value", "pnl_pct", "qty", "exit_type"]
            print("\n==== TRADES (SHORT, BEST PARAMS) ====")
            print(trades_df[cols].to_string(index=False))
            print("====================================\n")
        else:
            print("\nNo trades recorded for best parameters.\n")

        return best, metrics_df, results

    def run(self):
        self.log_config()
        best, _, results = self.run_backtests()

        print("\nAuto-starting live paper trading immediately after backtests (per requirements).")
        params = StrategyParams(int(best.iloc[0]["highest_high_lookback"]), str(best.iloc[0]["exit_type"]))
        LiveTradingEngine(self.config, params, results).run()


def run():
    MainEngine().run()


if __name__ == "__main__":
    run()
