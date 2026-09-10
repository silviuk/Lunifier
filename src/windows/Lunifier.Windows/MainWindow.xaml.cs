using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Lunifier.Windows.Config;
using Lunifier.Windows.Core;

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

        public MainWindow()
        {
            _config = AppConfig.Load();
            _service = new LunifierService(_config);

            InitializeComponent();

            _service.StateChanged += OnServiceStateChanged;
            AppLogger.LogReceived += OnLogReceived;

            Loaded += MainWindow_Loaded;
            Closing += MainWindow_Closing;
        }

        private void MainWindow_Loaded(object sender, RoutedEventArgs e)
        {
            try
            {
                _overlay = new BorderOverlayWindow { Owner = this };
                SetupBorderCombos();
                LoadMonitors();
                PopulateUiFromConfig();
                _isLoadingConfig = false;

                // Trigger initial device scan in background
                RefreshDevicesAsync();
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
            _service.Stop();
            try { _overlay?.Close(); } catch { }
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
            SyncCursorCheck.IsChecked = _config.SyncCursorPosition;
            SyncClipboardCheck.IsChecked = _config.SyncClipboard;

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
                    StatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#1B5E20"));
                    StatusText.Text = "RUNNING";
                    StatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#81C784"));
                    ToggleServiceBtn.Content = "Stop Service";
                }
                else
                {
                    StatusBadge.Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#3E2723"));
                    StatusText.Text = "STOPPED";
                    StatusText.Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#EF5350"));
                    ToggleServiceBtn.Content = "Start Service";
                }
            });
        }

        private void SaveConfig_Click(object sender, RoutedEventArgs e)
        {
            SaveConfigInternal();
            _service.ReloadConfig(_config);
            MessageBox.Show("Configuration saved successfully.", "Lunifier", MessageBoxButton.OK, MessageBoxImage.Information);
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
                        Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#38BDF8"))
                    });
                    panel.Children.Add(new TextBlock
                    {
                        Text = $"Transport: {dev.Transport}  |  Slot Index: 0x{dev.DeviceIndex:X2}  |  ChangeHost Feature: 0x{dev.ChangeHostFeatureIndex:X2}  |  PID: 0x{dev.Pid:X4}",
                        FontSize = 11,
                        Foreground = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#94A3B8"))
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
            MessageBox.Show("Logs copied to clipboard.", "Lunifier", MessageBoxButton.OK, MessageBoxImage.Information);
        }

        private void OnLogReceived(string logLine)
        {
            Dispatcher.InvokeAsync(() =>
            {
                LogsBox.AppendText(logLine + "\n");
                LogsBox.ScrollToEnd();
            });
        }
    }
}
