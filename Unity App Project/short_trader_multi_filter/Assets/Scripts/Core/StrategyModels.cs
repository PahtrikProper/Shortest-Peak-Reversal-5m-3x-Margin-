using System;
using System.Collections.Generic;

namespace UnityApp.ShortTraderMultiFilter
{
    public record StrategyParams(
        int SmaPeriod,
        int StochPeriod,
        int MacdFast,
        int MacdSlow,
        int MacdSignal,
        bool UseMacd,
        bool UseSignal,
        bool UseMomentumExit);

    public record BacktestMetrics(
        double PnlPct,
        double PnlValue,
        double FinalBalance,
        double AverageWinPct,
        double AverageLossPct,
        double WinRatePct,
        double? RiskReward,
        double Sharpe,
        int Wins,
        int Losses,
        IReadOnlyList<TradeRecord> Trades);

    public class PositionState
    {
        public string? Side { get; set; }
        public double EntryPrice { get; set; }
        public double? TakeProfit { get; set; }
        public double? LiquidationPrice { get; set; }
        public double Quantity { get; set; }
        public DateTime EntryTime { get; set; }
        public double EntryFee { get; set; }
        public double TradeValue { get; set; }
        public double MarginUsed { get; set; }
        public double Leverage { get; set; }
        public string? ExitType { get; set; }
        public double? ExitTarget { get; set; }
    }

    public record Candle(
        DateTime Timestamp,
        double Open,
        double High,
        double Low,
        double Close,
        double Volume);

    public record TradeRecord(
        DateTime EntryTime,
        DateTime ExitTime,
        string Side,
        double EntryPrice,
        double ExitPrice,
        double PnlValue,
        double PnlPct,
        double Quantity,
        string ExitType);
}
