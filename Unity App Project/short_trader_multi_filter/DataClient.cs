using System;
using System.Collections.Generic;
using System.Globalization;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

namespace UnityApp.ShortTraderMultiFilter
{
    public class DataClient
    {
        private static readonly HttpClient Http = new HttpClient();
        private readonly TraderConfig _config;

        public DataClient(TraderConfig config)
        {
            _config = config;
        }

        public List<Candle> FetchBybitBars(
            string? symbol = null,
            string? category = null,
            double? days = null,
            int? intervalMinutes = null,
            int maxRetries = 5,
            double backoffSeconds = 1.5)
        {
            var sym = symbol ?? _config.Symbol;
            var cat = category ?? _config.Category;
            var window = days ?? _config.BacktestDays;
            var interval = intervalMinutes ?? _config.AggregationMinutes;

            var end = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            var start = end - (long)(window * 24 * 60 * 60);
            var candles = new List<Candle>();

            while (start < end)
            {
                var url = $"https://api.bybit.com/v5/market/kline?category={cat}&symbol={sym}&interval={interval}&start={start * 1000}&limit=1000";
                var attempt = 0;
                JsonElement root;

                while (true)
                {
                    var resp = Http.GetAsync(url).GetAwaiter().GetResult();
                    if (!resp.IsSuccessStatusCode)
                    {
                        throw new InvalidOperationException($"Bybit API request failed ({resp.StatusCode}): {resp.ReasonPhrase}");
                    }

                    var content = resp.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    root = JsonDocument.Parse(content).RootElement;
                    var retCode = root.TryGetProperty("retCode", out var codeEl) ? codeEl.GetInt32() : -1;
                    if (retCode == 0)
                    {
                        break;
                    }

                    if (retCode == 10006 && attempt < maxRetries)
                    {
                        attempt++;
                        Task.Delay(TimeSpan.FromSeconds(backoffSeconds * attempt)).Wait();
                        continue;
                    }

                    var msg = root.TryGetProperty("retMsg", out var msgEl) ? msgEl.GetString() : "unknown error";
                    throw new InvalidOperationException($"Bybit API returned error code {retCode}: {msg}");
                }

                if (!root.TryGetProperty("result", out var result) || !result.TryGetProperty("list", out var rows) || rows.ValueKind != JsonValueKind.Array)
                {
                    break;
                }

                var chunk = new List<Candle>();
                foreach (var row in rows.EnumerateArray())
                {
                    if (row.ValueKind != JsonValueKind.Array || row.GetArrayLength() < 6)
                    {
                        continue;
                    }

                    var timestamp = long.Parse(row[0].GetString() ?? "0", CultureInfo.InvariantCulture);
                    var open = double.Parse(row[1].GetString() ?? "0", CultureInfo.InvariantCulture);
                    var high = double.Parse(row[2].GetString() ?? "0", CultureInfo.InvariantCulture);
                    var low = double.Parse(row[3].GetString() ?? "0", CultureInfo.InvariantCulture);
                    var close = double.Parse(row[4].GetString() ?? "0", CultureInfo.InvariantCulture);
                    var volume = double.Parse(row[5].GetString() ?? "0", CultureInfo.InvariantCulture);

                    var dt = DateTimeOffset.FromUnixTimeMilliseconds(timestamp).UtcDateTime;
                    chunk.Add(new Candle(dt, open, high, low, close, volume));
                }

                if (chunk.Count == 0)
                {
                    break;
                }

                chunk.Sort((a, b) => a.Timestamp.CompareTo(b.Timestamp));
                candles.AddRange(chunk);

                var last = chunk[^1].Timestamp;
                start = new DateTimeOffset(last).ToUnixTimeSeconds() + interval * 60;
            }

            if (candles.Count == 0)
            {
                throw new InvalidOperationException("No candle data received from Bybit.");
            }

            candles.Sort((a, b) => a.Timestamp.CompareTo(b.Timestamp));
            return candles;
        }
    }
}
