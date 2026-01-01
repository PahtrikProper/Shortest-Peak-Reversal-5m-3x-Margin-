using System;
using System.IO;
#if UNITY_2021_1_OR_NEWER
using UnityEngine;
#endif

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
#if UNITY_2021_1_OR_NEWER
            RepositoryRoot = Application.persistentDataPath ?? Directory.GetCurrentDirectory();
#else
            RepositoryRoot = Directory.GetCurrentDirectory();
#endif

            DataDirectory = Path.Combine(RepositoryRoot, "data", "multi_filter");
            Directory.CreateDirectory(DataDirectory);
        }
    }
}
