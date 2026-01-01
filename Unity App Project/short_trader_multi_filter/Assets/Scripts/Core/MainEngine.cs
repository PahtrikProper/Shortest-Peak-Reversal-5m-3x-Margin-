using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace UnityApp.ShortTraderMultiFilter
{
    public class MainEngine
    {
        private readonly TraderConfig _config;
        private readonly DataClient _dataClient;
        private readonly BacktestEngine _backtestEngine;
        private readonly string _bestParamsPath;

        public MainEngine(TraderConfig? config = null, string? bestParamsPath = null)
        {
            _config = config ?? new TraderConfig();
            _dataClient = new DataClient(_config);
            _backtestEngine = new BacktestEngine(_config);
            _bestParamsPath = bestParamsPath ?? Path.Combine(Paths.DataDirectory, "best_params.json");
            Directory.CreateDirectory(Path.GetDirectoryName(_bestParamsPath)!);
        }

        public void Run()
        {
            LogConfig();
            var (bestRow, metrics, summary) = RunOptimizer();
            var parameters = CreateParameters(bestRow);

            SaveBestParams(bestRow, summary);
            PrintTrades(metrics);

            var live = new LiveTradingEngine(_config, parameters, summary);
            live.Run();
        }

        public (Dictionary<string, object> BestRow, BacktestMetrics Metrics, Dictionary<string, double> Results) RunOptimizer()
        {
            return RunBacktests();
        }

        public StrategyParams CreateParameters(Dictionary<string, object> bestRow)
        {
            return new StrategyParams(
                Convert.ToInt32(bestRow["sma_period"]),
                Convert.ToInt32(bestRow["stoch_period"]),
                _config.MacdFast,
                _config.MacdSlow,
                _config.MacdSignal,
                Convert.ToBoolean(bestRow["use_macd"]),
                Convert.ToBoolean(bestRow["use_signal"]),
                Convert.ToBoolean(bestRow["use_momentum_exit"]));
        }

        private void LogConfig()
        {
            Console.WriteLine("\n===== STRATEGY CONFIGURATION =====");
            Console.WriteLine(_config.AsLogString());
            Console.WriteLine("==================================\n");
        }

        private void SaveBestParams(Dictionary<string, object> best, Dictionary<string, double> results)
        {
            var payload = new Dictionary<string, object>
            {
                ["generated_at"] = DateTime.UtcNow.ToString("o"),
                ["symbol"] = _config.Symbol,
                ["category"] = _config.Category,
                ["agg_minutes"] = _config.AggregationMinutes,
                ["params"] = best,
                ["results"] = results
            };

            var json = JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(_bestParamsPath, json);
            Console.WriteLine($"Saved optimal parameters to {_bestParamsPath}");
        }

        private (Dictionary<string, object> BestRow, BacktestMetrics Metrics, Dictionary<string, double> Results) RunBacktests()
        {
            Console.WriteLine($"Fetching data and running optimizer on {_config.AggregationMinutes}m bars...");
            var data = _dataClient.FetchBybitBars(days: _config.BacktestDays, intervalMinutes: _config.AggregationMinutes);

            var grid = _backtestEngine.GridSearch(data);
            var best = grid.OrderByDescending(r => Convert.ToDouble(r["pnl_pct"])).First();
            var results = BacktestEngine.SummarizeResults(best, _config.StartingBalance);

            Console.WriteLine($"\n==================== BEST PARAMETERS ({_config.AggregationMinutes}m) ====================");
            foreach (var kv in best)
            {
                Console.WriteLine($"{kv.Key}: {kv.Value}");
            }
            Console.WriteLine("\n============== BEST RESULTS ==============");
            foreach (var kv in results)
            {
                Console.WriteLine($"{kv.Key}: {kv.Value}");
            }
            Console.WriteLine("==================================================================\n");

            var metrics = _backtestEngine.RunBacktest(
                data,
                CreateParameters(best),
                captureTrades: true);

            return (best, metrics, results);
        }

        private void PrintTrades(BacktestMetrics metrics)
        {
            if (metrics.Trades.Count == 0)
            {
                Console.WriteLine("\nNo trades recorded for best parameters.\n");
                return;
            }

            Console.WriteLine("\n==== TRADES (BEST PARAMS) ====");
            foreach (var trade in metrics.Trades)
            {
                Console.WriteLine(
                    $"{trade.EntryTime:u} -> {trade.ExitTime:u} | entry={trade.EntryPrice:F4} exit={trade.ExitPrice:F4} qty={trade.Quantity:F4} pnl={trade.PnlValue:F2} ({trade.PnlPct:F2}%) type={trade.ExitType}");
            }
            Console.WriteLine("====================================\n");
        }
    }
}
