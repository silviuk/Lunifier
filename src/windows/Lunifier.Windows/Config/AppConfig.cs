using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using Lunifier.Windows.Core;

namespace Lunifier.Windows.Config
{
    public class MonitorEdgeConfig
    {
        [JsonPropertyName("enabled")]
        public bool Enabled { get; set; } = true;

        [JsonPropertyName("edges")]
        public Dictionary<string, int?> Edges { get; set; } = new()
        {
            { "left", null },
            { "right", null },
            { "top", null },
            { "bottom", null }
        };
    }

    public class AppConfig
    {
        private static readonly string DefaultConfigPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "Lunifier",
            "config.json"
        );

        private static readonly string LegacyConfigPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "LogiFlowBT",
            "config.json"
        );

        [JsonPropertyName("host_name")]
        public string HostName { get; set; } = "Host";

        [JsonPropertyName("my_channel")]
        public int MyChannel { get; set; } = 1;

        [JsonPropertyName("target_channel")]
        public int TargetChannel { get; set; } = 2;

        [JsonPropertyName("trigger_edge")]
        public string TriggerEdge { get; set; } = "right";

        [JsonPropertyName("entry_edge")]
        public string EntryEdge { get; set; } = "left";

        [JsonPropertyName("hold_delay_ms")]
        public int HoldDelayMs { get; set; } = 250;

        [JsonPropertyName("cooldown_ms")]
        public int CooldownMs { get; set; } = 2500;

        [JsonPropertyName("border_active_zone_pct")]
        public int BorderActiveZonePct { get; set; } = 50;

        [JsonPropertyName("knock_enabled")]
        public bool KnockEnabled { get; set; } = false;

        [JsonPropertyName("knock_timeout_ms")]
        public int KnockTimeoutMs { get; set; } = 1000;

        [JsonPropertyName("edge_channels")]
        public Dictionary<string, int?> EdgeChannels { get; set; } = new()
        {
            { "left", null },
            { "right", 2 },
            { "top", null },
            { "bottom", null }
        };

        [JsonPropertyName("monitor_configs")]
        public Dictionary<string, MonitorEdgeConfig> MonitorConfigs { get; set; } = new();

        [JsonPropertyName("devices")]
        public List<string> Devices { get; set; } = new()
        {
            "MX Keys",
            "Keys",
            "M370",
            "POP",
            "Triathlon",
            "M720",
            "MX Master",
            "MX Anywhere",
            "Mouse"
        };

        [JsonPropertyName("device_feature_indices")]
        public Dictionary<string, int> DeviceFeatureIndices { get; set; } = new();

        [JsonPropertyName("use_solaar_on_linux")]
        public bool UseSolaarOnLinux { get; set; } = true;

        [JsonPropertyName("switch_backend")]
        public string SwitchBackend { get; set; } = "auto";

        [JsonPropertyName("connection_support")]
        public string ConnectionSupport { get; set; } = "both";

        [JsonPropertyName("bt_p2p_enabled")]
        public bool BtP2pEnabled { get; set; } = false;

        [JsonPropertyName("bt_peer_address")]
        public string BtPeerAddress { get; set; } = string.Empty;

        [JsonPropertyName("bt_rfcomm_port")]
        public int BtRfcommPort { get; set; } = 4;

        [JsonPropertyName("sync_cursor_position")]
        public bool SyncCursorPosition { get; set; } = true;

        [JsonPropertyName("sync_clipboard")]
        public bool SyncClipboard { get; set; } = false;

        [JsonPropertyName("log_level")]
        public string LogLevel { get; set; } = "normal";

        public MonitorEdgeConfig GetMonitorConfig(string monitorId)
        {
            var mid = monitorId ?? "0";
            if (MonitorConfigs != null && MonitorConfigs.TryGetValue(mid, out var cfg))
            {
                return cfg;
            }

            // Fallback for primary monitor 0
            if (mid == "0")
            {
                return new MonitorEdgeConfig
                {
                    Enabled = true,
                    Edges = new Dictionary<string, int?>(EdgeChannels ?? new()
                    {
                        { "left", null },
                        { "right", 2 },
                        { "top", null },
                        { "bottom", null }
                    })
                };
            }

            return new MonitorEdgeConfig
            {
                Enabled = true,
                Edges = new Dictionary<string, int?>
                {
                    { "left", null },
                    { "right", null },
                    { "top", null },
                    { "bottom", null }
                }
            };
        }

        public void SetMonitorConfig(string monitorId, bool enabled, Dictionary<string, int?> edges)
        {
            var mid = monitorId ?? "0";
            MonitorConfigs ??= new();
            MonitorConfigs[mid] = new MonitorEdgeConfig
            {
                Enabled = enabled,
                Edges = new Dictionary<string, int?>(edges)
            };

            if (mid == "0")
            {
                EdgeChannels = new Dictionary<string, int?>(edges);
            }
        }

        public bool IsMonitorEnabled(string monitorId)
        {
            return GetMonitorConfig(monitorId).Enabled;
        }

        public int? GetTargetChannelForMonitorEdge(string monitorId, string edge)
        {
            var cfg = GetMonitorConfig(monitorId);
            if (!cfg.Enabled) return null;

            var e = (edge ?? string.Empty).ToLowerInvariant();
            if (cfg.Edges != null && cfg.Edges.TryGetValue(e, out var ch))
            {
                return ch;
            }
            return null;
        }

        public int? GetTargetChannelForEdge(string edge, string monitorId = "0")
        {
            var ch = GetTargetChannelForMonitorEdge(monitorId, edge);
            if (ch.HasValue) return ch;

            var e = (edge ?? string.Empty).ToLowerInvariant();
            if (EdgeChannels != null && EdgeChannels.TryGetValue(e, out var legacyCh) && legacyCh.HasValue)
            {
                return legacyCh;
            }

            if (string.Equals(e, TriggerEdge, StringComparison.OrdinalIgnoreCase))
            {
                return TargetChannel;
            }

            return null;
        }

        public List<string> GetActiveEdges(string monitorId = "0")
        {
            var cfg = GetMonitorConfig(monitorId);
            var result = new List<string>();
            if (!cfg.Enabled) return result;

            if (cfg.Edges != null)
            {
                foreach (var (e, ch) in cfg.Edges)
                {
                    if (ch.HasValue) result.Add(e.ToLowerInvariant());
                }
            }

            if (result.Count == 0 && monitorId == "0")
            {
                if (EdgeChannels != null)
                {
                    foreach (var (e, ch) in EdgeChannels)
                    {
                        if (ch.HasValue) result.Add(e.ToLowerInvariant());
                    }
                }
                if (result.Count == 0 && !string.IsNullOrEmpty(TriggerEdge))
                {
                    result.Add(TriggerEdge.ToLowerInvariant());
                }
            }

            return result;
        }

        public List<(string MonitorId, string Edge, int TargetChannel)> GetAllActiveMonitorBorders()
        {
            var active = new List<(string, string, int)>();
            var mids = MonitorConfigs != null && MonitorConfigs.Count > 0
                ? new List<string>(MonitorConfigs.Keys)
                : new List<string> { "0" };

            if (!mids.Contains("0"))
                mids.Insert(0, "0");

            foreach (var mid in mids)
            {
                var cfg = GetMonitorConfig(mid);
                if (!cfg.Enabled || cfg.Edges == null) continue;

                foreach (var (edge, ch) in cfg.Edges)
                {
                    if (ch.HasValue)
                    {
                        active.Add((mid, edge.ToLowerInvariant(), ch.Value));
                    }
                }
            }
            return active;
        }

        public static AppConfig Load(string? path = null)
        {
            var cfgPath = path ?? DefaultConfigPath;
            AppConfig? configObj = null;

            var options = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                ReadCommentHandling = JsonCommentHandling.Skip,
                AllowTrailingCommas = true
            };

            if (File.Exists(cfgPath))
            {
                try
                {
                    var json = File.ReadAllText(cfgPath);
                    configObj = JsonSerializer.Deserialize<AppConfig>(json, options);
                }
                catch (Exception ex)
                {
                    AppLogger.Log("Config", $"Error loading {cfgPath}: {ex.Message}, using defaults.");
                }
            }
            else if (path == null && File.Exists(LegacyConfigPath))
            {
                try
                {
                    var json = File.ReadAllText(LegacyConfigPath);
                    configObj = JsonSerializer.Deserialize<AppConfig>(json, options);
                    if (configObj != null)
                    {
                        AppLogger.Log("Config", $"Migrated configuration from {LegacyConfigPath} to {DefaultConfigPath}");
                        configObj.Save(DefaultConfigPath);
                    }
                }
                catch (Exception ex)
                {
                    AppLogger.Log("Config", $"Error migrating legacy config: {ex.Message}");
                }
            }

            configObj ??= new AppConfig();
            AppLogger.SetLogLevel(configObj.LogLevel);
            return configObj;
        }

        public void Save(string? path = null)
        {
            var cfgPath = path ?? DefaultConfigPath;
            var dir = Path.GetDirectoryName(cfgPath);
            if (!string.IsNullOrEmpty(dir))
            {
                Directory.CreateDirectory(dir);
            }

            var options = new JsonSerializerOptions
            {
                WriteIndented = true
            };

            var json = JsonSerializer.Serialize(this, options);
            File.WriteAllText(cfgPath, json);
            AppLogger.Log("Config", $"Configuration saved to {cfgPath}");
            AppLogger.SetLogLevel(LogLevel);
        }
    }
}
