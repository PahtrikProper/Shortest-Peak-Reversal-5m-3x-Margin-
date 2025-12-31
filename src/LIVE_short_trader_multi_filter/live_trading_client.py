from __future__ import annotations

from typing import Dict, Optional

from bybit_official_git_repo_scripts.unified_trading import HTTP

from .config import TraderConfig


class BybitLiveClient:
    """Lightweight wrapper around the official Bybit HTTP client for futures trading."""

    def __init__(self, config: TraderConfig):
        self.config = config
        self.http = HTTP(
            api_key=config.api_key,
            api_secret=config.api_secret,
            testnet=config.testnet,
            recv_window=config.recv_window,
            log_requests=config.log_requests,
        )

    def fetch_equity(self) -> Optional[float]:
        """Return available equity for the settlement coin."""
        try:
            resp = self.http.get_wallet_balance(
                accountType=self.config.account_type,
                coin=self.config.settlement_coin,
            )
            coins = resp.get("result", {}).get("list", [])
            if not coins:
                return None
            coin_info = coins[0].get("coin", [])
            for coin_entry in coin_info:
                if coin_entry.get("coin", "").upper() == self.config.settlement_coin.upper():
                    equity = coin_entry.get("equity") or coin_entry.get("walletBalance")
                    return float(equity) if equity is not None else None
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to fetch wallet balance: {exc}")
            return None

    def get_position(self) -> Optional[Dict]:
        """Fetch the current position for the configured symbol/category."""
        try:
            resp = self.http.get_positions(category=self.config.category, symbol=self.config.symbol)
            positions = resp.get("result", {}).get("list", [])
            for pos in positions:
                # Unified linear futures return size/avgPrice side in the payload
                size = float(pos.get("size", 0) or 0)
                side = pos.get("side")
                if size > 0 and side and side.lower() == "sell":
                    return pos
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to fetch positions: {exc}")
            return None

    def place_short_market(self, qty: float, tp_price: Optional[float] = None) -> Dict:
        """Submit a live market sell (short) order with optional take profit."""
        payload = {
            "category": self.config.category,
            "symbol": self.config.symbol,
            "side": "Sell",
            "orderType": "Market",
            "qty": f"{qty}",
            "timeInForce": self.config.time_in_force,
        }
        if tp_price is not None:
            payload["takeProfit"] = f"{tp_price:.6f}"
            payload["tpTriggerBy"] = "LastPrice"
        return self.http.place_order(**payload)

    def close_short_market(self, qty: float) -> Dict:
        """Submit a reduce-only market buy to close the short position."""
        payload = {
            "category": self.config.category,
            "symbol": self.config.symbol,
            "side": "Buy",
            "orderType": "Market",
            "qty": f"{qty}",
            "timeInForce": self.config.time_in_force,
            "reduceOnly": True,
        }
        return self.http.place_order(**payload)
