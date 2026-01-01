using System;
using System.Collections.Generic;

namespace UnityApp.ShortTraderMultiFilter
{
    public class SellOrderEngine
    {
        private readonly TraderConfig _config;

        public SellOrderEngine(TraderConfig config)
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
            double availableUsdt,
            bool useRawMidPrice = false)
        {
            (double? price, string status) fill;
            if (useRawMidPrice)
            {
                fill = (candle.Close, "filled");
            }
            else
            {
                fill = OrderUtils.SimulateOrderFill("short", candle.Close, _config);
            }

            if (fill.Status == "rejected" || !fill.Price.HasValue)
            {
                return (null, fill.Status, 0, 0, 0);
            }

            if (availableUsdt <= 0 || _config.RiskFraction <= 0)
            {
                return (null, "insufficient_funds", 0, 0, 0);
            }

            var marginUsed = availableUsdt * Math.Min(Math.Max(_config.RiskFraction, 0.0), _config.MaxRiskFraction);
            var leverageUsed = OrderUtils.ResolveLeverage(marginUsed, _config.DesiredLeverage, _config);
            var tradeValue = marginUsed * leverageUsed;
            if (tradeValue < _config.MinNotional)
            {
                return (null, "min_notional_not_met", 0, 0, 0);
            }

            var qty = tradeValue / fill.Price.Value;
            var entryFee = OrderUtils.BybitFee(tradeValue, _config);
            var liqPrice = OrderUtils.CalcLiquidationPriceShort(fill.Price.Value, (int)leverageUsed, _config);

            var position = new PositionState
            {
                Side = "short",
                EntryPrice = fill.Price.Value,
                LiquidationPrice = liqPrice,
                Quantity = qty,
                EntryTime = candle.Timestamp,
                EntryFee = entryFee,
                TradeValue = tradeValue,
                MarginUsed = marginUsed,
                Leverage = leverageUsed
            };
            return (position, fill.Status, entryFee, tradeValue, marginUsed);
        }
    }
}
