using System;
using System.Collections.Generic;

namespace UnityApp.ShortTraderMultiFilter
{
    public static class OrderUtils
    {
        private static readonly Random Random = new();

        public static double BybitFee(double tradeValue, TraderConfig config) => tradeValue * config.BybitFee;

        public static (double? Price, string Status) SimulateOrderFill(
            string direction,
            double midPrice,
            TraderConfig config,
            int? spreadBps = null,
            int? slippageBps = null,
            double? rejectProbability = null)
        {
            var spread = (spreadBps ?? config.SpreadBps) / 10000.0;
            var slippage = (slippageBps ?? config.SlippageBps) / 10000.0;
            var rejectProb = rejectProbability ?? config.OrderRejectProbability;

            if (Random.NextDouble() < rejectProb)
            {
                return (null, "rejected");
            }

            var spreadAmount = midPrice * spread;
            var slippageAmount = midPrice * Math.Abs(NormalSample(slippage, Math.Max(slippage / 2.0, 0.00001)));

            var fillPrice = direction == "long"
                ? midPrice + spreadAmount + slippageAmount
                : midPrice - spreadAmount - slippageAmount;

            if (config.MaxFillLatencySeconds > 0)
            {
                var wait = Random.NextDouble() * config.MaxFillLatencySeconds;
                System.Threading.Thread.Sleep(TimeSpan.FromSeconds(wait));
            }

            return (fillPrice, "filled");
        }

        public static double MarkToMarket(
            double cashEquity,
            int positionSide,
            double? entryPrice,
            double quantity,
            double lastPrice,
            double marginUsed = 0.0)
        {
            var total = cashEquity + marginUsed;
            if (positionSide == 1 && entryPrice.HasValue)
            {
                total += (lastPrice - entryPrice.Value) * quantity;
            }
            else if (positionSide == -1 && entryPrice.HasValue)
            {
                total += (entryPrice.Value - lastPrice) * quantity;
            }
            return total;
        }

        public static double CalcLiquidationPriceLong(double entryPrice, int leverage) =>
            entryPrice * (1 - 1.0 / leverage);

        public static double CalcLiquidationPriceShort(double entryPrice, int leverage, TraderConfig config)
        {
            var maintenanceRate = 0.004;
            var takerFee = config.BybitFee;
            var liq = entryPrice * (1 + (1.0 / leverage) - maintenanceRate + takerFee);
            return Math.Max(liq, 0.0);
        }

        public static int AllowedLeverageForNotional(double notional, IReadOnlyList<(double Threshold, int Leverage)> tiers, int maxLeverage)
        {
            var sorted = new List<(double, int)>(tiers);
            sorted.Sort((a, b) => a.Threshold.CompareTo(b.Threshold));
            foreach (var (threshold, lev) in sorted)
            {
                if (notional <= threshold)
                {
                    return Math.Max(1, Math.Min(lev, maxLeverage));
                }
            }
            var last = sorted[^1].Leverage;
            return Math.Max(1, Math.Min(last, maxLeverage));
        }

        public static double ResolveLeverage(double marginUsed, double desiredLeverage, TraderConfig config)
        {
            var leverage = Math.Min(desiredLeverage, config.BybitMaxLeverage);
            if (marginUsed <= 0)
            {
                return 1.0;
            }

            while (true)
            {
                var notional = marginUsed * leverage;
                var allowed = AllowedLeverageForNotional(notional, config.BybitLeverageTiers, config.BybitMaxLeverage);
                if (leverage <= allowed || leverage <= 1)
                {
                    return Math.Max(1.0, leverage);
                }
                leverage = allowed;
            }
        }

        private static double NormalSample(double mean, double stdDev)
        {
            // Box-Muller transform
            var u1 = 1.0 - Random.NextDouble();
            var u2 = 1.0 - Random.NextDouble();
            var randStdNormal = Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Sin(2.0 * Math.PI * u2);
            return mean + stdDev * randStdNormal;
        }
    }
}
