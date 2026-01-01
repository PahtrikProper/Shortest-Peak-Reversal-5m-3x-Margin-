using System;

namespace UnityApp.ShortTraderMultiFilter
{
    /// <summary>
    /// Console entry point for running the optimizer + live paper loop directly from Unity's C# environment.
    /// </summary>
    public static class StartRunner
    {
        public static void Run()
        {
            Console.Write("Enter USDT pair symbol (e.g., BTCUSDT): ");
            var symbol = Console.ReadLine()?.Trim().ToUpperInvariant() ?? "BTCUSDT";
            if (!symbol.EndsWith("USDT", StringComparison.OrdinalIgnoreCase))
            {
                symbol += "USDT";
            }

            var config = new TraderConfig { Symbol = string.IsNullOrWhiteSpace(symbol) ? "BTCUSDT" : symbol };
            var engine = new MainEngine(config);
            engine.Run();
        }
    }
}
