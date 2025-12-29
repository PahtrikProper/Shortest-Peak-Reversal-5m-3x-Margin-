from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

DEFAULT_AGG_MINUTES = 5


@dataclass
class TraderConfig:
    symbol: str = "SOLUSDT"
    category: str = "linear"
    backtest_days: int = 7
    contract_type: str = "LinearPerpetual"  # Bybit futures contract type
    starting_balance: float = 472
    bybit_fee: float = 0.001
    agg_minutes: int = DEFAULT_AGG_MINUTES
    spread_bps: int = 2  # simulated spread in basis points (0.02%)
    slippage_bps: int = 3  # additional slippage beyond spread (avg in bps)
    order_reject_prob: float = 0.01  # probability an order is rejected (simulated failure)
    max_fill_latency: float = 0.5  # seconds
    risk_fraction: float = 0.95  # portion of available USDT to deploy per entry
    max_risk_fraction: float = 0.9  # cap similar to Bybit not allowing full balance as initial margin
    maintenance_margin_rate: float = 0.004  # Bybit linear perp maintenance margin (approximation)
    log_blocked_trades: bool = True  # verbose logging for rejected/skipped entries

    # Strategy inputs
    highest_high_lookback: int = 50
    take_profit_pct: float = 0.0044  # used as a fallback target when no structure target is available
    min_take_profit_pct: float = 0.0022  # minimum TP (0.22%); failing to hit counts as a loss
    # Only structural exits are searched by default; midpoint remains supported for backwards compatibility.
    exit_type_candidates: Sequence[str] = field(default_factory=lambda: ("highest_low", "lowest_high"))

    highest_high_lookback_range: Sequence[int] = field(default_factory=lambda: (10, 20, 30, 40, 50, 60, 70))
    take_profit_pct_candidates: Sequence[float] = field(default_factory=lambda: (0.0022, 0.0044, 0.0060, 0.0080))
    risk_fraction_candidates: Sequence[float] = field(default_factory=lambda: (0.5, 0.7, 0.85, 0.95))

    # Bybit leverage and liquidation handling
    desired_leverage: int = 3
    bybit_max_leverage: int = 50
    bybit_leverage_tiers: Sequence[tuple[float, int]] = field(
        default_factory=lambda: (
            (50000.0, 50),
            (100000.0, 25),
            (250000.0, 10),
        )
    )
    min_notional: float = 5.0

    # Live loop options
    live_history_days: int = 10
    min_history_padding: int = 200

    def as_log_string(self) -> str:
        return (
            f"Symbol: {self.symbol} | Category: {self.category}\n"
            f"Contract type: {self.contract_type}\n"
            f"Backtest window (days): {self.backtest_days} | Aggregation: {self.agg_minutes}m\n"
            f"Requested leverage: {self.desired_leverage}x | Bybit cap: {self.bybit_max_leverage}x\n"
            f"Fees: {self.bybit_fee * 100:.2f}% per trade | Spread model: {self.spread_bps} bps | Slippage model: ~{self.slippage_bps} bps\n"
            f"Order reject probability: {self.order_reject_prob * 100:.2f}% | Max simulated latency: {self.max_fill_latency}s\n"
            f"Risk per entry: min({self.risk_fraction * 100:.1f}%, {self.max_risk_fraction * 100:.1f}%) of available USDT | Min TP: {self.min_take_profit_pct * 100:.2f}%\n"
            f"Strategy: Short new highs, exit via tested structure targets (highest low / lowest high / midpoint) with Bybit-style liquidation and leverage gating."
        )
