using System;
using System.Collections.Generic;
using System.IO;

namespace Lunifier.Windows.Core
{
    public static class AppLogger
    {
        public const string LevelNone = "none";
        public const string LevelNormal = "normal";
        public const string LevelDebug = "debug";

        private static string _currentLevel = LevelNormal;
        private static readonly object _lock = new();

        public static event Action<string>? LogReceived;

        public static void SetLogLevel(string? level)
        {
            lock (_lock)
            {
                var lvl = (level ?? LevelNormal).Trim().ToLowerInvariant();
                _currentLevel = lvl switch
                {
                    "none" or "off" or "disabled" or "silent" => LevelNone,
                    "debug" or "verbose" or "trace" => LevelDebug,
                    _ => LevelNormal
                };
            }
        }

        public static string GetLogLevel()
        {
            lock (_lock)
            {
                return _currentLevel;
            }
        }

        public static bool IsDebugEnabled()
        {
            lock (_lock)
            {
                return _currentLevel == LevelDebug;
            }
        }

        public static void Log(string tag, string message, string level = LevelNormal)
        {
            string curLevel;
            lock (_lock)
            {
                curLevel = _currentLevel;
            }

            if (curLevel == LevelNone)
                return;

            var msgLevel = (level ?? LevelNormal).ToLowerInvariant();
            if (curLevel == LevelNormal && msgLevel == LevelDebug)
                return;

            var now = DateTime.Now;
            var ts = now.ToString("yyyy-MM-dd HH:mm:ss") + $".{now.Millisecond:D3}";
            var prefix = msgLevel == LevelDebug ? $"[{ts}] [DEBUG] [{tag}]" : $"[{ts}] [{tag}]";

            var lines = (message ?? string.Empty).Replace("\r\n", "\n").Split('\n');
            var formatted = prefix + " " + (lines.Length > 0 ? lines[0] : "");

            if (lines.Length > 1)
            {
                var indent = new string(' ', prefix.Length) + "   ";
                for (int i = 1; i < lines.Length; i++)
                {
                    formatted += "\n" + indent + lines[i];
                }
            }

            lock (_lock)
            {
                Console.WriteLine(formatted);
            }

            try
            {
                LogReceived?.Invoke(formatted);
            }
            catch
            {
                // UI dispatch errors shouldn't crash logging
            }
        }

        public static void LogDebug(string tag, string message)
        {
            Log(tag, message, LevelDebug);
        }
    }
}
