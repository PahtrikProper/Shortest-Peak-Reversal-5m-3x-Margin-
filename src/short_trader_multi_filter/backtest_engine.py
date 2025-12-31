from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, List

import numpy as np
import pandas as pd
from tqdm import tqdm

from .config import TraderConfig
from .order_utils import PositionState


@dataclass
class StrategyParams:
    sma_period: int
    stoch_period: int
    macd_fast: int
    macd_slow: int
    macd_signal: int
    use_macd: bool
    use_signal: bool
    use_momentum_exit: bool


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

    def _run_backtest(self, df: pd.DataFrame, params: StrategyParams, capture_trades: bool = False) -> BacktestMetrics:
        data = df.copy().sort_index()
        data["sma"] = data["Close"].rolling(params.sma_period).mean()

        lowest_low = data["Low"].rolling(params.stoch_period).min()
        highest_high = data["High"].rolling(params.stoch_period).max()
        raw_stoch = 100 * (data["Close"] - lowest_low) / (highest_high - lowest_low)
        raw_stoch = raw_stoch.replace([np.inf, -np.inf], np.nan).fillna(0)
        data["k"] = raw_stoch.rolling(self.config.smooth_k).mean() - 50

        data["ema_fast"] = data["Close"].ewm(span=params.macd_fast, adjust=False).mean()
        data["ema_slow"] = data["Close"].ewm(span=params.macd_slow, adjust=False).mean()
        data["macd"] = data["ema_fast"] - data["ema_slow"]
        data["signal"] = data["macd"].ewm(span=params.macd_signal, adjust=False).mean()

        balance = self.config.starting_balance
        equity_curve: List[float] = []
        position: PositionState | None = None
        wins = 0
        losses = 0
        win_sizes: List[float] = []
        loss_sizes: List[float] = []
        trades: List[Dict] = [] if capture_trades else []

        warmup = max(params.sma_period, params.stoch_period, params.macd_slow, params.macd_signal) + 2
        for i in range(warmup, len(data)):
            row = data.iloc[i]
            close = float(row["Close"])

            year = row.name.year
            month = row.name.month
            in_date = (year > self.config.start_year) or (year == self.config.start_year and month >= self.config.start_month)

            if position is None:
                if not in_date:
                    equity_curve.append(balance)
                    continue

                lows_ok = data["Low"].iloc[i - 2] <= data["Low"].iloc[i - 1] and data["Low"].iloc[i] < data["Low"].iloc[i - 1]
                sma_ok = row["sma"] < data["sma"].iloc[i - 1]
                macd_ok = (not params.use_macd) or (row["macd"] < data["macd"].iloc[i - 1])
                signal_ok = (not params.use_signal) or (row["signal"] < data["signal"].iloc[i - 1])

                if lows_ok and sma_ok and macd_ok and signal_ok and not np.isnan(row["sma"]):
                    risk_fraction = self.config.risk_fraction
                    margin_rate = self.config.margin_rate
                    position_value = (balance * risk_fraction) / margin_rate
                    qty = position_value / close
                    margin_used = balance * risk_fraction
                    if margin_used <= 0 or qty <= 0:
                        equity_curve.append(balance)
                        continue

                    balance -= margin_used
                    tp_price = close * (1 - 0.004)
                    position = PositionState(side="short", entry_price=close, tp_price=tp_price, qty=qty, entry_bar_time=row.name, margin_used=margin_used)
                    if capture_trades:
                        trades.append(
                            {
                                "entry_time": row.name,
                                "side": "SHORT",
                                "entry_price": close,
                                "qty": qty,
                                "margin_used": margin_used,
                            }
                        )
                    equity_curve.append(balance + margin_used)
                    continue

            else:
                exit_price: float | None = None
                tp_hit = row["Low"] <= (position.tp_price or 0)
                mom_exit = params.use_momentum_exit and (row["k"] > data["k"].iloc[i - 1])

                if tp_hit:
                    exit_price = float(position.tp_price)
                elif mom_exit:
                    exit_price = close

                if exit_price is not None:
                    gross = (position.entry_price - exit_price) * position.qty  # short PnL
                    balance += position.margin_used + gross
                    pnl_pct = (gross / self.config.starting_balance) * 100
                    if gross > 0:
                        wins += 1
                        win_sizes.append(pnl_pct)
                    else:
                        losses += 1
                        loss_sizes.append(pnl_pct)
                    if capture_trades:
                        trades.append(
                            {
                                "entry_time": position.entry_bar_time,
                                "exit_time": row.name,
                                "side": "SHORT",
                                "entry_price": position.entry_price,
                                "exit_price": exit_price,
                                "pnl_value": gross,
                                "pnl_pct": pnl_pct,
                                "qty": position.qty,
                                "exit_type": "tp" if tp_hit else "momentum",
                            }
                        )
                    position = None

            equity_curve.append(balance + (position.margin_used if position else 0))

        if position is not None:
            final_close = float(data.iloc[-1]["Close"])
            gross = (position.entry_price - final_close) * position.qty
            balance += position.margin_used + gross
            pnl_pct = (gross / self.config.starting_balance) * 100
            if gross > 0:
                wins += 1
                win_sizes.append(pnl_pct)
            else:
                losses += 1
                loss_sizes.append(pnl_pct)
            if capture_trades:
                trades.append(
                    {
                        "entry_time": position.entry_bar_time,
                        "exit_time": data.index[-1],
                        "side": "SHORT",
                        "entry_price": position.entry_price,
                        "exit_price": final_close,
                        "pnl_value": gross,
                        "pnl_pct": pnl_pct,
                        "qty": position.qty,
                        "exit_type": "eod",
                    }
                )
            equity_curve.append(balance)

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
            len(self.config.sma_period_range)
            * len(self.config.stoch_period_range)
            * len(self.config.use_macd_options)
            * len(self.config.use_signal_options)
            * len(self.config.use_momentum_exit_options)
        )

        for sma_p, stoch_p, use_macd, use_signal, use_mom in tqdm(
            product(
                self.config.sma_period_range,
                self.config.stoch_period_range,
                self.config.use_macd_options,
                self.config.use_signal_options,
                self.config.use_momentum_exit_options,
            ),
            total=total,
            desc="Param search",
            ncols=80,
        ):
            params = StrategyParams(
                sma_period=int(sma_p),
                stoch_period=int(stoch_p),
                macd_fast=self.config.macd_fast,
                macd_slow=self.config.macd_slow,
                macd_signal=self.config.macd_signal,
                use_macd=bool(use_macd),
                use_signal=bool(use_signal),
                use_momentum_exit=bool(use_mom),
            )
            metrics = self._run_backtest(df_1m, params, capture_trades=False)
            results.append({**params.__dict__, **metrics.__dict__})

        return pd.DataFrame(results)
