from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .config import TraderConfig


def bybit_fee_fn(trade_value: float, config: TraderConfig) -> float:
    return trade_value * config.bybit_fee


def simulate_order_fill(
    direction: str,
    mid_price: float,
    config: TraderConfig,
    spread_bps: Optional[float] = None,
    slippage_bps: Optional[float] = None,
    reject_prob: Optional[float] = None,
) -> Tuple[Optional[float], str]:
    spread_bps = spread_bps if spread_bps is not None else config.spread_bps
    slippage_bps = slippage_bps if slippage_bps is not None else config.slippage_bps
    reject_prob = reject_prob if reject_prob is not None else config.order_reject_prob

    if random.random() < reject_prob:
        return None, "rejected"

    spread = mid_price * (spread_bps / 10000)
    slippage = abs(np.random.normal(slippage_bps, slippage_bps / 2))
    slippage_amt = mid_price * (slippage / 10000)

    if direction == "long":
        fill_price = mid_price + spread + slippage_amt
    else:
        fill_price = mid_price - spread - slippage_amt

    time.sleep(random.uniform(0, config.max_fill_latency))
    return fill_price, "filled"


def mark_to_market_equity(
    cash_equity: float,
    position: int,
    entry_price: Optional[float],
    qty: float,
    last_price: float,
    margin_used: float = 0.0,
) -> float:
    total = cash_equity + margin_used
    if position == 1 and entry_price:
        total += (last_price - entry_price) * qty
    if position == -1 and entry_price:
        total += (entry_price - last_price) * qty
    return total


def calc_liq_price_long(entry_price: float, leverage: int) -> float:
    return entry_price * (1 - 1 / leverage)


def calc_liq_price_short(entry_price: float, leverage: int, config: TraderConfig) -> float:
    """Approximate Bybit linear perp liquidation with maintenance margin + taker fee."""
    mm_rate = getattr(config, "maintenance_margin_rate", 0.004)
    taker_fee = config.bybit_fee
    liq_price = entry_price * (1 + (1 / leverage) - mm_rate + taker_fee)
    return max(liq_price, 0.0)


def allowed_leverage_for_notional(notional: float, tiers: Sequence[tuple[float, int]], max_leverage: int) -> int:
    """Return the maximum leverage Bybit would allow for the proposed notional."""
    sorted_tiers = sorted(tiers, key=lambda x: x[0])
    for threshold, lev in sorted_tiers:
        if notional <= threshold:
            return max(1, min(int(lev), max_leverage))
    # If above the largest threshold, fall back to the smallest leverage in the last tier
    return max(1, min(int(sorted_tiers[-1][1]), max_leverage))


def resolve_leverage(margin_used: float, desired_leverage: float, config: TraderConfig) -> float:
    """Clamp requested leverage against Bybit tier rules and the configured cap."""
    leverage = min(desired_leverage, config.bybit_max_leverage)
    if margin_used <= 0:
        return 1.0

    # Iteratively clamp leverage until notional fits within the allowed tier.
    while True:
        notional = margin_used * leverage
        allowed = allowed_leverage_for_notional(notional, config.bybit_leverage_tiers, config.bybit_max_leverage)
        if leverage <= allowed or leverage <= 1:
            return max(1.0, float(leverage))
        leverage = float(allowed)


@dataclass
class PositionState:
    side: Optional[str] = None  # "long" or "short"
    entry_price: Optional[float] = None
    tp_price: Optional[float] = None
    liq_price: Optional[float] = None
    qty: float = 0.0
    entry_bar_time: Optional[pd.Timestamp] = None
    entry_fee: float = 0.0
    trade_value: float = 0.0
    margin_used: float = 0.0
    leverage: float = 1.0
    exit_type: Optional[str] = None
    exit_target: Optional[float] = None
