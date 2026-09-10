using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;

namespace Lunifier.Windows.Core
{
    public class MonitorInfo
    {
        public string Id { get; set; } = "0";
        public string Name { get; set; } = string.Empty;
        public int Left { get; set; }
        public int Top { get; set; }
        public int Right { get; set; }
        public int Bottom { get; set; }
        public int Width { get; set; }
        public int Height { get; set; }
        public bool IsPrimary { get; set; }
        public int Index { get; set; }

        public bool Contains(int x, int y, int tol = 2)
        {
            return (Left - tol) <= x && x <= (Right + tol) &&
                   (Top - tol) <= y && y <= (Bottom + tol);
        }

        public double CalculateRatio(int x, int y, string edge)
        {
            var e = (edge ?? string.Empty).ToLowerInvariant();
            if (e is "left" or "right")
            {
                if (Height <= 0) return 0.5;
                return Math.Clamp((y - Top) / (double)Height, 0.0, 1.0);
            }
            else
            {
                if (Width <= 0) return 0.5;
                return Math.Clamp((x - Left) / (double)Width, 0.0, 1.0);
            }
        }
    }

    public static class MonitorManager
    {
        [StructLayout(LayoutKind.Sequential)]
        private struct RECT
        {
            public int left;
            public int top;
            public int right;
            public int bottom;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct MONITORINFOEXW
        {
            public int cbSize;
            public RECT rcMonitor;
            public RECT rcWork;
            public int dwFlags;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
            public string szDevice;
        }

        private delegate bool MonitorEnumProc(IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData);

        [DllImport("user32.dll")]
        private static extern bool EnumDisplayMonitors(IntPtr hdc, IntPtr lprcClip, MonitorEnumProc lpfnEnum, IntPtr dwData);

        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        private static extern bool GetMonitorInfoW(IntPtr hMonitor, ref MONITORINFOEXW lpmi);

        [DllImport("user32.dll")]
        private static extern bool SetProcessDpiAwarenessContext(IntPtr dpiContext);

        private static readonly IntPtr DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = new IntPtr(-4);

        static MonitorManager()
        {
            try
            {
                SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
            }
            catch
            {
                // Fallback on older Windows versions
            }
        }

        public static List<MonitorInfo> GetMonitors()
        {
            var list = new List<MonitorInfo>();

            bool Callback(IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData)
            {
                var info = new MONITORINFOEXW();
                info.cbSize = Marshal.SizeOf(typeof(MONITORINFOEXW));

                if (GetMonitorInfoW(hMonitor, ref info))
                {
                    var r = info.rcMonitor;
                    var isPrimary = (info.dwFlags & 1) != 0;
                    var w = r.right - r.left;
                    var h = r.bottom - r.top;
                    var idx = list.Count + 1;
                    var primaryTag = isPrimary ? " (Primary)" : "";

                    list.Add(new MonitorInfo
                    {
                        Id = (idx - 1).ToString(),
                        Name = $"Monitor {idx}{primaryTag} - {w}x{h} at ({r.left}, {r.top})",
                        Left = r.left,
                        Top = r.top,
                        Right = r.right,
                        Bottom = r.bottom,
                        Width = w,
                        Height = h,
                        IsPrimary = isPrimary,
                        Index = idx - 1
                    });
                }
                return true;
            }

            try
            {
                EnumDisplayMonitors(IntPtr.Zero, IntPtr.Zero, Callback, IntPtr.Zero);
            }
            catch (Exception ex)
            {
                AppLogger.Log("Monitors", $"Error enumerating monitors: {ex.Message}");
            }

            if (list.Count == 0)
            {
                // Universal fallback
                return new List<MonitorInfo>
                {
                    new MonitorInfo
                    {
                        Id = "0",
                        Name = "Monitor 1 (Primary) - 1920x1080 at (0, 0)",
                        Left = 0,
                        Top = 0,
                        Right = 1920,
                        Bottom = 1080,
                        Width = 1920,
                        Height = 1080,
                        IsPrimary = true,
                        Index = 0
                    }
                };
            }

            // Sort primary first, then left-to-right, top-to-bottom
            list = list.OrderBy(m => !m.IsPrimary)
                       .ThenBy(m => m.Left)
                       .ThenBy(m => m.Top)
                       .ToList();

            for (int i = 0; i < list.Count; i++)
            {
                list[i].Id = i.ToString();
                list[i].Index = i;
                var primaryTag = list[i].IsPrimary ? " (Primary)" : "";
                list[i].Name = $"Monitor {i + 1}{primaryTag} - {list[i].Width}x{list[i].Height} at ({list[i].Left}, {list[i].Top})";
            }

            return list;
        }

        public static MonitorInfo? GetMonitorForPoint(List<MonitorInfo> monitors, int x, int y, int tol = 2)
        {
            if (monitors == null || monitors.Count == 0) return null;

            // 1. Exact match
            foreach (var m in monitors)
            {
                if (m.Left <= x && x <= m.Right && m.Top <= y && y <= m.Bottom)
                    return m;
            }

            // 2. Tolerance match
            foreach (var m in monitors)
            {
                if (m.Contains(x, y, tol))
                    return m;
            }

            // 3. Closest monitor fallback
            MonitorInfo best = monitors[0];
            double minDist = double.MaxValue;
            foreach (var m in monitors)
            {
                var dx = Math.Max(m.Left - x, Math.Max(0, x - m.Right));
                var dy = Math.Max(m.Top - y, Math.Max(0, y - m.Bottom));
                var dist = dx * dx + dy * dy;
                if (dist < minDist)
                {
                    minDist = dist;
                    best = m;
                }
            }
            return best;
        }

        public static (int Left, int Top, int Right, int Bottom) GetVirtualDesktopBounds(List<MonitorInfo> monitors)
        {
            if (monitors == null || monitors.Count == 0)
                return (0, 0, 1920, 1080);

            return (
                monitors.Min(m => m.Left),
                monitors.Min(m => m.Top),
                monitors.Max(m => m.Right),
                monitors.Max(m => m.Bottom)
            );
        }
    }
}
