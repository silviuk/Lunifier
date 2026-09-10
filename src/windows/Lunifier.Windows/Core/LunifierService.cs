using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading.Tasks;
using Lunifier.Windows.Config;

namespace Lunifier.Windows.Core
{
    public class LunifierService
    {
        public AppConfig Config { get; private set; }
        public HidppEngine Hidpp { get; } = new();
        public EdgeDetector? Detector { get; private set; }
        public BluetoothPeer? BtPeer { get; private set; }

        public bool IsRunning { get; private set; }

        public event Action<bool>? StateChanged;

        public LunifierService(AppConfig? config = null)
        {
            Config = config ?? AppConfig.Load();
            SetupSubsystems();
        }

        public void ReloadConfig(AppConfig config)
        {
            Config = config;
            SetupSubsystems();
        }

        private void SetupSubsystems()
        {
            Hidpp.ConnectionSupport = Config.ConnectionSupport;

            if (Detector != null)
            {
                Detector.Stop();
                Detector = null;
            }

            Detector = new EdgeDetector(Config, OnEdgeTriggered);

            if (BtPeer != null)
            {
                BtPeer.Stop();
                BtPeer = null;
            }

            if (Config.BtP2pEnabled || !string.IsNullOrEmpty(Config.BtPeerAddress))
            {
                BtPeer = new BluetoothPeer(Config.HostName, Config.BtPeerAddress, Config.BtRfcommPort)
                {
                    OnSwitchReceived = OnIncomingSwitch,
                    OnPeerStatusChanged = connected =>
                    {
                        AppLogger.Log("Lunifier", $"Partner host Bluetooth link: {(connected ? "CONNECTED" : "DISCONNECTED")}");
                    }
                };
            }

            // Warm up device cache in background
            Task.Run(() => Hidpp.ScanDevices(Config.Devices, forceRescan: true, connectionSupport: Config.ConnectionSupport));
        }

        public void Start()
        {
            if (IsRunning) return;
            IsRunning = true;

            Detector?.Start();
            BtPeer?.Start();

            AppLogger.Log("Lunifier", "==================================================");
            AppLogger.Log("Lunifier", " Lunifier Windows Service Running");
            AppLogger.Log("Lunifier", $" Host: {Config.HostName} (Channel {Config.MyChannel})");
            AppLogger.Log("Lunifier", $" Active Border Zone: Central {Config.BorderActiveZonePct}%");
            AppLogger.Log("Lunifier", $" Knock Mode: {(Config.KnockEnabled ? $"ENABLED ({Config.KnockTimeoutMs}ms)" : "DISABLED")}");
            AppLogger.Log("Lunifier", "==================================================");

            StateChanged?.Invoke(true);
        }

        public void Stop()
        {
            if (!IsRunning) return;
            IsRunning = false;

            Detector?.Stop();
            BtPeer?.Stop();

            AppLogger.Log("Lunifier", "Lunifier Windows Service Stopped.");
            StateChanged?.Invoke(false);
        }

        private void OnEdgeTriggered(string edge, int x, int y, double ratio, string monitorId, int targetChannel)
        {
            AppLogger.Log("Lunifier", $">>> SCREEN BORDER REACHED: '{edge.ToUpperInvariant()}' on Monitor {monitorId} at ({x}, {y}) (Ratio: {ratio:F2}) <<<");
            AppLogger.Log("Lunifier", $"Instantly switching devices to Channel {targetChannel} (Support: {Config.ConnectionSupport})...");

            var t0 = Stopwatch.GetTimestamp();
            var results = Hidpp.SwitchAllToChannel(targetChannel, Config.Devices);
            var elapsed = (Stopwatch.GetTimestamp() - t0) * 1000.0 / Stopwatch.Frequency;

            foreach (var (devName, success) in results)
            {
                AppLogger.Log("Lunifier", $"Device '{devName}' -> Channel {targetChannel}: {(success ? "SUCCESS" : "FAILED")}");
            }
            AppLogger.Log("Lunifier", $"Hardware switch sequence completed in {elapsed:F1}ms");

            // Async notify peer over Bluetooth
            if (BtPeer != null && BtPeer.IsConnected)
            {
                Task.Run(() =>
                {
                    string? clip = Config.SyncClipboard ? ClipboardHelper.GetText() : null;
                    BtPeer.NotifySwitchOut(edge, ratio, clip);
                });
            }

            // Step cursor inward
            const int stepBack = 160;
            int newX = x;
            int newY = y;
            switch (edge.ToLowerInvariant())
            {
                case "right": newX = x - stepBack; break;
                case "left": newX = x + stepBack; break;
                case "top": newY = y + stepBack; break;
                case "bottom": newY = y - stepBack; break;
            }

            CursorHelper.SetPosition(newX, newY);
            Detector?.NotifySwitchedOut(edge, newX, newY);
            AppLogger.Log("Lunifier", $"Repositioned cursor {stepBack}px inward to ({newX}, {newY}) to prevent border bounceback");
        }

        private void OnIncomingSwitch(string partnerExitEdge, double ratio, string? clipboardText)
        {
            AppLogger.Log("Lunifier", $"<<< INCOMING TRANSFER from partner (Exit Edge: '{partnerExitEdge}', Ratio: {ratio:F2}) <<<");

            if (Config.SyncClipboard && !string.IsNullOrEmpty(clipboardText))
            {
                var ok = ClipboardHelper.SetText(clipboardText);
                AppLogger.Log("Lunifier", $"Updated local clipboard from partner: {(ok ? "OK" : "FAILED")}");
            }

            var bounds = MonitorManager.GetVirtualDesktopBounds(MonitorManager.GetMonitors());
            var entryEdge = Config.EntryEdge;
            if (string.IsNullOrEmpty(entryEdge))
            {
                entryEdge = partnerExitEdge.ToLowerInvariant() switch
                {
                    "right" => "left",
                    "left" => "right",
                    "top" => "bottom",
                    "bottom" => "top",
                    _ => "left"
                };
            }

            CursorHelper.PositionAtEntry(entryEdge, ratio, bounds);
            Detector?.NotifySwitchedIn(entryEdge);
        }
    }
}
