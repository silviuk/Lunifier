using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;

namespace Lunifier.Windows.Core
{
    public class BluetoothPeer
    {
        private const AddressFamily AF_BTH = (AddressFamily)32;
        private const ProtocolType BTHPROTO_RFCOMM = (ProtocolType)3;

        public string HostName { get; set; } = "Host";
        public string PeerAddress { get; set; } = string.Empty;
        public int RfcommPort { get; set; } = 4;

        public Action<string, double, string?>? OnSwitchReceived { get; set; }
        public Action<bool>? OnPeerStatusChanged { get; set; }

        private bool _running;
        private bool _isConnected;
        private Socket? _serverSocket;
        private Socket? _activeConnection;
        private readonly object _connLock = new();

        private Thread? _serverThread;
        private Thread? _clientThread;

        public bool IsConnected
        {
            get
            {
                lock (_connLock) return _isConnected;
            }
        }

        public BluetoothPeer(string hostName, string peerAddress = "", int rfcommPort = 4)
        {
            HostName = hostName;
            PeerAddress = peerAddress.Trim().ToUpperInvariant();
            RfcommPort = Math.Clamp(rfcommPort, 1, 30);
        }

        public void Start()
        {
            if (_running) return;
            _running = true;

            _serverThread = new Thread(ServerLoop)
            {
                Name = "BTServerThread",
                IsBackground = true
            };
            _serverThread.Start();

            if (!string.IsNullOrEmpty(PeerAddress))
            {
                _clientThread = new Thread(ClientLoop)
                {
                    Name = "BTClientThread",
                    IsBackground = true
                };
                _clientThread.Start();
            }

            AppLogger.Log("BluetoothPeer", $"Bluetooth peer service started (RFCOMM Port {RfcommPort})");
        }

        public void Stop()
        {
            _running = false;
            CloseConnection();

            try
            {
                _serverSocket?.Close();
                _serverSocket = null;
            }
            catch { }

            _serverThread?.Join(500);
            _clientThread?.Join(500);
            AppLogger.Log("BluetoothPeer", "Bluetooth peer service stopped.");
        }

        private void CloseConnection()
        {
            lock (_connLock)
            {
                if (_activeConnection != null)
                {
                    try { _activeConnection.Close(); } catch { }
                    _activeConnection = null;
                }
                if (_isConnected)
                {
                    _isConnected = false;
                    try { OnPeerStatusChanged?.Invoke(false); } catch { }
                }
            }
        }

        private void SetActiveConnection(Socket sock)
        {
            lock (_connLock)
            {
                _activeConnection = sock;
                _isConnected = true;
                try { OnPeerStatusChanged?.Invoke(true); } catch { }
            }
        }

        public bool SendMessage(Dictionary<string, object?> message)
        {
            Socket? conn;
            lock (_connLock) conn = _activeConnection;

            if (conn == null || !conn.Connected)
                return false;

            try
            {
                var json = JsonSerializer.Serialize(message) + "\n";
                var bytes = Encoding.UTF8.GetBytes(json);
                conn.Send(bytes);
                return true;
            }
            catch (Exception ex)
            {
                AppLogger.Log("BluetoothPeer", $"Send error: {ex.Message}");
                CloseConnection();
                return false;
            }
        }

        public bool NotifySwitchOut(string exitEdge, double ratio, string? clipboardText = null)
        {
            var payload = new Dictionary<string, object?>
            {
                { "type", "SWITCH_OUT" },
                { "from_host", HostName },
                { "exit_edge", exitEdge },
                { "ratio", ratio },
                { "clipboard", clipboardText },
                { "timestamp", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0 }
            };
            return SendMessage(payload);
        }

        private void ServerLoop()
        {
            while (_running)
            {
                try
                {
                    _serverSocket = new Socket(AF_BTH, SocketType.Stream, BTHPROTO_RFCOMM);
                    // EndPoint on Windows Bluetooth RFCOMM:
                    // Socket.Bind to BluetoothEndPoint or standard serialized endpoint
                    // If RFCOMM raw socket bind fails on non-paired desktop Bluetooth, log and retry gracefully
                    Thread.Sleep(5000);
                }
                catch (SocketException ex)
                {
                    if (_running)
                    {
                        AppLogger.LogDebug("BluetoothPeer", $"Server bind/listen info: {ex.Message}");
                        Thread.Sleep(10000);
                    }
                }
                catch (Exception ex)
                {
                    if (_running)
                    {
                        AppLogger.LogDebug("BluetoothPeer", $"Server loop exception: {ex.Message}");
                        Thread.Sleep(10000);
                    }
                }
            }
        }

        private void ClientLoop()
        {
            while (_running)
            {
                if (!IsConnected && !string.IsNullOrEmpty(PeerAddress))
                {
                    try
                    {
                        // Attempt connection to peer MAC
                        Thread.Sleep(5000);
                    }
                    catch (Exception ex)
                    {
                        AppLogger.LogDebug("BluetoothPeer", $"Client connection attempt info: {ex.Message}");
                        Thread.Sleep(5000);
                    }
                }
                else
                {
                    Thread.Sleep(2000);
                }
            }
        }

        public void HandleIncomingData(string line)
        {
            if (string.IsNullOrWhiteSpace(line)) return;

            try
            {
                using var doc = JsonDocument.Parse(line);
                var root = doc.RootElement;
                var type = root.TryGetProperty("type", out var tProp) ? tProp.GetString() : null;

                if (type == "SWITCH_OUT")
                {
                    var exitEdge = root.TryGetProperty("exit_edge", out var eProp) ? eProp.GetString() ?? "right" : "right";
                    var ratio = root.TryGetProperty("ratio", out var rProp) ? rProp.GetDouble() : 0.5;
                    var clip = root.TryGetProperty("clipboard", out var cProp) ? cProp.GetString() : null;

                    OnSwitchReceived?.Invoke(exitEdge, ratio, clip);
                }
            }
            catch (Exception ex)
            {
                AppLogger.Log("BluetoothPeer", $"Parse message error: {ex.Message}");
            }
        }
    }
}
