using System;
using System.Collections.Generic;

namespace UnityApp.ShortTraderMultiFilter
{
    /// <summary>
    /// Configuration values used by both the backtester and live loop.
    /// </summary>
    public class TraderConfig
    {
        public string Symbol { get; set; } = "BTCUSDT";
        public string Category { get; set; } = "linear";
        public double BacktestDays { get; set; } = 0.125; // ~3 hours
        public string ContractType { get; set; } = "LinearPerpetual";
        public double StartingBalance { get; set; } = 1000.0;
        public double BybitFee { get; set; } = 0.0;
        public int AggregationMinutes { get; set; } = 3;
        public int SpreadBps { get; set; } = 0;
        public int SlippageBps { get; set; } = 0;
        public double OrderRejectProbability { get; set; } = 0.0;
        public double MaxFillLatencySeconds { get; set; } = 0.0;
        public double RiskFraction { get; set; } = 0.95;
        public double MarginRate { get; set; } = 0.10;
        public bool LogBlockedTrades { get; set; } = true;
        public int StartYear { get; set; } = 2020;
        public int StartMonth { get; set; } = 1;

        // Strategy inputs
        public int SmaPeriod { get; set; } = 50;
        public int StochPeriod { get; set; } = 14;
        public int SmoothK { get; set; } = 2;
        public int MacdFast { get; set; } = 12;
        public int MacdSlow { get; set; } = 26;
        public int MacdSignal { get; set; } = 9;
        public bool UseMacd { get; set; } = true;
        public bool UseSignal { get; set; } = true;
        public bool UseMomentumExit { get; set; } = true;

        // Ranges for sweeps
        public IReadOnlyList<int> SmaPeriodRange { get; set; } = new[] { 50 };
        public IReadOnlyList<int> StochPeriodRange { get; set; } = new[] { 14 };
        public IReadOnlyList<bool> UseMacdOptions { get; set; } = new[] { true, false };
        public IReadOnlyList<bool> UseSignalOptions { get; set; } = new[] { true, false };
        public IReadOnlyList<bool> UseMomentumExitOptions { get; set; } = new[] { true, false };

        // Live loop options
        public int LiveHistoryDays { get; set; } = 1;
        public int MinHistoryPadding { get; set; } = 200;

        // Live leverage controls (used in order simulation helpers)
        public double DesiredLeverage { get; set; } = 10;
        public int BybitMaxLeverage { get; set; } = 50;
        public double MaxRiskFraction { get; set; } = 0.95;
        public double MinNotional { get; set; } = 1.0;
        public IReadOnlyList<(double NotionalThreshold, int Leverage)> BybitLeverageTiers { get; set; } =
            new List<(double, int)>
            {
                (50000, 50),
                (200000, 25),
                (500000, 10),
            };

        public string AsLogString()
        {
            return
                $"Symbol: {Symbol} | Category: {Category}{Environment.NewLine}" +
                $"Contract type: {ContractType}{Environment.NewLine}" +
                $"Backtest window (days): {BacktestDays} (~{BacktestDays * 24:0.0}h) | Aggregation: {AggregationMinutes}m{Environment.NewLine}" +
                $"Fees: {BybitFee * 100:0.2f}% | Spread: {SpreadBps} bps | Slippage: {SlippageBps} bps{Environment.NewLine}" +
                $"Risk per entry: {RiskFraction * 100:0.1f}% equity | Margin rate: {MarginRate * 100:0.1f}% | Start date: {StartYear}-{StartMonth:00}{Environment.NewLine}" +
                "Strategy: Short-only, date-filtered, SMA + centered Stoch + optional MACD/Signal filters, fixed 0.4% TP, optional momentum exit.";
        }
    }
}
