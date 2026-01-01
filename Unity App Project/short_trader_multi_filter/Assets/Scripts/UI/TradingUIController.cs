using System;
using System.Collections.Concurrent;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.UI;

namespace UnityApp.ShortTraderMultiFilter
{
    public class TradingUIController : MonoBehaviour
    {
        private const int LogLimit = 8000;

        private Text _statusText = null!;
        private Text _equityText = null!;
        private Text _signalText = null!;
        private Text _logText = null!;
        private AudioSource _audioSource = null!;
        private ScrollRect _scroll = null!;

        private readonly ConcurrentQueue<string> _logQueue = new();
        private readonly ConcurrentQueue<Action> _mainThreadActions = new();

        private CancellationTokenSource? _cts;
        private LiveTradingEngine? _liveEngine;

        public void BindUi(UiReferences refs)
        {
            _statusText = refs.Status;
            _equityText = refs.Equity;
            _signalText = refs.Signals;
            _logText = refs.Log;
            _audioSource = refs.Audio;
            _scroll = refs.Scroll;

            _statusText.text = "Status: Booting";
            _equityText.text = "Equity: --";
            _signalText.text = "Signals: --";
            _logText.text = string.Empty;
        }

        private void Awake()
        {
            PlatformOptimizer.ApplyQuality();
            _statusText ??= FindObjectOfType<Text>();
        }

        private void Start()
        {
            _cts = new CancellationTokenSource();
            _ = InitializeAsync(_cts.Token);
        }

        private void OnDestroy()
        {
            _cts?.Cancel();
        }

        private async Task InitializeAsync(CancellationToken token)
        {
            try
            {
                AppendLog("Booting trading UI...");

                var config = PlatformOptimizer.CreateConfig();
                var engine = new MainEngine(config);

                var optimizerResult = await Task.Run(engine.RunOptimizer, token).ConfigureAwait(false);
                var parameters = engine.CreateParameters(optimizerResult.BestRow);

                _liveEngine = new LiveTradingEngine(config, parameters, optimizerResult.Results);
                HookEvents(_liveEngine);

                AppendLog("Live trading loop starting...");
                await _liveEngine.RunAsync(token).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                AppendLog("Shutting down...");
            }
            catch (Exception ex)
            {
                EnqueueMainThread(() => _statusText.text = $"Error: {ex.Message}");
                AppendLog($"Exception: {ex}");
            }
        }

        private void HookEvents(LiveTradingEngine engine)
        {
            engine.OnEntry += alert =>
            {
                EnqueueMainThread(() =>
                {
                    _signalText.text = $"Entry @ {alert.Price:F4} | Equity {alert.Equity:F2}";
                    _statusText.text = "Status: In Position";
                    AlertAudio.Play(_audioSource);
                });
                AppendLog(alert.ToString());
            };

            engine.OnExit += alert =>
            {
                EnqueueMainThread(() =>
                {
                    _signalText.text = $"Exit ({alert.Type}) @ {alert.Price:F4} | Equity {alert.Equity:F2}";
                    _statusText.text = "Status: Flat";
                    AlertAudio.Play(_audioSource);
                });
                AppendLog(alert.ToString());
            };

            engine.OnStatus += status =>
            {
                EnqueueMainThread(() => _statusText.text = $"Status: {status}");
                AppendLog(status);
            };

            engine.OnEquity += equity => EnqueueMainThread(() => _equityText.text = $"Equity: {equity:F2} USDT");

            engine.OnError += ex => AppendLog($"Live loop error: {ex.Message}");
        }

        private void Update()
        {
            while (_mainThreadActions.TryDequeue(out var action))
            
            {
                action();
            }

            FlushLogs();
        }

        private void FlushLogs()
        {
            var updated = false;
            while (_logQueue.TryDequeue(out var line))
            {
                updated = true;
                var sb = new StringBuilder(_logText.text.Length + line.Length + 2);
                sb.AppendLine(line);
                sb.Append(_logText.text);
                var text = sb.ToString();
                if (text.Length > LogLimit)
                {
                    text = text[..Math.Min(text.Length, LogLimit)];
                }

                _logText.text = text;
            }

            if (updated)
            {
                _scroll.verticalNormalizedPosition = 0f;
            }
        }

        private void AppendLog(string message)
        {
            var timestamped = $"[{DateTime.UtcNow:HH:mm:ss}] {message}";
            _logQueue.Enqueue(timestamped);
        }

        private void EnqueueMainThread(Action action)
        {
            _mainThreadActions.Enqueue(action);
        }
    }
}
