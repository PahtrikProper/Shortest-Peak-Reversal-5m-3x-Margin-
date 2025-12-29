from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, List

import numpy as np
import pandas as pd
from tqdm import tqdm

from .config import TraderConfig
from .order_utils import bybit_fee_fn, calc_liq_price_short, resolve_leverage, simulate_order_fill


@dataclass
class StrategyParams:
    highest_high_lookback: int
    exit_type: str
    risk_fraction: float
    take_profit_pct: float


@dataclass
class BacktestMetrics:
    pnl_pct: float
    pnl_value: float
    final_balance: float
    avg_win: float
    avg_loss: float
    win_rate: float
    rr_ratio: float | None
    sharpe: float
    drawdown: float
    wins: int
    losses: int


def summarize_results(best_row: pd.DataFrame, starting_balance: float) -> Dict[str, float]:
    l = best_row.iloc[0]
    total_trades = int(l["wins"] + l["losses"])
    total_wins = int(l["wins"])
    total_losses = int(l["losses"])
    total_pnl = float(l["pnl_value"])
    final_balance = float(l["final_balance"])
    win_rate = (total_wins / total_trades) * 100 if total_trades > 0 else 0
    avg_win = float(l["avg_win"])
    avg_loss = float(l["avg_loss"])
    return {
        "Total Trades": total_trades,
        "Wins": total_wins,
        "Losses": total_losses,
        "Win Rate %": round(win_rate, 2),
        "Total PnL": round(total_pnl, 2),
        "Final Balance": round(final_balance, 2),
        "Average Win": round(avg_win, 2),
        "Average Loss": round(avg_loss, 2),
    }


class BacktestEngine:
    def __init__(self, config: TraderConfig):
        self.config = config
        self._last_trades: List[Dict] = []

    def _exit_target_for_row(self, row: pd.Series, exit_type: str) -> float:
        if exit_type == "highest_low":
            return float(row.get("highest_low", np.nan))
        if exit_type == "lowest_high":
            return float(row.get("lowest_high", np.nan))
        if exit_type == "midpoint":
            hi_low = row.get("highest_low", np.nan)
            lo_high = row.get("lowest_high", np.nan)
            if not np.isnan(hi_low) and not np.isnan(lo_high):
                return float((hi_low + lo_high) / 2)
        return float("nan")

    def _run_backtest(self, df_1m: pd.DataFrame, params: StrategyParams, capture_trades: bool = False) -> BacktestMetrics:
        data = df_1m.copy().sort_index()
        data["prev_highest_high"] = data["High"].rolling(params.highest_high_lookback).max().shift(1)
        data["highest_low"] = data["Low"].rolling(params.highest_high_lookback).max().shift(1)
        data["lowest_high"] = data["High"].rolling(params.highest_high_lookback).min().shift(1)

        data["entry_signal"] = (data["High"] >= data["prev_highest_high"]) & (data["Close"] < data["Open"])
        data["tradable"] = data["entry_signal"].notna()

        balance = self.config.starting_balance
        equity_curve: List[float] = []
        position_open = False
        entry_price = None
        entry_time = None
        liq_price = None
        qty = 0.0
        margin_used = 0.0
        exit_target = None
        entry_fill_status: str | None = None
        wins = 0
        losses = 0
        win_sizes: List[float] = []
        loss_sizes: List[float] = []
        trades: List[Dict] = [] if capture_trades else []

        warmup = params.highest_high_lookback + 1
        for i in range(warmup, len(data)):
            row = data.iloc[i]
            close = row["Close"]
            fill_price: float | None = None

            if not position_open and balance > 0 and bool(row["entry_signal"] and row["tradable"]):
                fill_price, fill_status = simulate_order_fill("short", close, self.config)
                if fill_status != "filled" or fill_price is None:
                    equity_curve.append(balance)
                    continue

                risk_fraction = min(max(params.risk_fraction, 0.0), 1.0)
                if risk_fraction == 0:
                    equity_curve.append(balance)
                    continue

                margin_used = balance * risk_fraction
                if margin_used < self.config.min_notional:
                    equity_curve.append(balance)
                    continue

                leverage_used = resolve_leverage(margin_used, self.config.desired_leverage, self.config)
                trade_value = margin_used * leverage_used
                if trade_value < self.config.min_notional:
                    equity_curve.append(balance)
                    continue

                entry_price = fill_price
                qty = trade_value / entry_price
                entry_fee = bybit_fee_fn(trade_value, self.config)
                balance -= entry_fee + margin_used
                liq_price = calc_liq_price_short(entry_price, int(leverage_used))
                exit_target = self._exit_target_for_row(row, params.exit_type)
                if np.isnan(exit_target) and entry_price is not None:
                    exit_target = entry_price * (1 - params.take_profit_pct)

                entry_time = row.name
                entry_fill_status = fill_status
                position_open = True

            if position_open and entry_price is not None and liq_price is not None:
                margin_call = row["High"] >= liq_price
                tp_hit = exit_target is not None and row["Low"] <= exit_target

                if margin_call:
                    net_pnl = -margin_used
                    balance = max(0.0, balance)
                    losses += 1
                    loss_sizes.append((net_pnl / self.config.starting_balance) * 100)
                    if capture_trades and entry_time is not None:
                        trades.append(
                            {
                                "entry_time": entry_time,
                                "exit_time": row.name,
                                "side": "SHORT",
                                "entry_price": entry_price,
                                "exit_price": liq_price,
                                "pnl_value": net_pnl,
                                "pnl_pct": (net_pnl / self.config.starting_balance) * 100,
                                "qty": qty,
                                "exit_type": "margin_call",
                                "fill_status": entry_fill_status,
                            }
                        )
                    position_open = False
                    entry_price = None
                    entry_time = None
                    liq_price = None
                    exit_target = None
                    qty = 0.0
                    margin_used = 0.0
                    entry_fill_status = None
                elif tp_hit:
                    exit_price = exit_target if tp_hit and exit_target is not None else close
                    exit_fee = bybit_fee_fn(qty * exit_price, self.config)
                    gross = (entry_price - exit_price) * qty
                    net_pnl = gross - exit_fee
                    balance += margin_used + net_pnl
                    if net_pnl > 0:
                        wins += 1
                        win_sizes.append((net_pnl / self.config.starting_balance) * 100)
                    else:
                        losses += 1
                        loss_sizes.append((net_pnl / self.config.starting_balance) * 100)

                    if capture_trades and entry_time is not None:
                        trades.append(
                            {
                                "entry_time": entry_time,
                                "exit_time": row.name,
                                "side": "SHORT",
                                "entry_price": entry_price,
                                "exit_price": exit_price,
                                "pnl_value": net_pnl,
                                "pnl_pct": (net_pnl / self.config.starting_balance) * 100,
                                "qty": qty,
                                "exit_type": params.exit_type,
                                "fill_status": entry_fill_status,
                            }
                        )
                    position_open = False
                    entry_price = None
                    entry_time = None
                    liq_price = None
                    exit_target = None
                    qty = 0.0
                    margin_used = 0.0
                    entry_fill_status = None

            if position_open and entry_price is not None:
                unrealized_pnl = (entry_price - close) * qty
                equity = balance + margin_used + unrealized_pnl
            else:
                equity = balance
            equity_curve.append(max(equity, 0))

        if not equity_curve:
            return BacktestMetrics(0, 0, self.config.starting_balance, 0, 0, 0, None, 0, 0, 0, 0)

        final_balance = equity_curve[-1]
        pnl_value = final_balance - self.config.starting_balance
        pnl_pct = (pnl_value / self.config.starting_balance) * 100
        avg_win = float(np.mean(win_sizes)) if win_sizes else 0
        avg_loss = float(np.mean(loss_sizes)) if loss_sizes else 0
        win_rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
        rr_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else None
        returns = pd.Series(equity_curve).pct_change().dropna()
        sharpe = (returns.mean() / returns.std()) * np.sqrt(365 * 24 * 60 / self.config.agg_minutes) if returns.std() != 0 else 0

        self._last_trades = trades if capture_trades else []
        return BacktestMetrics(pnl_pct, pnl_value, final_balance, avg_win, avg_loss, win_rate, rr_ratio, sharpe, 0, wins, losses)

    def run_backtest_with_trades(self, df_1m: pd.DataFrame, params: StrategyParams) -> tuple[pd.DataFrame, pd.DataFrame]:
        metrics = self._run_backtest(df_1m, params, capture_trades=True)
        trades_df = pd.DataFrame(self._last_trades) if hasattr(self, "_last_trades") else pd.DataFrame()
        metrics_df = pd.DataFrame([{**params.__dict__, **metrics.__dict__}])
        return metrics_df, trades_df

    def grid_search_with_progress(self, df_1m: pd.DataFrame) -> pd.DataFrame:
        results: List[Dict] = []
        total = (
            len(self.config.highest_high_lookback_range)
            * len(list(self.config.exit_type_candidates))
            * len(list(self.config.risk_fraction_candidates))
            * len(list(self.config.take_profit_pct_candidates))
        )

        for hh_lb, exit_type, risk_frac, tp_pct in tqdm(
            product(
                self.config.highest_high_lookback_range,
                self.config.exit_type_candidates,
                self.config.risk_fraction_candidates,
                self.config.take_profit_pct_candidates,
            ),
            total=total,
            desc="Param search",
            ncols=80,
        ):
            params = StrategyParams(int(hh_lb), str(exit_type), float(risk_frac), float(tp_pct))
            metrics = self._run_backtest(df_1m, params, capture_trades=False)
            results.append({**params.__dict__, **metrics.__dict__})

        return pd.DataFrame(results)
