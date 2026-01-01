using System;
using System.Collections.Generic;

namespace UnityApp.ShortTraderMultiFilter
{
    public class BuyOrderEngine
    {
        private readonly TraderConfig _config;

        public BuyOrderEngine(TraderConfig config)
        {
            _config = config;
        }

        public bool ShouldEnter(Dictionary<string, object> row, string? positionSide)
        {
            if (!string.IsNullOrEmpty(positionSide))
            {
                return false;
            }

            return row.TryGetValue("entry_signal", out var signalObj) && Convert.ToBoolean(signalObj)
                && (!row.TryGetValue("tradable", out var tradableObj) || Convert.ToBoolean(tradableObj));
        }

        public (PositionState? Position, string Status, double EntryFee, double TradeValue, double MarginUsed) OpenPosition(
            Candle candle,
            double availableUsdt)
        {
            var (entryPrice, status) = OrderUtils.SimulateOrderFill("long", candle.Close, _config);
            if (status == "rejected" || !entryPrice.HasValue)
            {
                return (null, status, 0, 0, 0);
            }

            if (availableUsdt <= 0 || _config.RiskFraction <= 0)
            {
                return (null, "insufficient_funds", 0, 0, 0);
            }

            var marginUsed = availableUsdt * _config.RiskFraction;
            var leverageUsed = OrderUtils.ResolveLeverage(marginUsed, _config.DesiredLeverage, _config);
            var tradeValue = marginUsed * leverageUsed;
            if (tradeValue < _config.MinNotional)
            {
                return (null, "min_notional_not_met", 0, 0, 0);
            }

            var qty = tradeValue / entryPrice.Value;
            var entryFee = OrderUtils.BybitFee(tradeValue, _config);
            var liqPrice = OrderUtils.CalcLiquidationPriceLong(entryPrice.Value, (int)leverageUsed);

            var position = new PositionState
            {
                Side = "long",
                EntryPrice = entryPrice.Value,
                LiquidationPrice = liqPrice,
                Quantity = qty,
                EntryTime = candle.Timestamp,
                EntryFee = entryFee,
                TradeValue = tradeValue,
                MarginUsed = marginUsed,
                Leverage = leverageUsed
            };
            return (position, status, entryFee, tradeValue, marginUsed);
        }
    }
}
