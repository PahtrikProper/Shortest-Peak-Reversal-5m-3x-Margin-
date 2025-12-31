from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

DEFAULT_AGG_MINUTES = 3


@dataclass
class TraderConfig:
    symbol: str = "BTCUSDT"
    category: str = "linear"
    backtest_days: float = 0.125  # 3 hours
    contract_type: str = "LinearPerpetual"
    starting_balance: float = 1000.0
    bybit_fee: float = 0.0  # commission = 0
    agg_minutes: int = DEFAULT_AGG_MINUTES
    spread_bps: int = 0
    slippage_bps: int = 0
    order_reject_prob: float = 0.0
    max_fill_latency: float = 0.0
    risk_fraction: float = 0.95  # 95% equity
    margin_rate: float = 0.19  # short margin requirement
    log_blocked_trades: bool = True
    start_year: int = 2020
    start_month: int = 1

    # Strategy inputs
    sma_period: int = 50
    stoch_period: int = 14
    smooth_k: int = 2
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    use_macd: bool = True
    use_signal: bool = True
    use_momentum_exit: bool = True

    # Ranges for optional sweeps
    sma_period_range: Sequence[int] = field(default_factory=lambda: (50,))
    stoch_period_range: Sequence[int] = field(default_factory=lambda: (14,))
    use_macd_options: Sequence[bool] = field(default_factory=lambda: (True, False))
    use_signal_options: Sequence[bool] = field(default_factory=lambda: (True, False))
    use_momentum_exit_options: Sequence[bool] = field(default_factory=lambda: (True, False))

    # Live loop options
    live_history_days: int = 1
    min_history_padding: int = 200

    def as_log_string(self) -> str:
        return (
            f"Symbol: {self.symbol} | Category: {self.category}\n"
            f"Contract type: {self.contract_type}\n"
            f"Backtest window (days): {self.backtest_days} (~{self.backtest_days*24:.1f}h) | Aggregation: {self.agg_minutes}m\n"
            f"Fees: {self.bybit_fee * 100:.2f}% | Spread: {self.spread_bps} bps | Slippage: {self.slippage_bps} bps\n"
            f"Risk per entry: {self.risk_fraction * 100:.1f}% equity | Margin rate: {self.margin_rate * 100:.1f}% | Start date: {self.start_year}-{self.start_month:02d}\n"
            "Strategy: Short-only, date-filtered, SMA + centered Stoch + optional MACD/Signal filters, fixed 0.4% TP, optional momentum exit."
        )
