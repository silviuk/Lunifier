using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Threading;
using Microsoft.Win32;
using Lunifier.Windows.Core;
using Color = System.Windows.Media.Color;
using ColorConverter = System.Windows.Media.ColorConverter;
using Brush = System.Windows.Media.Brush;
using Point = System.Windows.Point;
using Size = System.Windows.Size;

namespace Lunifier.Windows
{
    public partial class BorderOverlayWindow : Window
    {
        private const int GWL_EXSTYLE = -20;
        private const int WS_EX_LAYERED = 0x00080000;
        private const int WS_EX_TRANSPARENT = 0x00000020;
        private const int WS_EX_TOOLWINDOW = 0x00000080;
        private const int WS_EX_NOACTIVATE = 0x08000000;

        private static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
        private const uint SWP_NOACTIVATE = 0x0010;
        private const uint SWP_SHOWWINDOW = 0x0040;

        [DllImport("user32.dll")]
        private static extern int GetWindowLong(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll")]
        private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

        [DllImport("user32.dll")]
        private static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        private readonly DispatcherTimer _hideTimer;
        private readonly List<BorderOverlayWindow> _secondaryWindows = new();
        private readonly bool _isSecondary;

        public BorderOverlayWindow() : this(false) { }

        private BorderOverlayWindow(bool isSecondary)
        {
            _isSecondary = isSecondary;
            InitializeComponent();
            Loaded += OnLoaded;

            if (!_isSecondary)
            {
                _hideTimer = new DispatcherTimer
                {
                    Interval = TimeSpan.FromSeconds(1.2)
                };
                _hideTimer.Tick += (s, e) =>
                {
                    _hideTimer.Stop();
                    HideAll();
                };
            }
            else
            {
                _hideTimer = null!;
            }
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            ApplyWindowStyles();
        }

        private void ApplyWindowStyles()
        {
            var hwnd = new WindowInteropHelper(this).EnsureHandle();
            int exStyle = GetWindowLong(hwnd, GWL_EXSTYLE);
            SetWindowLong(hwnd, GWL_EXSTYLE, exStyle | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_LAYERED);
        }

        public static Color GetAccentColor()
        {
            try
            {
                var val = Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\DWM", "AccentColor", null);
                if (val is int intVal)
                {
                    // Registry AccentColor is in AABBGGRR format
                    byte a = (byte)((intVal >> 24) & 0xFF);
                    byte b = (byte)((intVal >> 16) & 0xFF);
                    byte g = (byte)((intVal >> 8) & 0xFF);
                    byte r = (byte)(intVal & 0xFF);
                    if (a == 0) a = 255;
                    return Color.FromArgb(a, r, g, b);
                }
            }
            catch { }

            try
            {
                var glass = SystemParameters.WindowGlassColor;
                if (glass.A > 0) return glass;
            }
            catch { }

            return (Color)ColorConverter.ConvertFromString("#FF5722"); // Fallback to vibrant orange
        }

        public void ShowBorders(int activeZonePct, List<MonitorInfo> monitors, Dictionary<string, List<string>>? edgesByMonitor = null)
        {
            if (_isSecondary) return;
            _hideTimer?.Stop();

            // Collect only monitors that have active configured edges
            var targetMonitors = new List<(MonitorInfo Monitor, List<string> Edges)>();
            foreach (var m in monitors)
            {
                var mid = m.Id;
                if (edgesByMonitor != null)
                {
                    if (edgesByMonitor.TryGetValue(mid, out var list) && list != null && list.Count > 0)
                    {
                        targetMonitors.Add((m, list));
                    }
                    else if (mid == "0" && edgesByMonitor.TryGetValue("0", out var list0) && list0 != null && list0.Count > 0)
                    {
                        targetMonitors.Add((m, list0));
                    }
                }
            }

            if (targetMonitors.Count == 0)
            {
                HideAll();
                return;
            }

            var brush = new SolidColorBrush(GetAccentColor());
            brush.Freeze();

            var pct = Math.Clamp(activeZonePct, 10, 100);
            var marginRatio = (1.0 - (pct / 100.0)) / 2.0;

            // Render primary/first active monitor on 'this'
            var (firstMon, firstEdges) = targetMonitors[0];
            RenderOnMonitor(firstMon, firstEdges, marginRatio, brush);

            // Render additional active monitors on secondary windows
            for (int i = 1; i < targetMonitors.Count; i++)
            {
                int secIdx = i - 1;
                while (_secondaryWindows.Count <= secIdx)
                {
                    var secWin = new BorderOverlayWindow(true) { Owner = this.Owner };
                    _secondaryWindows.Add(secWin);
                }

                var (mon, edges) = targetMonitors[i];
                _secondaryWindows[secIdx].RenderOnMonitor(mon, edges, marginRatio, brush);
            }

            // Hide any unused secondary windows
            for (int i = targetMonitors.Count - 1; i < _secondaryWindows.Count; i++)
            {
                if (i >= 0 && i < _secondaryWindows.Count)
                {
                    _secondaryWindows[i].Hide();
                }
            }

            _hideTimer?.Start();
        }

        private void RenderOnMonitor(MonitorInfo m, List<string> edges, double marginRatio, Brush fillBrush)
        {
            ApplyWindowStyles();
            OverlayCanvas.Children.Clear();

            var hwnd = new WindowInteropHelper(this).EnsureHandle();
            SetWindowPos(hwnd, HWND_TOPMOST, m.Left, m.Top, m.Width, m.Height, SWP_NOACTIVATE | SWP_SHOWWINDOW);

            var dpi = VisualTreeHelper.GetDpi(this);
            double w = Math.Max(100, m.Width / dpi.DpiScaleX);
            double h = Math.Max(100, m.Height / dpi.DpiScaleY);

            Width = w;
            Height = h;
            OverlayCanvas.Width = w;
            OverlayCanvas.Height = h;

            foreach (var edge in edges)
            {
                var bar = CreateBorderBar(edge, w, h, marginRatio, fillBrush);
                if (bar != null)
                {
                    OverlayCanvas.Children.Add(bar);
                }
            }

            Show();
        }

        private static Shape? CreateBorderBar(string edge, double w, double h, double marginRatio, Brush fillBrush)
        {
            const double T = 7.0;       // Base thickness
            const double B = 3.5;       // Convex bulge towards screen center
            const double R = 3.0;       // Corner rounding radius at ends

            var edgeLower = (edge ?? string.Empty).ToLowerInvariant();
            PathFigure fig;

            switch (edgeLower)
            {
                case "left":
                {
                    double y0 = marginRatio * h;
                    double segH = Math.Max(12, (1.0 - 2.0 * marginRatio) * h);
                    double y1 = y0 + segH;

                    fig = new PathFigure { StartPoint = new Point(0, y0), IsClosed = true, IsFilled = true };
                    fig.Segments.Add(new LineSegment(new Point(T - R, y0), true));
                    fig.Segments.Add(new ArcSegment(new Point(T, y0 + R), new Size(R, R), 0, false, SweepDirection.Clockwise, true));
                    fig.Segments.Add(new QuadraticBezierSegment(new Point(T + B * 1.33, y0 + segH / 2.0), new Point(T, y1 - R), true));
                    fig.Segments.Add(new ArcSegment(new Point(T - R, y1), new Size(R, R), 0, false, SweepDirection.Clockwise, true));
                    fig.Segments.Add(new LineSegment(new Point(0, y1), true));
                    break;
                }
                case "right":
                {
                    double y0 = marginRatio * h;
                    double segH = Math.Max(12, (1.0 - 2.0 * marginRatio) * h);
                    double y1 = y0 + segH;

                    fig = new PathFigure { StartPoint = new Point(w, y0), IsClosed = true, IsFilled = true };
                    fig.Segments.Add(new LineSegment(new Point(w - T + R, y0), true));
                    fig.Segments.Add(new ArcSegment(new Point(w - T, y0 + R), new Size(R, R), 0, false, SweepDirection.Counterclockwise, true));
                    fig.Segments.Add(new QuadraticBezierSegment(new Point(w - T - B * 1.33, y0 + segH / 2.0), new Point(w - T, y1 - R), true));
                    fig.Segments.Add(new ArcSegment(new Point(w - T + R, y1), new Size(R, R), 0, false, SweepDirection.Counterclockwise, true));
                    fig.Segments.Add(new LineSegment(new Point(w, y1), true));
                    break;
                }
                case "top":
                {
                    double x0 = marginRatio * w;
                    double segW = Math.Max(12, (1.0 - 2.0 * marginRatio) * w);
                    double x1 = x0 + segW;

                    fig = new PathFigure { StartPoint = new Point(x0, 0), IsClosed = true, IsFilled = true };
                    fig.Segments.Add(new LineSegment(new Point(x0, T - R), true));
                    fig.Segments.Add(new ArcSegment(new Point(x0 + R, T), new Size(R, R), 0, false, SweepDirection.Counterclockwise, true));
                    fig.Segments.Add(new QuadraticBezierSegment(new Point(x0 + segW / 2.0, T + B * 1.33), new Point(x1 - R, T), true));
                    fig.Segments.Add(new ArcSegment(new Point(x1, T - R), new Size(R, R), 0, false, SweepDirection.Counterclockwise, true));
                    fig.Segments.Add(new LineSegment(new Point(x1, 0), true));
                    break;
                }
                case "bottom":
                {
                    double x0 = marginRatio * w;
                    double segW = Math.Max(12, (1.0 - 2.0 * marginRatio) * w);
                    double x1 = x0 + segW;

                    fig = new PathFigure { StartPoint = new Point(x0, h), IsClosed = true, IsFilled = true };
                    fig.Segments.Add(new LineSegment(new Point(x0, h - T + R), true));
                    fig.Segments.Add(new ArcSegment(new Point(x0 + R, h - T), new Size(R, R), 0, false, SweepDirection.Clockwise, true));
                    fig.Segments.Add(new QuadraticBezierSegment(new Point(x0 + segW / 2.0, h - T - B * 1.33), new Point(x1 - R, h - T), true));
                    fig.Segments.Add(new ArcSegment(new Point(x1, h - T + R), new Size(R, R), 0, false, SweepDirection.Clockwise, true));
                    fig.Segments.Add(new LineSegment(new Point(x1, h), true));
                    break;
                }
                default:
                    return null;
            }

            var geo = new PathGeometry(new[] { fig });
            var path = new Path
            {
                Data = geo,
                Fill = fillBrush,
                IsHitTestVisible = false
            };
            RenderOptions.SetEdgeMode(path, EdgeMode.Unspecified); // Anti-aliased DirectX vector rasterization
            return path;
        }

        public void HideAll()
        {
            _hideTimer?.Stop();
            Hide();
            foreach (var w in _secondaryWindows)
            {
                try { w.Hide(); } catch { }
            }
        }

        public void CloseAll()
        {
            _hideTimer?.Stop();
            Hide();
            foreach (var w in _secondaryWindows)
            {
                try { w.Close(); } catch { }
            }
            _secondaryWindows.Clear();
            try { Close(); } catch { }
        }
    }
}
