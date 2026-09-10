using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Threading;
using Lunifier.Windows.Core;

namespace Lunifier.Windows
{
    public partial class BorderOverlayWindow : Window
    {
        private const int GWL_EXSTYLE = -20;
        private const int WS_EX_LAYERED = 0x00080000;
        private const int WS_EX_TRANSPARENT = 0x00000020;
        private const int WS_EX_TOOLWINDOW = 0x00000080;
        private const int WS_EX_NOACTIVATE = 0x08000000;

        [DllImport("user32.dll")]
        private static extern int GetWindowLong(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll")]
        private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

        private readonly DispatcherTimer _hideTimer;
        private static readonly SolidColorBrush LineBrush = new((Color)ColorConverter.ConvertFromString("#FF5722"));
        private const int LineThickness = 5;

        public BorderOverlayWindow()
        {
            InitializeComponent();
            Loaded += OnLoaded;

            _hideTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(1.0)
            };
            _hideTimer.Tick += (s, e) =>
            {
                _hideTimer.Stop();
                Hide();
            };
        }

        private void OnLoaded(object sender, RoutedEventArgs e)
        {
            var hwnd = new WindowInteropHelper(this).Handle;
            int exStyle = GetWindowLong(hwnd, GWL_EXSTYLE);
            SetWindowLong(hwnd, GWL_EXSTYLE, exStyle | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_LAYERED);
        }

        public void ShowBorders(int activeZonePct, List<MonitorInfo> monitors, Dictionary<string, List<string>>? edgesByMonitor = null)
        {
            _hideTimer.Stop();

            OverlayCanvas.Children.Clear();
            var bounds = MonitorManager.GetVirtualDesktopBounds(monitors);

            // Cover the entire virtual desktop
            Left = bounds.Left;
            Top = bounds.Top;
            Width = Math.Max(1, bounds.Right - bounds.Left);
            Height = Math.Max(1, bounds.Bottom - bounds.Top);

            var pct = Math.Clamp(activeZonePct, 10, 100);
            var marginRatio = (1.0 - (pct / 100.0)) / 2.0;

            foreach (var m in monitors)
            {
                var mid = m.Id;
                List<string>? edges = null;

                if (edgesByMonitor != null && edgesByMonitor.TryGetValue(mid, out var list))
                {
                    edges = list;
                }
                else
                {
                    edges = new List<string> { "left", "right", "top", "bottom" };
                }

                if (edges == null || edges.Count == 0) continue;

                foreach (var edge in edges)
                {
                    var rect = new Rectangle
                    {
                        Fill = LineBrush,
                        IsHitTestVisible = false
                    };

                    double segX, segY, segW, segH;
                    var localLeft = m.Left - bounds.Left;
                    var localTop = m.Top - bounds.Top;

                    switch (edge.ToLowerInvariant())
                    {
                        case "left":
                            segX = localLeft;
                            segY = localTop + (marginRatio * m.Height);
                            segW = LineThickness;
                            segH = Math.Max(1, (1.0 - 2.0 * marginRatio) * m.Height);
                            break;
                        case "right":
                            segX = localLeft + m.Width - LineThickness;
                            segY = localTop + (marginRatio * m.Height);
                            segW = LineThickness;
                            segH = Math.Max(1, (1.0 - 2.0 * marginRatio) * m.Height);
                            break;
                        case "top":
                            segX = localLeft + (marginRatio * m.Width);
                            segY = localTop;
                            segW = Math.Max(1, (1.0 - 2.0 * marginRatio) * m.Width);
                            segH = LineThickness;
                            break;
                        case "bottom":
                            segX = localLeft + (marginRatio * m.Width);
                            segY = localTop + m.Height - LineThickness;
                            segW = Math.Max(1, (1.0 - 2.0 * marginRatio) * m.Width);
                            segH = LineThickness;
                            break;
                        default:
                            continue;
                    }

                    Canvas.SetLeft(rect, segX);
                    Canvas.SetTop(rect, segY);
                    rect.Width = segW;
                    rect.Height = segH;

                    OverlayCanvas.Children.Add(rect);
                }
            }

            Show();
            _hideTimer.Start();
        }
    }
}
