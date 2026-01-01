using UnityEngine;

namespace UnityApp.ShortTraderMultiFilter
{
    public static class PlatformOptimizer
    {
        public static void ApplyQuality()
        {
            Application.targetFrameRate = Application.platform == RuntimePlatform.Android ? 60 : 90;
            QualitySettings.vSyncCount = 1;
            Screen.sleepTimeout = SleepTimeout.SystemSetting;
        }

        public static TraderConfig CreateConfig()
        {
            var config = new TraderConfig();

            if (Application.platform == RuntimePlatform.Android)
            {
                config.BacktestDays = 0.05; // keep memory footprint small on mobile
                config.LiveHistoryDays = 0.5;
                config.MinHistoryPadding = 120;
                config.RiskFraction = 0.5;
                config.MarginRate = 0.1;
            }
            else
            {
                config.BacktestDays = 0.25;
                config.LiveHistoryDays = 1;
                config.MinHistoryPadding = 200;
                config.RiskFraction = 0.75;
            }

            return config;
        }
    }
}
