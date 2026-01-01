using System;
using System.Collections.Generic;
using System.Linq;

namespace UnityApp.ShortTraderMultiFilter
{
    public class BacktestEngine
    {
        private readonly TraderConfig _config;

        public BacktestEngine(TraderConfig config)
        {
            _config = config;
        }

        public BacktestMetrics RunBacktest(IReadOnlyList<Candle> candles, StrategyParams parameters, bool captureTrades = false)
        {
            var ordered = candles.OrderBy(c => c.Timestamp).ToList();
            var closes = ordered.Select(c => c.Close).ToList();
            var highs = ordered.Select(c => c.High).ToList();
            var lows = ordered.Select(c => c.Low).ToList();

            var sma = RollingMean(closes, parameters.SmaPeriod);
            var lowestLow = RollingMin(lows, parameters.StochPeriod);
            var highestHigh = RollingMax(highs, parameters.StochPeriod);

            var rawStoch = new List<double?>();
            for (var i = 0; i < ordered.Count; i++)
            {
                if (!lowestLow[i].HasValue || !highestHigh[i].HasValue || Math.Abs(highestHigh[i]!.Value - lowestLow[i]!.Value) < 1e-12)
                {
                    rawStoch.Add(0);
                }
                else
                {
                    var value = 100 * (closes[i] - lowestLow[i]!.Value) / (highestHigh[i]!.Value - lowestLow[i]!.Value);
                    rawStoch.Add(value);
                }
            }

            var smoothedK = RollingMean(rawStoch, _config.SmoothK).Select(x => x.HasValue ? x - 50 : (double?)null).ToList();
            var emaFast = ExponentialMovingAverage(closes, parameters.MacdFast);
            var emaSlow = ExponentialMovingAverage(closes, parameters.MacdSlow);
            var macd = emaFast.Zip(emaSlow, (fast, slow) => fast - slow).ToList();
            var signal = ExponentialMovingAverage(macd, parameters.MacdSignal);

            var balance = _config.StartingBalance;
            var equityCurve = new List<double>();
            var trades = new List<TradeRecord>();
            PositionState? position = null;
            var wins = 0;
            var losses = 0;
            var winSizes = new List<double>();
            var lossSizes = new List<double>();

            var warmup = Math.Max(parameters.SmaPeriod, Math.Max(parameters.StochPeriod, Math.Max(parameters.MacdSlow, parameters.MacdSignal))) + 2;
            for (var i = warmup; i < ordered.Count; i++)
            {
                var candle = ordered[i];
                var close = candle.Close;

                var inDate = candle.Timestamp.Year > _config.StartYear ||
                             (candle.Timestamp.Year == _config.StartYear && candle.Timestamp.Month >= _config.StartMonth);

                if (position == null)
                {
                    if (!inDate)
                    {
                        equityCurve.Add(balance);
                        continue;
                    }

                    var lowsOk = ordered[i - 2].Low <= ordered[i - 1].Low && candle.Low < ordered[i - 1].Low;
                    var smaOk = sma[i].HasValue && sma[i - 1].HasValue && sma[i] < sma[i - 1];
                    var macdOk = !parameters.UseMacd || (macd[i] < macd[i - 1]);
                    var signalOk = !parameters.UseSignal || (signal[i].HasValue && signal[i - 1].HasValue && signal[i] < signal[i - 1]);

                    if (lowsOk && smaOk && macdOk && signalOk)
                    {
                        var riskFraction = _config.RiskFraction;
                        var marginRate = _config.MarginRate;
                        var positionValue = (balance * riskFraction) / marginRate;
                        var qty = positionValue / close;
                        var marginUsed = balance * riskFraction;
                        if (marginUsed <= 0 || qty <= 0)
                        {
                            equityCurve.Add(balance);
                            continue;
                        }

                        balance -= marginUsed;
                        var tp = close * (1 - 0.004);
                        position = new PositionState
                        {
                            Side = "short",
                            EntryPrice = close,
                            TakeProfit = tp,
                            Quantity = qty,
                            EntryTime = candle.Timestamp,
                            MarginUsed = marginUsed,
                        };

                        equityCurve.Add(balance + marginUsed);
                        continue;
                    }
                }
                else
                {
                    var tpHit = position.TakeProfit.HasValue && candle.Low <= position.TakeProfit.Value;
                    var momentumExit = parameters.UseMomentumExit &&
                                       smoothedK[i].HasValue && smoothedK[i - 1].HasValue &&
                                       smoothedK[i] > smoothedK[i - 1];

                    double? exitPrice = null;
                    var exitType = "momentum";
                    if (tpHit)
                    {
                        exitPrice = position.TakeProfit;
                        exitType = "tp";
                    }
                    else if (momentumExit)
                    {
                        exitPrice = close;
                    }

                    if (exitPrice.HasValue)
                    {
                        var gross = (position.EntryPrice - exitPrice.Value) * position.Quantity;
                        balance += position.MarginUsed + gross;
                        var pnlPct = (gross / _config.StartingBalance) * 100;
                        if (gross > 0)
                        {
                            wins++;
                            winSizes.Add(pnlPct);
                        }
                        else
                        {
                            losses++;
                            lossSizes.Add(pnlPct);
                        }

                        if (captureTrades)
                        {
                            trades.Add(new TradeRecord(
                                position.EntryTime,
                                candle.Timestamp,
                                "SHORT",
                                position.EntryPrice,
                                exitPrice.Value,
                                gross,
                                pnlPct,
                                position.Quantity,
                                exitType));
                        }

                        position = null;
                    }
                }

                equityCurve.Add(balance + (position?.MarginUsed ?? 0));
            }

            if (position != null)
            {
                var finalClose = ordered[^1].Close;
                var gross = (position.EntryPrice - finalClose) * position.Quantity;
                balance += position.MarginUsed + gross;
                var pnlPct = (gross / _config.StartingBalance) * 100;
                if (gross > 0)
                {
                    wins++;
                    winSizes.Add(pnlPct);
                }
                else
                {
                    losses++;
                    lossSizes.Add(pnlPct);
                }
                if (captureTrades)
                {
                    trades.Add(new TradeRecord(
                        position.EntryTime,
                        ordered[^1].Timestamp,
                        "SHORT",
                        position.EntryPrice,
                        finalClose,
                        gross,
                        pnlPct,
                        position.Quantity,
                        "final_close"));
                }
                equityCurve.Add(balance);
            }

            if (equityCurve.Count == 0)
            {
                return new BacktestMetrics(0, 0, _config.StartingBalance, 0, 0, 0, null, 0, 0, 0, trades);
            }

            var finalBalance = equityCurve[^1];
            var pnlValue = finalBalance - _config.StartingBalance;
            var pnlPctTotal = (pnlValue / _config.StartingBalance) * 100;
            var avgWin = winSizes.Count > 0 ? winSizes.Average() : 0;
            var avgLoss = lossSizes.Count > 0 ? lossSizes.Average() : 0;
            var winRate = (wins + losses) > 0 ? (double)wins / (wins + losses) * 100 : 0;
            double? rr = avgLoss != 0 ? avgWin / Math.Abs(avgLoss) : null;

            var returns = new List<double>();
            for (var i = 1; i < equityCurve.Count; i++)
            {
                var prev = equityCurve[i - 1];
                var curr = equityCurve[i];
                if (prev != 0)
                {
                    returns.Add((curr - prev) / prev);
                }
            }

            var meanReturn = returns.Count > 0 ? returns.Average() : 0;
            var stdReturn = returns.Count > 1 ? StdDev(returns) : 0;
            var sharpe = stdReturn != 0 ? meanReturn / stdReturn * Math.Sqrt(365 * 24 * 60 / _config.AggregationMinutes) : 0;

            return new BacktestMetrics(pnlPctTotal, pnlValue, finalBalance, avgWin, avgLoss, winRate, rr, sharpe, wins, losses, trades);
        }

        public IReadOnlyList<Dictionary<string, object>> GridSearch(IReadOnlyList<Candle> candles)
        {
            var results = new List<Dictionary<string, object>>();

            foreach (var sma in _config.SmaPeriodRange)
            {
                foreach (var stoch in _config.StochPeriodRange)
                {
                    foreach (var useMacd in _config.UseMacdOptions)
                    {
                        foreach (var useSignal in _config.UseSignalOptions)
                        {
                            foreach (var useMom in _config.UseMomentumExitOptions)
                            {
                                var parameters = new StrategyParams(
                                    sma,
                                    stoch,
                                    _config.MacdFast,
                                    _config.MacdSlow,
                                    _config.MacdSignal,
                                    useMacd,
                                    useSignal,
                                    useMom);

                                var metrics = RunBacktest(candles, parameters, false);
                                var row = new Dictionary<string, object>
                                {
                                    ["sma_period"] = sma,
                                    ["stoch_period"] = stoch,
                                    ["macd_fast"] = _config.MacdFast,
                                    ["macd_slow"] = _config.MacdSlow,
                                    ["macd_signal"] = _config.MacdSignal,
                                    ["use_macd"] = useMacd,
                                    ["use_signal"] = useSignal,
                                    ["use_momentum_exit"] = useMom,
                                    ["pnl_pct"] = metrics.PnlPct,
                                    ["pnl_value"] = metrics.PnlValue,
                                    ["final_balance"] = metrics.FinalBalance,
                                    ["wins"] = metrics.Wins,
                                    ["losses"] = metrics.Losses,
                                    ["avg_win"] = metrics.AverageWinPct,
                                    ["avg_loss"] = metrics.AverageLossPct,
                                    ["win_rate"] = metrics.WinRatePct,
                                    ["rr_ratio"] = metrics.RiskReward,
                                    ["sharpe"] = metrics.Sharpe
                                };
                                results.Add(row);
                            }
                        }
                    }
                }
            }

            return results;
        }

        public static Dictionary<string, double> SummarizeResults(Dictionary<string, object> bestRow, double startingBalance)
        {
            var wins = Convert.ToInt32(bestRow["wins"]);
            var losses = Convert.ToInt32(bestRow["losses"]);
            var totalTrades = wins + losses;
            var finalBalance = Convert.ToDouble(bestRow["final_balance"]);
            var totalPnl = Convert.ToDouble(bestRow["pnl_value"]);
            var avgWin = Convert.ToDouble(bestRow["avg_win"]);
            var avgLoss = Convert.ToDouble(bestRow["avg_loss"]);

            var winRate = totalTrades > 0 ? (double)wins / totalTrades * 100 : 0;

            return new Dictionary<string, double>
            {
                ["Total Trades"] = totalTrades,
                ["Wins"] = wins,
                ["Losses"] = losses,
                ["Win Rate %"] = Math.Round(winRate, 2),
                ["Total PnL"] = Math.Round(totalPnl, 2),
                ["Final Balance"] = Math.Round(finalBalance, 2),
                ["Average Win"] = Math.Round(avgWin, 2),
                ["Average Loss"] = Math.Round(avgLoss, 2)
            };
        }

        private static List<double?> RollingMean(IReadOnlyList<double> values, int period)
        {
            var result = new List<double?>(new double?[values.Count]);
            if (period <= 0)
            {
                return result;
            }
            double sum = 0;
            for (var i = 0; i < values.Count; i++)
            {
                sum += values[i];
                if (i >= period)
                {
                    sum -= values[i - period];
                }
                if (i >= period - 1)
                {
                    result[i] = sum / period;
                }
            }
            return result;
        }

        private static List<double?> RollingMean(IReadOnlyList<double?> values, int period)
        {
            var result = new List<double?>(new double?[values.Count]);
            if (period <= 0)
            {
                return result;
            }

            var window = new Queue<double>();
            for (var i = 0; i < values.Count; i++)
            {
                var val = values[i];
                if (val.HasValue)
                {
                    window.Enqueue(val.Value);
                }

                if (window.Count > period)
                {
                    window.Dequeue();
                }

                if (window.Count == period)
                {
                    result[i] = window.Average();
                }
            }

            return result;
        }

        private static List<double?> RollingMin(IReadOnlyList<double> values, int period)
        {
            var result = new List<double?>(new double?[values.Count]);
            if (period <= 0)
            {
                return result;
            }
            for (var i = 0; i < values.Count; i++)
            {
                if (i >= period - 1)
                {
                    var window = values.Skip(i - period + 1).Take(period);
                    result[i] = window.Min();
                }
            }
            return result;
        }

        private static List<double?> RollingMax(IReadOnlyList<double> values, int period)
        {
            var result = new List<double?>(new double?[values.Count]);
            if (period <= 0)
            {
                return result;
            }
            for (var i = 0; i < values.Count; i++)
            {
                if (i >= period - 1)
                {
                    var window = values.Skip(i - period + 1).Take(period);
                    result[i] = window.Max();
                }
            }
            return result;
        }

        private static List<double> ExponentialMovingAverage(IReadOnlyList<double> values, int period)
        {
            var result = new List<double>(new double[values.Count]);
            if (period <= 0 || values.Count == 0)
            {
                return result;
            }

            var multiplier = 2.0 / (period + 1);
            result[0] = values[0];
            for (var i = 1; i < values.Count; i++)
            {
                result[i] = ((values[i] - result[i - 1]) * multiplier) + result[i - 1];
            }
            return result;
        }

        private static double StdDev(IReadOnlyList<double> values)
        {
            var mean = values.Average();
            var variance = values.Select(v => Math.Pow(v - mean, 2)).Average();
            return Math.Sqrt(variance);
        }
    }
}
