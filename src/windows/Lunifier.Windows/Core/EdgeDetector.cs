using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
using Lunifier.Windows.Config;

namespace Lunifier.Windows.Core
{
    public class EdgeDetector
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct POINT
        {
            public int x;
            public int y;
        }

        [DllImport("user32.dll")]
        private static extern bool GetCursorPos(out POINT lpPoint);

        [DllImport("user32.dll")]
        private static extern bool SetCursorPos(int X, int Y);

        public string TriggerEdge { get; set; } = "right";
        public List<string> ActiveEdges { get; set; } = new() { "right" };
        public int HoldDelayMs { get; set; } = 250;
        public int CooldownMs { get; set; } = 500;
        public int ActiveZonePct { get; set; } = 50;
        public bool KnockEnabled { get; set; } = false;
        public int KnockTimeoutMs { get; set; } = 1000;
        public Dictionary<string, MonitorEdgeConfig> MonitorConfigs { get; set; } = new();

        public Action<string, int, int, double, string, int>? OnTriggerCallback { get; set; }

        private bool _running;
        private Thread? _thread;
        private string? _currentEdge;
        private string? _currentMonitorId;
        private double? _holdStartTime;
        private double _lastTriggerTime;

        private List<MonitorInfo> _monitors = new();
        private (int Left, int Top, int Right, int Bottom) _screenBounds;

        private string? _lastKnockEdge;
        private double _lastKnockTime;

        private bool _isSwitchedOut;
        private string? _switchedOutEdge;
        private (int X, int Y)? _lastKnownCursorPos;
        private double _returnGuardUntil;
        private double _lastCooldownLogTime;

        private struct CursorHistoryItem
        {
            public double Time;
            public int X;
            public int Y;
        }

        private readonly CursorHistoryItem[] _historyBuffer = new CursorHistoryItem[64];
        private int _historyCount;
        private int _historyHead;
        private readonly object _historyLock = new();
        private MonitorEdgeConfig? _cachedDefaultConfig;

        private void AddCursorHistory(double time, int x, int y)
        {
            lock (_historyLock)
            {
                _historyBuffer[_historyHead] = new CursorHistoryItem { Time = time, X = x, Y = y };
                _historyHead = (_historyHead + 1) % _historyBuffer.Length;
                if (_historyCount < _historyBuffer.Length)
                    _historyCount++;
            }
        }

        private void ClearCursorHistory()
        {
            lock (_historyLock)
            {
                _historyCount = 0;
                _historyHead = 0;
            }
        }

        private const int MinApproachDisplacement = 15;
        private readonly Stopwatch _stopwatch = Stopwatch.StartNew();

        private double NowSeconds => _stopwatch.Elapsed.TotalSeconds;

        public EdgeDetector(AppConfig config, Action<string, int, int, double, string, int>? callback = null)
        {
            UpdateFromConfig(config);
            OnTriggerCallback = callback;
            RefreshScreenBounds();
        }

        public void UpdateFromConfig(AppConfig config)
        {
            TriggerEdge = config.TriggerEdge.ToLowerInvariant();
            ActiveEdges = config.GetActiveEdges();
            HoldDelayMs = config.HoldDelayMs;
            CooldownMs = config.CooldownMs;
            ActiveZonePct = Math.Clamp(config.BorderActiveZonePct, 10, 100);
            KnockEnabled = config.KnockEnabled;
            KnockTimeoutMs = config.KnockTimeoutMs;
            MonitorConfigs = config.MonitorConfigs ?? new();

            var edges = new Dictionary<string, int?>();
            foreach (var e in ActiveEdges)
                edges[e] = 2;
            _cachedDefaultConfig = new MonitorEdgeConfig { Enabled = true, Edges = edges };
        }

        public void RefreshScreenBounds()
        {
            _monitors = MonitorManager.GetMonitors();
            _screenBounds = MonitorManager.GetVirtualDesktopBounds(_monitors);
        }

        public void Start()
        {
            if (_running) return;
            _running = true;
            RefreshScreenBounds();
            _thread = new Thread(Loop)
            {
                Name = "EdgeDetectorThread",
                IsBackground = true,
                Priority = ThreadPriority.Normal
            };
            _thread.Start();
            AppLogger.Log("EdgeDetector", $"Started monitoring across {_monitors.Count} monitor(s). Bounds: ({_screenBounds.Left}, {_screenBounds.Top}, {_screenBounds.Right}, {_screenBounds.Bottom})");
        }

        public void Stop()
        {
            _running = false;
            _thread?.Join(500);
            _thread = null;
            AppLogger.Log("EdgeDetector", "Stopped.");
        }

        public void NotifySwitchedOut(string edge, int cursorX, int cursorY)
        {
            _isSwitchedOut = true;
            _switchedOutEdge = edge;
            _lastKnownCursorPos = (cursorX, cursorY);
            _lastTriggerTime = NowSeconds;
            _returnGuardUntil = 0.0;
            _lastKnockEdge = null;
            _lastKnockTime = 0.0;
            _holdStartTime = null;
            _currentEdge = null;
            _currentMonitorId = null;
            ClearCursorHistory();
            AppLogger.Log("EdgeDetector", $"Switched out via '{edge}'. Cursor parked at ({cursorX}, {cursorY}). Return guard armed.");
        }

        public void NotifySwitchedIn(string? entryEdge = null)
        {
            var now = NowSeconds;
            _isSwitchedOut = false;
            _lastTriggerTime = now;
            var guardDur = Math.Min(CooldownMs, 1000) / 1000.0;
            _returnGuardUntil = now + guardDur;
            _lastKnockEdge = null;
            _lastKnockTime = 0.0;
            _holdStartTime = null;
            _currentEdge = null;
            _currentMonitorId = null;
            ClearCursorHistory();
            AppLogger.Log("EdgeDetector", $"Mouse return detected (entry: {entryEdge ?? "unknown"}). Return guard armed for {(int)(guardDur * 1000)}ms.");
        }

        private MonitorEdgeConfig GetMonitorConfig(string monitorId)
        {
            var mid = monitorId ?? "0";
            if (MonitorConfigs.TryGetValue(mid, out var cfg))
                return cfg;

            if (mid == "0" && _cachedDefaultConfig != null)
                return _cachedDefaultConfig;

            return new MonitorEdgeConfig { Enabled = true, Edges = new() };
        }

        private (string Edge, double Ratio, string MonitorId, int TargetChannel)? GetTriggeredEdgeInfo(int x, int y)
        {
            var m = MonitorManager.GetMonitorForPoint(_monitors, x, y, tol: 2);
            if (m == null) return null;

            var mid = m.Id;
            var mCfg = GetMonitorConfig(mid);
            if (!mCfg.Enabled || mCfg.Edges == null) return null;

            const int tol = 2;

            foreach (var (edgeName, ch) in mCfg.Edges)
            {
                if (!ch.HasValue) continue;
                var edge = edgeName.ToLowerInvariant();
                bool atBorder = edge switch
                {
                    "left" => (x <= m.Left + tol) && (m.Top - tol <= y && y <= m.Bottom + tol),
                    "right" => (x >= m.Right - tol) && (m.Top - tol <= y && y <= m.Bottom + tol),
                    "top" => (y <= m.Top + tol) && (m.Left - tol <= x && x <= m.Right + tol),
                    "bottom" => (y >= m.Bottom - tol) && (m.Left - tol <= x && x <= m.Right + tol),
                    _ => false
                };

                if (atBorder)
                {
                    double ratio = edge is "left" or "right"
                        ? Math.Clamp((y - m.Top) / (double)Math.Max(1, m.Height), 0.0, 1.0)
                        : Math.Clamp((x - m.Left) / (double)Math.Max(1, m.Width), 0.0, 1.0);

                    if (ActiveZonePct < 100)
                    {
                        var margin = (1.0 - (ActiveZonePct / 100.0)) / 2.0;
                        if (ratio < margin || ratio > (1.0 - margin))
                            continue;
                    }

                    return (edge, ratio, mid, ch.Value);
                }
            }

            return null;
        }

        private bool IsApproachingEdge(string edge, int currentX, int currentY, double? holdStart)
        {
            lock (_historyLock)
            {
                if (_historyCount < 2) return true;

                var targetTime = (holdStart ?? NowSeconds) - 0.08;
                int oldestIdx = (_historyHead - _historyCount + _historyBuffer.Length) % _historyBuffer.Length;
                (int X, int Y) prev = (_historyBuffer[oldestIdx].X, _historyBuffer[oldestIdx].Y);

                for (int i = 0; i < _historyCount; i++)
                {
                    int idx = (_historyHead - _historyCount + i + _historyBuffer.Length) % _historyBuffer.Length;
                    var item = _historyBuffer[idx];
                    if (item.Time <= targetTime)
                    {
                        prev = (item.X, item.Y);
                    }
                }

                const int minDisplacement = 4;
                return edge switch
                {
                    "right" => (currentX - prev.X) >= minDisplacement,
                    "left" => (prev.X - currentX) >= minDisplacement,
                    "bottom" => (currentY - prev.Y) >= minDisplacement,
                    "top" => (prev.Y - currentY) >= minDisplacement,
                    _ => true
                };
            }
        }

        private void Loop()
        {
            while (_running)
            {
                try
                {
                    var now = NowSeconds;
                    if (!GetCursorPos(out var pt))
                    {
                        Thread.Sleep(15);
                        continue;
                    }

                    int x = pt.x;
                    int y = pt.y;

                    // Anti-bounceback Return Guard
                    if (_isSwitchedOut)
                    {
                        if (_lastKnownCursorPos.HasValue)
                        {
                            var (lx, ly) = _lastKnownCursorPos.Value;
                            var dx = x - lx;
                            var dy = y - ly;
                            if ((dx * dx + dy * dy) > 2500) // Deliberate movement > 50 pixels
                            {
                                AppLogger.Log("EdgeDetector", $"Physical mouse movement detected on host ({lx}, {ly}) -> ({x}, {y})");
                                NotifySwitchedIn(_switchedOutEdge);
                                _lastKnownCursorPos = (x, y);
                                Thread.Sleep(50);
                                continue;
                            }
                        }
                        else
                        {
                            _lastKnownCursorPos = (x, y);
                        }
                        Thread.Sleep(50);
                        continue;
                    }

                    AddCursorHistory(now, x, y);

                    // Cooldown check
                    if ((now - _lastTriggerTime) * 1000 < CooldownMs || now < _returnGuardUntil)
                    {
                        var trig = GetTriggeredEdgeInfo(x, y);
                        if (trig.HasValue && (now - _lastCooldownLogTime) >= 0.5)
                        {
                            _lastCooldownLogTime = now;
                            var remaining = Math.Max(0, (int)((Math.Max(_lastTriggerTime + CooldownMs / 1000.0, _returnGuardUntil) - now) * 1000));
                            AppLogger.LogDebug("EdgeDetector", $"Border '{trig.Value.Edge}' touched during cooldown ({remaining}ms remaining)");
                        }
                        _holdStartTime = null;
                        _currentEdge = null;
                        _currentMonitorId = null;
                        Thread.Sleep(20);
                        continue;
                    }

                    // Expire stale knock
                    if (KnockEnabled && _lastKnockEdge != null)
                    {
                        if ((now - _lastKnockTime) * 1000 > KnockTimeoutMs)
                        {
                            _lastKnockEdge = null;
                            _lastKnockTime = 0.0;
                        }
                    }

                    var triggerInfo = GetTriggeredEdgeInfo(x, y);

                    if (triggerInfo.HasValue)
                    {
                        var (edge, ratio, mid, ch) = triggerInfo.Value;
                        var key = $"{mid}_{edge}";

                        if (_currentEdge != key)
                        {
                            _currentEdge = key;
                            _currentMonitorId = mid;
                            _holdStartTime = now;
                            AppLogger.Log("EdgeDetector", $"Cursor reached border '{edge}' on Monitor {mid} at ({x}, {y}) [Ratio: {ratio:F2}] -> Holding for {HoldDelayMs}ms...");
                        }
                        else
                        {
                            var elapsedMs = (now - _holdStartTime!.Value) * 1000;
                            var requiredHold = KnockEnabled ? Math.Min(100, HoldDelayMs) : HoldDelayMs;

                            if (elapsedMs >= requiredHold)
                            {
                                bool canTrigger = (HoldDelayMs > 0) || IsApproachingEdge(edge, x, y, _holdStartTime);
                                if (canTrigger)
                                {
                                    if (KnockEnabled)
                                    {
                                        if (_lastKnockEdge == key && ((now - _lastKnockTime) * 1000 <= KnockTimeoutMs))
                                        {
                                            AppLogger.Log("EdgeDetector", $"Border knock (2/2) on Monitor {mid} '{edge}' -> Switch to Channel {ch}");
                                            _lastKnockEdge = null;
                                            _lastKnockTime = 0.0;
                                            _lastTriggerTime = now;
                                            _holdStartTime = null;
                                            _currentEdge = null;
                                            _currentMonitorId = null;
                                            ClearCursorHistory();
                                            try
                                            {
                                                OnTriggerCallback?.Invoke(edge, x, y, ratio, mid, ch);
                                            }
                                            catch (Exception cbEx)
                                            {
                                                AppLogger.Log("EdgeDetector", $"Error executing trigger callback: {cbEx.Message}");
                                            }
                                        }
                                        else
                                        {
                                            AppLogger.Log("EdgeDetector", $"Border knock (1/2) on Monitor {mid} '{edge}' at ({x}, {y})");
                                            _lastKnockEdge = key;
                                            _lastKnockTime = now;
                                            _holdStartTime = null;
                                            _currentEdge = null;
                                            Thread.Sleep(150);
                                        }
                                    }
                                    else
                                    {
                                        AppLogger.Log("EdgeDetector", $"Edge '{edge}' on Monitor {mid} triggered at ({x}, {y}) ratio={ratio:F2} -> Switch to Channel {ch}");
                                        _lastTriggerTime = now;
                                        _holdStartTime = null;
                                        _currentEdge = null;
                                        _currentMonitorId = null;
                                        ClearCursorHistory();
                                        try
                                        {
                                            OnTriggerCallback?.Invoke(edge, x, y, ratio, mid, ch);
                                        }
                                        catch (Exception cbEx)
                                        {
                                            AppLogger.Log("EdgeDetector", $"Error executing trigger callback: {cbEx.Message}");
                                        }
                                    }
                                }
                            }
                        }
                    }
                    else
                    {
                        _currentEdge = null;
                        _currentMonitorId = null;
                        _holdStartTime = null;
                    }

                    Thread.Sleep(15);
                }
                catch (Exception ex)
                {
                    AppLogger.Log("EdgeDetector", $"Error in detector loop: {ex.Message}");
                    Thread.Sleep(50);
                }
            }
        }
    }
}
