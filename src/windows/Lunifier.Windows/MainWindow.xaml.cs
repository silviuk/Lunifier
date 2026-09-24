using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;
using Lunifier.Windows.Config;
using Lunifier.Windows.Core;
using Application = System.Windows.Application;
using Button = System.Windows.Controls.Button;
using ComboBox = System.Windows.Controls.ComboBox;
using MessageBox = System.Windows.MessageBox;
using Forms = System.Windows.Forms;
using Color = System.Windows.Media.Color;
using ColorConverter = System.Windows.Media.ColorConverter;
using DrawingIcon = System.Drawing.Icon;

namespace Lunifier.Windows
{
    public partial class MainWindow : Window
    {
        private AppConfig _config;
        private readonly LunifierService _service;
        private BorderOverlayWindow? _overlay;
        private List<MonitorInfo> _monitors = new();
        private string _selectedMonitorId = "0";
        private bool _isLoadingConfig = true;

        private Forms.NotifyIcon? _trayIcon;
        private bool _isExiting = false;
        private HwndSource? _hwndSource;
        private const int WM_HOTKEY = 0x0312;
        private const uint MOD_ALT = 0x0001;
        private const uint MOD_CONTROL = 0x0002;
        private const uint MOD_NOREPEAT = 0x4000;
        private const int HOTKEY_ID_CH1 = 9001;
        private const int HOTKEY_ID_CH2 = 9002;
        private const int HOTKEY_ID_CH3 = 9003;

        [DllImport("user32.dll")]
        private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

        [DllImport("user32.dll")]
        private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

        private readonly bool _startMinimized;

        public MainWindow() : this(false) { }

        public MainWindow(bool startMinimized)
        {
            _startMinimized = startMinimized;
            _config = AppConfig.Load();
            _service = new LunifierService(_config);

            InitializeComponent();

            _service.StateChanged += OnServiceStateChanged;
            AppLogger.LogReceived += OnLogReceived;

            if (_service.BtPeer != null)
            {
                _service.BtPeer.OnAdvertisingStateChanged += OnBtAdvertisingStateChanged;
            }

            Loaded += MainWindow_Loaded;
            Closing += MainWindow_Closing;
        }

        private void MainWindow_Loaded(object sender, RoutedEventArgs e)
        {
            try
            {
                var helper = new WindowInteropHelper(this);
                ThemeManager.ApplyTitleBarTheme(helper.Handle, ThemeManager.IsDark);
                ThemeManager.ThemeChanged += isDark =>
                {
                    Dispatcher.InvokeAsync(() => ThemeManager.ApplyTitleBarTheme(helper.Handle, isDark));
                };

                _overlay = new BorderOverlayWindow { Owner = this };
                SetupBorderCombos();
                LoadMonitors();
                PopulateUiFromConfig();
                _isLoadingConfig = false;

                InitializeTrayIcon();
                RegisterGlobalHotkeys();

                // Auto-start service on launch if not running
                if (!_service.IsRunning)
                {
                    _service.Start();
                }

                // Trigger initial device scan in background
                RefreshDevicesAsync();

                if (_startMinimized)
                {
                    Hide();
                    WindowState = WindowState.Minimized;
                    ShowInTaskbar = false;
                }
            }
            catch (Exception ex)
            {
                AppLogger.Log("GUI", $"Error during MainWindow_Loaded: {ex}");
                MessageBox.Show($"Initialization error in MainWindow_Loaded:\n\n{ex.Message}\n\n{ex.StackTrace}",
                    "Lunifier - Load Error", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void MainWindow_Closing(object? sender, System.ComponentModel.CancelEventArgs e)
        {
            if (!_isExiting)
            {
                e.Cancel = true;
                Hide();
                return;
            }

            _service.Stop();
            try { _overlay?.Close(); } catch { }
            UnregisterGlobalHotkeys();
            _trayIcon?.Dispose();
        }

        private void InitializeTrayIcon()
        {
            try
            {
                _trayIcon = new Forms.NotifyIcon
                {
                    Text = "Lunifier - Logitech Easy-Switch Flow",
                    Visible = true
                };

                var iconPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Resources", "icon.ico");
                if (File.Exists(iconPath))
                {
                    _trayIcon.Icon = new DrawingIcon(iconPath);
                }
                else
                {
                    var exePath = Environment.ProcessPath ?? Path.Combine(AppContext.BaseDirectory, "Lunifier.exe");
                    _trayIcon.Icon = DrawingIcon.ExtractAssociatedIcon(exePath);
                }

                var contextMenu = new Forms.ContextMenuStrip();
                var showItem = new Forms.ToolStripMenuItem("Show Lunifier", null, (s, e) => RestoreFromTray());
                var toggleServiceItem = new Forms.ToolStripMenuItem("Start / Stop Service", null, (s, e) => ToggleServiceBtn_Click(this, new RoutedEventArgs()));
                var exitItem = new Forms.ToolStripMenuItem("Exit", null, (s, e) => ExitApplication());

                contextMenu.Items.Add(showItem);
                contextMenu.Items.Add(toggleServiceItem);
                contextMenu.Items.Add(new Forms.ToolStripSeparator());
                contextMenu.Items.Add(exitItem);

                _trayIcon.ContextMenuStrip = contextMenu;
                _trayIcon.DoubleClick += (s, e) => RestoreFromTray();
            }
            catch (Exception ex)
            {
                AppLogger.Log("GUI", $"Failed to initialize system tray icon: {ex.Message}");
            }
        }

        public void RestoreFromTray()
        {
            ShowInTaskbar = true;
            Visibility = Visibility.Visible;
            WindowState = WindowState.Normal;
            Show();
            Activate();
            Focus();
        }

        private void ExitApplication()
        {
            _isExiting = true;
            _service.Stop();
            _trayIcon?.Dispose();
            UnregisterGlobalHotkeys();
            Application.Current.Shutdown();
        }

        private void RegisterGlobalHotkeys()
        {
            try
            {
                var helper = new WindowInteropHelper(this);
                _hwndSource = HwndSource.FromHwnd(helper.Handle);
                _hwndSource?.AddHook(HwndHook);

                // Register Ctrl+Alt+1, Ctrl+Alt+2, Ctrl+Alt+3
                RegisterHotKey(helper.Handle, HOTKEY_ID_CH1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x31);
                RegisterHotKey(helper.Handle, HOTKEY_ID_CH2, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x32);
                RegisterHotKey(helper.Handle, HOTKEY_ID_CH3, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, 0x33);
                AppLogger.Log("GUI", "Registered global hotkeys: Ctrl+Alt+1/2/3 for instant channel switching.");
            }
            catch (Exception ex)
            {
                AppLogger.Log("GUI", $"Failed to register global hotkeys: {ex.Message}");
            }
        }

        private void UnregisterGlobalHotkeys()
        {
            try
            {
                var helper = new WindowInteropHelper(this);
                UnregisterHotKey(helper.Handle, HOTKEY_ID_CH1);
                UnregisterHotKey(helper.Handle, HOTKEY_ID_CH2);
                UnregisterHotKey(helper.Handle, HOTKEY_ID_CH3);
                _hwndSource?.RemoveHook(HwndHook);
            }
            catch { }
        }

        private IntPtr HwndHook(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            if (msg == WM_HOTKEY)
            {
                int id = wParam.ToInt32();
                switch (id)
                {
                    case HOTKEY_ID_CH1:
                        TestSwitch(1);
                        handled = true;
                        break;
                    case HOTKEY_ID_CH2:
                        TestSwitch(2);
                        handled = true;
                        break;
                    case HOTKEY_ID_CH3:
                        TestSwitch(3);
                        handled = true;
                        break;
                }
            }
            return IntPtr.Zero;
        }

        private void SetupBorderCombos()
        {
            var combos = new[] { LeftBorderCombo, RightBorderCombo, TopBorderCombo, BottomBorderCombo };
            foreach (var cb in combos)
            {
                cb.Items.Clear();
                cb.Items.Add(new ComboBoxItem { Content = "Disabled", Tag = null });
                cb.Items.Add(new ComboBoxItem { Content = "Channel 1 (Slot 1)", Tag = 1 });
                cb.Items.Add(new ComboBoxItem { Content = "Channel 2 (Slot 2)", Tag = 2 });
                cb.Items.Add(new ComboBoxItem { Content = "Channel 3 (Slot 3)", Tag = 3 });
            }
        }

        private void LoadMonitors()
        {
            _monitors = MonitorManager.GetMonitors();
            MonitorSelectorCombo.Items.Clear();
            foreach (var m in _monitors)
            {
                MonitorSelectorCombo.Items.Add(new ComboBoxItem
                {
                    Content = m.Name,
                    Tag = m.Id
                });
            }

            if (MonitorSelectorCombo.Items.Count > 0)
            {
                MonitorSelectorCombo.SelectedIndex = 0;
            }
        }

        private void PopulateUiFromConfig()
        {
            HostNameBox.Text = _config.HostName;
            MyChannelCombo.SelectedIndex = Math.Clamp(_config.MyChannel - 1, 0, 2);

            ActiveZoneSlider.Value = _config.BorderActiveZonePct;
            ActiveZoneText.Text = $"{_config.BorderActiveZonePct}%";

            HoldDelaySlider.Value = _config.HoldDelayMs;
            HoldDelayText.Text = $"{_config.HoldDelayMs}ms";

            CooldownSlider.Value = _config.CooldownMs;
            CooldownText.Text = $"{_config.CooldownMs}ms";

            KnockEnabledCheck.IsChecked = _config.KnockEnabled;
            KnockTimeoutBox.Text = _config.KnockTimeoutMs.ToString();

            // Connection support
            var connMode = _config.ConnectionSupport.ToLowerInvariant();
            for (int i = 0; i < ConnectionSupportCombo.Items.Count; i++)
            {
                if (ConnectionSupportCombo.Items[i] is ComboBoxItem item &&
                    string.Equals(item.Tag?.ToString(), connMode, StringComparison.OrdinalIgnoreCase))
                {
                    ConnectionSupportCombo.SelectedIndex = i;
                    break;
                }
            }

            // Log level
            var lvl = _config.LogLevel.ToLowerInvariant();
            for (int i = 0; i < LogLevelCombo.Items.Count; i++)
            {
                if (LogLevelCombo.Items[i] is ComboBoxItem item &&
                    string.Equals(item.Tag?.ToString(), lvl, StringComparison.OrdinalIgnoreCase))
                {
                    LogLevelCombo.SelectedIndex = i;
                    break;
                }
            }

            // Bluetooth P2P
            BtEnabledCheck.IsChecked = _config.BtP2pEnabled;
            PeerMacBox.Text = _config.BtPeerAddress;
            RfcommPortBox.Text = _config.BtRfcommPort.ToString();

            var localMac = BluetoothPeer.GetLocalBluetoothMac();
            LocalMacBox.Text = string.IsNullOrEmpty(localMac) ? "(No adapter detected)" : localMac;
            SyncCursorCheck.IsChecked = _config.SyncCursorPosition;
            SyncClipboardCheck.IsChecked = _config.SyncClipboard;

            AutostartCheck.IsChecked = AppConfig.IsAutostartEnabled();

            UpdateMonitorUi(_selectedMonitorId);
        }

        private void UpdateMonitorUi(string monitorId)
        {
            var mCfg = _config.GetMonitorConfig(monitorId);
            MonitorEnabledCheck.IsChecked = mCfg?.Enabled ?? true;

            var edges = mCfg?.Edges;
            SetComboValue(LeftBorderCombo, edges != null && edges.TryGetValue("left", out var l) ? l : null);
            SetComboValue(RightBorderCombo, edges != null && edges.TryGetValue("right", out var r) ? r : null);
            SetComboValue(TopBorderCombo, edges != null && edges.TryGetValue("top", out var t) ? t : null);
            SetComboValue(BottomBorderCombo, edges != null && edges.TryGetValue("bottom", out var b) ? b : null);
        }

        private void SetComboValue(ComboBox combo, int? channel)
        {
            for (int i = 0; i < combo.Items.Count; i++)
            {
                if (combo.Items[i] is ComboBoxItem item)
                {
                    if (item.Tag == null && channel == null)
                    {
                        combo.SelectedIndex = i;
                        return;
                    }
                    if (item.Tag is int val && channel.HasValue && val == channel.Value)
                    {
                        combo.SelectedIndex = i;
                        return;
                    }
                }
            }
            combo.SelectedIndex = 0;
        }

        private int? GetComboValue(ComboBox combo)
        {
            if (combo.SelectedItem is ComboBoxItem item && item.Tag is int val)
            {
                return val;
            }
            return null;
        }

        private void SaveCurrentMonitorState()
        {
            if (_isLoadingConfig) return;

            var edges = new Dictionary<string, int?>
            {
                { "left", GetComboValue(LeftBorderCombo) },
                { "right", GetComboValue(RightBorderCombo) },
                { "top", GetComboValue(TopBorderCombo) },
                { "bottom", GetComboValue(BottomBorderCombo) }
            };

            bool enabled = MonitorEnabledCheck.IsChecked == true;
            _config.SetMonitorConfig(_selectedMonitorId, enabled, edges);
        }

        private void MonitorSelectorCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (_isLoadingConfig) return;

            SaveCurrentMonitorState();

            if (MonitorSelectorCombo.SelectedItem is ComboBoxItem item && item.Tag is string mid)
            {
                _selectedMonitorId = mid;
                UpdateMonitorUi(_selectedMonitorId);
            }
        }

        private void MonitorEnabledCheck_Changed(object sender, RoutedEventArgs e)
        {
            SaveCurrentMonitorState();
        }

        private void BorderCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            SaveCurrentMonitorState();
        }

        private void ActiveZoneSlider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (ActiveZoneText == null || _config == null) return;
            var val = (int)e.NewValue;
            ActiveZoneText.Text = $"{val}%";
            _config.BorderActiveZonePct = val;

            if (!_isLoadingConfig && _overlay != null && _monitors != null)
            {
                var edgesDict = new Dictionary<string, List<string>>();
                var active = _config.GetAllActiveMonitorBorders();
                foreach (var (mid, edge, _) in active)
                {
                    if (!edgesDict.ContainsKey(mid)) edgesDict[mid] = new List<string>();
                    edgesDict[mid].Add(edge);
                }

                if (edgesDict.Count == 0)
                {
                    edgesDict[_selectedMonitorId] = new List<string> { "left", "right", "top", "bottom" };
                }

                _overlay.ShowBorders(val, _monitors, edgesDict);
            }
        }

        private void HoldDelaySlider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (HoldDelayText == null || _config == null) return;
            var val = (int)e.NewValue;
            HoldDelayText.Text = $"{val}ms";
            _config.HoldDelayMs = val;
        }

        private void CooldownSlider_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (CooldownText == null || _config == null) return;
            var val = (int)e.NewValue;
            CooldownText.Text = $"{val}ms";
            _config.CooldownMs = val;
        }

        private void ToggleServiceBtn_Click(object sender, RoutedEventArgs e)
        {
            if (_service.IsRunning)
            {
                _service.Stop();
            }
            else
            {
                SaveConfigInternal();
                _service.ReloadConfig(_config);
                _service.Start();
            }
        }

        private void OnServiceStateChanged(bool isRunning)
        {
            Dispatcher.InvokeAsync(() =>
            {
                if (isRunning)
                {
                    StatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#16A34A"));
                    StatusText.Text = "RUNNING";
                    StatusText.Foreground = System.Windows.Media.Brushes.White;
                    ToggleServiceBtn.Content = "Stop Service";
                }
                else
                {
                    StatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#DC2626"));
                    StatusText.Text = "STOPPED";
                    StatusText.Foreground = System.Windows.Media.Brushes.White;
                    ToggleServiceBtn.Content = "Start Service";
                }
            });
        }

        private void SaveConfig_Click(object sender, RoutedEventArgs e)
        {
            SaveConfigInternal();
            _service.ReloadConfig(_config);
            SaveStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(ThemeManager.IsDark ? "#4ADE80" : "#15803D"));
            SaveStatusText.Text = "✓ Saved";
            var timer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromSeconds(3) };
            timer.Tick += (s, ev) =>
            {
                SaveStatusText.Text = "";
                timer.Stop();
            };
            timer.Start();
        }

        private void SaveConfigInternal()
        {
            SaveCurrentMonitorState();

            _config.HostName = HostNameBox.Text.Trim();
            _config.MyChannel = MyChannelCombo.SelectedIndex + 1;
            _config.BorderActiveZonePct = (int)ActiveZoneSlider.Value;
            _config.HoldDelayMs = (int)HoldDelaySlider.Value;
            _config.CooldownMs = (int)CooldownSlider.Value;
            _config.KnockEnabled = KnockEnabledCheck.IsChecked == true;

            if (int.TryParse(KnockTimeoutBox.Text, out var kt))
                _config.KnockTimeoutMs = kt;

            if (ConnectionSupportCombo.SelectedItem is ComboBoxItem connItem && connItem.Tag is string cm)
                _config.ConnectionSupport = cm;

            if (LogLevelCombo.SelectedItem is ComboBoxItem logItem && logItem.Tag is string lm)
                _config.LogLevel = lm;

            _config.BtP2pEnabled = BtEnabledCheck.IsChecked == true;
            _config.BtPeerAddress = PeerMacBox.Text.Trim();
            if (int.TryParse(RfcommPortBox.Text, out var port))
                _config.BtRfcommPort = port;

            _config.SyncCursorPosition = SyncCursorCheck.IsChecked == true;
            _config.SyncClipboard = SyncClipboardCheck.IsChecked == true;

            _config.Autostart = AutostartCheck.IsChecked == true;
            AppConfig.SetAutostart(_config.Autostart);

            _config.Save();
        }

        private void RefreshDevicesBtn_Click(object sender, RoutedEventArgs e)
        {
            RefreshDevicesAsync();
        }

        private async void RefreshDevicesAsync()
        {
            try
            {
                DevicesCountText.Text = "Scanning devices...";
                RefreshDevicesBtn.IsEnabled = false;

                var connSupport = (ConnectionSupportCombo.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "both";
                var devices = await Task.Run(() => _service.Hidpp.ScanDevices(_config.Devices, forceRescan: true, connectionSupport: connSupport));

                DevicesList.Items.Clear();
                foreach (var dev in devices)
                {
                    var panel = new StackPanel { Margin = new Thickness(0, 4, 0, 4) };
                    panel.Children.Add(new TextBlock
                    {
                        Text = dev.Name,
                        FontWeight = FontWeights.SemiBold,
                        Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(ThemeManager.IsDark ? "#38BDF8" : "#0284C7"))
                    });
                    panel.Children.Add(new TextBlock
                    {
                        Text = $"Transport: {dev.Transport}  |  Slot Index: 0x{dev.DeviceIndex:X2}  |  ChangeHost Feature: 0x{dev.ChangeHostFeatureIndex:X2}  |  PID: 0x{dev.Pid:X4}",
                        FontSize = 11,
                        Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(ThemeManager.IsDark ? "#94A3B8" : "#334155"))
                    });
                    DevicesList.Items.Add(panel);
                }

                DevicesCountText.Text = $"{devices.Count} device(s) connected";
            }
            catch (Exception ex)
            {
                AppLogger.Log("GUI", $"Error refreshing devices: {ex.Message}");
                DevicesCountText.Text = "Scan error";
            }
            finally
            {
                RefreshDevicesBtn.IsEnabled = true;
            }
        }

        private async void TestSwitch(int channel)
        {
            AppLogger.Log("GUI", $"Initiating manual test switch to Channel {channel}...");
            await Task.Run(() => _service.Hidpp.SwitchAllToChannel(channel, _config.Devices));
        }

        private void TestSwitch1_Click(object sender, RoutedEventArgs e) => TestSwitch(1);
        private void TestSwitch2_Click(object sender, RoutedEventArgs e) => TestSwitch(2);
        private void TestSwitch3_Click(object sender, RoutedEventArgs e) => TestSwitch(3);

        private void ClearLogs_Click(object sender, RoutedEventArgs e)
        {
            LogsBox.Text = string.Empty;
        }

        private void CopyLogs_Click(object sender, RoutedEventArgs e)
        {
            ClipboardHelper.SetText(LogsBox.Text);
            CopyLogsBtn.Content = "✓ Copied";
            var timer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
            timer.Tick += (s, ev) =>
            {
                CopyLogsBtn.Content = "Copy Logs";
                timer.Stop();
            };
            timer.Start();
        }

        private void OnLogReceived(string logLine)
        {
            Dispatcher.InvokeAsync(() =>
            {
                LogsBox.AppendText(logLine + "\n");
                LogsBox.ScrollToEnd();
            });
        }

        private void OnBtAdvertisingStateChanged(bool isAdvertising, int remainingSeconds)
        {
            Dispatcher.InvokeAsync(() =>
            {
                if (isAdvertising)
                {
                    ToggleAdvBtn.Content = "Stop Advertising";
                    AdvStatusText.Text = $"Advertising ({remainingSeconds}s remaining)...";
                    AdvStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(ThemeManager.IsDark ? "#4ADE80" : "#15803D"));
                }
                else
                {
                    ToggleAdvBtn.Content = "Advertise Lunifier";
                    AdvStatusText.Text = "Idle";
                    AdvStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(ThemeManager.IsDark ? "#94A3B8" : "#334155"));
                }
            });
        }

        private void CopyLocalMacBtn_Click(object sender, RoutedEventArgs e)
        {
            var mac = LocalMacBox.Text.Trim();
            if (!string.IsNullOrEmpty(mac) && !mac.StartsWith("("))
            {
                System.Windows.Clipboard.SetText(mac);
                CopyLocalMacBtn.Content = "✓ Copied";
                var timer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
                timer.Tick += (s, ev) =>
                {
                    CopyLocalMacBtn.Content = "Copy";
                    timer.Stop();
                };
                timer.Start();
            }
        }

        private void ToggleAdvBtn_Click(object sender, RoutedEventArgs e)
        {
            if (_service.BtPeer == null) return;

            if (_service.BtPeer.IsAdvertising)
            {
                _service.BtPeer.StopAdvertising();
            }
            else
            {
                int duration = 60;
                if (AdvDurationCombo.SelectedItem is ComboBoxItem item &&
                    int.TryParse(item.Tag?.ToString(), out var parsedDuration))
                {
                    duration = parsedDuration;
                }
                _service.BtPeer.StartAdvertising(duration);
            }
        }

        private async void ScanBtHostsBtn_Click(object sender, RoutedEventArgs e)
        {
            if (_service.BtPeer == null) return;

            ScanBtHostsBtn.IsEnabled = false;
            BtScanStatusText.Text = "Scanning Bluetooth devices for Lunifier hosts...";
            DiscoveredPeersList.Items.Clear();

            try
            {
                var peers = await _service.BtPeer.ScanLunifierPeersAsync(timeoutSeconds: 4.0);
                if (peers.Count == 0)
                {
                    BtScanStatusText.Text = "No advertising Lunifier hosts found.";
                }
                else
                {
                    BtScanStatusText.Text = $"Found {peers.Count} advertising Lunifier host(s):";
                    foreach (var p in peers)
                    {
                        var panel = new Grid { Margin = new Thickness(0, 4, 0, 4) };
                        panel.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                        panel.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

                        var info = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
                        info.Children.Add(new TextBlock
                        {
                            Text = string.IsNullOrEmpty(p.Name) ? "Lunifier Host" : p.Name,
                            FontWeight = FontWeights.Bold,
                            Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(ThemeManager.IsDark ? "#38BDF8" : "#0284C7"))
                        });
                        info.Children.Add(new TextBlock
                        {
                            Text = $"MAC: {p.MacAddress}  |  Port: {p.Port}  |  Token: {p.AdvertisingToken}",
                            FontSize = 11,
                            Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(ThemeManager.IsDark ? "#94A3B8" : "#334155"))
                        });
                        Grid.SetColumn(info, 0);
                        panel.Children.Add(info);

                        var pairBtn = new Button
                        {
                            Content = "Pair & Connect",
                            Width = 120,
                            Height = 32,
                            Margin = new Thickness(8, 0, 0, 0),
                            Tag = p
                        };
                        pairBtn.Click += PairPeerBtn_Click;
                        Grid.SetColumn(pairBtn, 1);
                        panel.Children.Add(pairBtn);

                        DiscoveredPeersList.Items.Add(panel);
                    }
                }
            }
            catch (Exception ex)
            {
                AppLogger.Log("GUI", $"Bluetooth scan error: {ex.Message}");
                BtScanStatusText.Text = "Scan error: " + ex.Message;
            }
            finally
            {
                ScanBtHostsBtn.IsEnabled = true;
            }
        }

        private async void PairPeerBtn_Click(object sender, RoutedEventArgs e)
        {
            if (sender is Button btn && btn.Tag is DiscoveredPeer peer && _service.BtPeer != null)
            {
                btn.IsEnabled = false;
                btn.Content = "Pairing...";
                AppLogger.Log("GUI", $"Requesting pairing with {peer.Name} ({peer.MacAddress}) on port {peer.Port}...");

                try
                {
                    var (success, reason) = await _service.BtPeer.RequestPairingAsync(peer.MacAddress, peer.AdvertisingToken, peer.Port);
                    if (success)
                    {
                        PeerMacBox.Text = peer.MacAddress;
                        RfcommPortBox.Text = peer.Port.ToString();
                        _config.BtRfcommPort = peer.Port;
                        BtEnabledCheck.IsChecked = true;
                        SaveConfigInternal();
                        _service.ReloadConfig(_config);
                        _service.BtPeer.Start();

                        btn.Content = "✓ Paired";
                        BtScanStatusText.Text = $"✓ Paired with {peer.Name} ({peer.MacAddress}) on port {peer.Port}. Link active!";
                        BtScanStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(ThemeManager.IsDark ? "#4ADE80" : "#15803D"));
                    }
                    else
                    {
                        btn.Content = "Failed";
                        BtScanStatusText.Text = $"Pairing with {peer.MacAddress} failed: {reason}. Ensure advertising is active.";
                        BtScanStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(ThemeManager.IsDark ? "#F87171" : "#DC2626"));
                    }
                }
                catch (Exception ex)
                {
                    AppLogger.Log("GUI", $"Pairing exception: {ex.Message}");
                    btn.Content = "Error";
                    BtScanStatusText.Text = $"Pairing error: {ex.Message}";
                    BtScanStatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString(ThemeManager.IsDark ? "#F87171" : "#DC2626"));
                }
                finally
                {
                    btn.IsEnabled = true;
                }
            }
        }

        private void VisitGitHub_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = "https://github.com/silviuk/Lunifier",
                    UseShellExecute = true
                });
            }
            catch { }
        }
    }
}
