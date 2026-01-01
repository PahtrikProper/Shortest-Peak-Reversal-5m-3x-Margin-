using System;
using System.IO;

namespace UnityApp.ShortTraderMultiFilter
{
    /// <summary>
    /// Simple helper for resolving repository-relative paths in the Unity context.
    /// </summary>
    public static class Paths
    {
        public static readonly string RepositoryRoot;
        public static readonly string DataDirectory;

        static Paths()
        {
            var current = Directory.GetCurrentDirectory();
            RepositoryRoot = current;

            DataDirectory = Path.Combine(RepositoryRoot, "data", "multi_filter");
            Directory.CreateDirectory(DataDirectory);
        }
    }
}
