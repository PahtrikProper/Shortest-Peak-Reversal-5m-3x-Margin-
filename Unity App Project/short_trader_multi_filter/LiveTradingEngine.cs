using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;

namespace UnityApp.ShortTraderMultiFilter
{
    /// <summary>
    /// Lightweight live loop that reuses the indicator logic from the backtester for paper trading.
    /// </summary>
    public class LiveTradingEngine
    {
        private readonly TraderConfig _config;
        private readonly StrategyParams _params;
        private readonly Dictionary<string, double> _results;
        private readonly DataClient _dataClient;
        private PositionState? _position;
        private double _equity;

        public LiveTradingEngine(TraderConfig config, StrategyParams parameters, Dictionary<string, double> results)
        {
            _config = config;
            _params = parameters;
            _results = results;
            _dataClient = new DataClient(config);
            _equity = config.StartingBalance;
        }

        public void Run(CancellationToken? cancellation = null)
        {
            Console.WriteLine("\n--- Live Short Trader (multi-filter) ---\n");
            Console.WriteLine($"Last optimizer summary: {string.Join(", ", _results.Select(kv => $"{kv.Key}={kv.Value}"))}");

            while (cancellation?.IsCancellationRequested != true)
            {
                try
                {
                    var data = PrepareDataFrame();
                    MaybeExit(data);
                    if (ShouldEnter(data))
                    {
                        Enter(data.Last());
                    }
                    LogStatus(data.Last());
                    Thread.Sleep(TimeSpan.FromMinutes(_config.AggregationMinutes));
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Exception in live loop: {ex}");
                    Thread.Sleep(TimeSpan.FromSeconds(2));
                }
            }
        }

        private List<Candle> PrepareDataFrame()
        {
            var bars = _dataClient.FetchBybitBars(days: _config.LiveHistoryDays, intervalMinutes: _config.AggregationMinutes);
            var ordered = bars.OrderBy(b => b.Timestamp).ToList();
            return ordered;
        }

        private bool ShouldEnter(IReadOnlyList<Candle> data)
        {
            if (_position != null || data.Count < _config.MinHistoryPadding)
            {
                return false;
            }

            var engine = new BacktestEngine(_config);
            var metrics = engine.RunBacktest(data, _params, false);

            // Use the latest bar to evaluate entry conditions
            var last = data[^1];
            var prev = data[^2];
            var lowsOk = data[^3].Low <= prev.Low && last.Low < prev.Low;
            return metrics.Trades.Count >= 0 && lowsOk; // keep conditions loose for live paper loop
        }

        private void Enter(Candle candle)
        {
            var riskFraction = _config.RiskFraction;
            var marginRate = _config.MarginRate;
            var positionValue = (_equity * riskFraction) / marginRate;
            var qty = positionValue / candle.Close;
            var marginUsed = _equity * riskFraction;
            if (marginUsed <= 0 || qty <= 0)
            {
                return;
            }

            _equity -= marginUsed;
            var tp = candle.Close * (1 - 0.004);
            var liqPrice = candle.Close * (1 + marginRate);
            _position = new PositionState
            {
                Side = "short",
                EntryPrice = candle.Close,
                TakeProfit = tp,
                LiquidationPrice = liqPrice,
                Quantity = qty,
                EntryTime = candle.Timestamp,
                MarginUsed = marginUsed
            };

            Console.WriteLine($"ENTER SHORT @ {candle.Close:F6} qty={qty:F4} TP={tp:F6} LIQ={liqPrice:F6} Equity={_equity:F2}");
        }

        private void MaybeExit(IReadOnlyList<Candle> data)
        {
            if (_position == null)
            {
                return;
            }

            var last = data[^1];
            var tpHit = last.Low <= (_position.TakeProfit ?? 0);
            var marginCall = last.High >= (_position.LiquidationPrice ?? double.MaxValue);

            double? exitPrice = null;
            var exitType = "hold";

            if (marginCall)
            {
                exitPrice = _position.LiquidationPrice;
                exitType = "margin_call";
            }
            else if (tpHit)
            {
                exitPrice = _position.TakeProfit;
                exitType = "tp";
            }

            if (!exitPrice.HasValue)
            {
                return;
            }

            var gross = (_position.EntryPrice - exitPrice.Value) * _position.Quantity;
            _equity += _position.MarginUsed + gross;
            Console.WriteLine($"EXIT @ {exitPrice.Value:F6} type={exitType} pnl={gross:F4} equity={_equity:F2}");
            _position = null;
        }

        private void LogStatus(Candle candle)
        {
            var now = candle.Timestamp.ToString("yyyy-MM-dd HH:mm");
            if (_position != null)
            {
                Console.WriteLine($"{now} | STATUS | pos=SHORT qty={_position.Quantity:F4} entry={_position.EntryPrice:F6} tp={_position.TakeProfit:F6} liq={_position.LiquidationPrice:F6} last={candle.Close:F6} equity={_equity:F2}");
            }
            else
            {
                Console.WriteLine($"{now} | STATUS | flat | last={candle.Close:F6} equity={_equity:F2}");
            }
        }
    }
}
