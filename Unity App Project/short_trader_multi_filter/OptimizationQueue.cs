using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace UnityApp.ShortTraderMultiFilter
{
    public record QueuedOptimization(
        string QueueId,
        string QueuedAt,
        string ReadyAt,
        double ElapsedSeconds,
        Dictionary<string, object> Payload);

    public class OptimizationQueue
    {
        private readonly string _queuePath;

        public OptimizationQueue(string? queuePath = null)
        {
            _queuePath = queuePath ?? Path.Combine(Paths.DataDirectory, "optimization_queue.json");
            Directory.CreateDirectory(Path.GetDirectoryName(_queuePath)!);
        }

        public Dictionary<string, object> Enqueue(DateTime queuedAt, DateTime readyAt, double elapsedSeconds, Dictionary<string, object> payload)
        {
            var queuedOffset = new DateTimeOffset(queuedAt.ToUniversalTime());
            var readyOffset = new DateTimeOffset(readyAt.ToUniversalTime());
            var entry = new QueuedOptimization(
                queuedOffset.ToUnixTimeSeconds().ToString(),
                queuedOffset.ToString("o"),
                readyOffset.ToString("o"),
                Math.Round(elapsedSeconds, 3),
                payload);

            var existing = LoadExisting();
            existing.Add(entry);
            Persist(existing);

            return new Dictionary<string, object>
            {
                ["queue_id"] = entry.QueueId,
                ["queued_at"] = entry.QueuedAt,
                ["ready_at"] = entry.ReadyAt,
                ["elapsed_seconds"] = entry.ElapsedSeconds,
                ["payload"] = entry.Payload
            };
        }

        private List<QueuedOptimization> LoadExisting()
        {
            if (!File.Exists(_queuePath))
            {
                return new List<QueuedOptimization>();
            }

            try
            {
                var content = File.ReadAllText(_queuePath);
                var data = JsonSerializer.Deserialize<List<QueuedOptimization>>(content);
                return data ?? new List<QueuedOptimization>();
            }
            catch
            {
                return new List<QueuedOptimization>();
            }
        }

        private void Persist(List<QueuedOptimization> entries)
        {
            var json = JsonSerializer.Serialize(entries, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(_queuePath, json);
        }
    }
}
