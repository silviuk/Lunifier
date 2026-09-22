using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Win32;

namespace Lunifier.Windows.Core
{
    public class DiscoveredPeer
    {
        public string Name { get; set; } = string.Empty;
        public string MacAddress { get; set; } = string.Empty;
        public string AdvertisingToken { get; set; } = string.Empty;
        public bool IsAdvertising { get; set; } = true;
    }

    public class BluetoothEndPoint : EndPoint
    {
        public ulong Address { get; }
        public int Port { get; }

        public BluetoothEndPoint(ulong address, int port)
        {
            Address = address;
            Port = port;
        }

        public override AddressFamily AddressFamily => (AddressFamily)32;

        public override SocketAddress Serialize()
        {
            var sa = new SocketAddress(AddressFamily, 30);
            var addrBytes = BitConverter.GetBytes(Address);
            for (int i = 0; i < 8; i++) sa[2 + i] = addrBytes[i];
            var portBytes = BitConverter.GetBytes((uint)Port);
            for (int i = 0; i < 4; i++) sa[26 + i] = portBytes[i];
            return sa;
        }

        public override EndPoint Create(SocketAddress socketAddress)
        {
            byte[] addrBuf = new byte[8];
            for (int i = 0; i < 8; i++) addrBuf[i] = socketAddress[2 + i];
            ulong addr = BitConverter.ToUInt64(addrBuf, 0);

            byte[] portBuf = new byte[4];
            for (int i = 0; i < 4; i++) portBuf[i] = socketAddress[26 + i];
            uint port = BitConverter.ToUInt32(portBuf, 0);

            return new BluetoothEndPoint(addr, (int)port);
        }

        public static ulong ParseMac(string mac)
        {
            var hex = mac.Replace(":", "").Replace("-", "").Trim();
            if (ulong.TryParse(hex, System.Globalization.NumberStyles.HexNumber, null, out var val))
                return val;
            return 0;
        }

        public static string FormatMac(ulong addr)
        {
            var bytes = BitConverter.GetBytes(addr);
            return $"{bytes[5]:X2}:{bytes[4]:X2}:{bytes[3]:X2}:{bytes[2]:X2}:{bytes[1]:X2}:{bytes[0]:X2}";
        }
    }

    public class BluetoothPeer
    {
        private const AddressFamily AF_BTH = (AddressFamily)32;
        private const ProtocolType BTHPROTO_RFCOMM = (ProtocolType)3;

        public string HostName { get; set; } = "Host";
        public string PeerAddress { get; set; } = string.Empty;
        public int RfcommPort { get; set; } = 4;

        public Action<string, double, string?>? OnSwitchReceived { get; set; }
        public Action<bool>? OnPeerStatusChanged { get; set; }
        public Action<bool, int>? OnAdvertisingStateChanged { get; set; }
        public Action<bool, string, string?>? OnPairResponse { get; set; }
        public Action<string>? OnClipboardReceived { get; set; }
        public Action<Dictionary<string, int>>? OnAlignmentReceived { get; set; }

        private static string? _cachedLocalMac;

        public static string GetLocalBluetoothMac()
        {
            if (!string.IsNullOrEmpty(_cachedLocalMac)) return _cachedLocalMac;

            try
            {
                using var sock = new Socket(AF_BTH, SocketType.Stream, BTHPROTO_RFCOMM);
                var ep = new BluetoothEndPoint(0, 0);
                sock.Bind(ep);
                if (sock.LocalEndPoint is BluetoothEndPoint localEp && localEp.Address != 0)
                {
                    _cachedLocalMac = BluetoothEndPoint.FormatMac(localEp.Address);
                    return _cachedLocalMac;
                }
            }
            catch { }

            return string.Empty;
        }

        private bool _running;
        private bool _isConnected;
        private Socket? _serverSocket;
        private Socket? _activeConnection;
        private readonly object _connLock = new();

        private Thread? _serverThread;
        private Thread? _clientThread;

        // Timed Advertising State
        private bool _isAdvertising;
        private int _advRemainingSeconds;
        private string _advToken = string.Empty;
        private System.Threading.Timer? _advTimer;
        private readonly object _advLock = new();

        public bool IsConnected
        {
            get
            {
                lock (_connLock) return _isConnected;
            }
        }

        public bool IsAdvertising
        {
            get
            {
                lock (_advLock) return _isAdvertising;
            }
        }

        public int AdvertisingRemainingSeconds
        {
            get
            {
                lock (_advLock) return _advRemainingSeconds;
            }
        }

        public string AdvertisingToken
        {
            get
            {
                lock (_advLock) return _advToken;
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
            StopAdvertising();
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

        public void StartAdvertising(int durationSeconds = 60)
        {
            if (!_running)
            {
                Start();
            }

            lock (_advLock)
            {
                _advToken = Guid.NewGuid().ToString("N")[..8].ToUpperInvariant();
                _advRemainingSeconds = Math.Max(10, durationSeconds);
                _isAdvertising = true;

                _advTimer?.Dispose();
                _advTimer = new System.Threading.Timer(OnAdvTimerTick, null, 1000, 1000);

                AppLogger.Log("BluetoothPeer", $"Bluetooth advertising STARTED for {_advRemainingSeconds}s (Token: {_advToken})");
                OnAdvertisingStateChanged?.Invoke(true, _advRemainingSeconds);
            }
        }

        public void StopAdvertising()
        {
            lock (_advLock)
            {
                if (!_isAdvertising) return;
                _isAdvertising = false;
                _advRemainingSeconds = 0;
                _advTimer?.Dispose();
                _advTimer = null;
                _advToken = string.Empty;

                AppLogger.Log("BluetoothPeer", "Bluetooth advertising stopped/expired.");
                OnAdvertisingStateChanged?.Invoke(false, 0);
            }
        }

        private void OnAdvTimerTick(object? state)
        {
            lock (_advLock)
            {
                if (!_isAdvertising) return;
                _advRemainingSeconds--;
                if (_advRemainingSeconds <= 0)
                {
                    StopAdvertising();
                }
                else
                {
                    OnAdvertisingStateChanged?.Invoke(true, _advRemainingSeconds);
                }
            }
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

        public bool SendClipboardText(string text)
        {
            var payload = new Dictionary<string, object?>
            {
                { "type", "CLIPBOARD_SYNC" },
                { "clipboard", text },
                { "timestamp", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0 }
            };
            return SendMessage(payload);
        }

        public bool SendAlignmentBounds(Dictionary<string, int> bounds)
        {
            var payload = new Dictionary<string, object?>
            {
                { "type", "ALIGNMENT_EXCHANGE" },
                { "screen_bounds", bounds },
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
                    var ep = new BluetoothEndPoint(0, RfcommPort);
                    _serverSocket.Bind(ep);
                    _serverSocket.Listen(4);

                    AppLogger.Log("BluetoothPeer", $"Listening for incoming Bluetooth RFCOMM on port {RfcommPort}...");

                    while (_running)
                    {
                        var clientSock = _serverSocket.Accept();
                        ThreadPool.QueueUserWorkItem(_ => HandleIncomingClient(clientSock));
                    }
                }
                catch (SocketException ex)
                {
                    if (_running)
                    {
                        AppLogger.LogDebug("BluetoothPeer", $"Server bind/listen info: {ex.Message}");
                        Thread.Sleep(5000);
                    }
                }
                catch (Exception ex)
                {
                    if (_running)
                    {
                        AppLogger.LogDebug("BluetoothPeer", $"Server loop exception: {ex.Message}");
                        Thread.Sleep(5000);
                    }
                }
                finally
                {
                    try { _serverSocket?.Close(); } catch { }
                    _serverSocket = null;
                }
            }
        }

        private void HandleIncomingClient(Socket client)
        {
            var isPairedSession = false;
            try
            {
                using var stream = new NetworkStream(client, false);
                using var reader = new StreamReader(stream, Encoding.UTF8);

                while (_running && client.Connected)
                {
                    var line = reader.ReadLine();
                    if (line == null) break;
                    line = line.Trim();
                    if (string.IsNullOrEmpty(line)) continue;

                    using var doc = JsonDocument.Parse(line);
                    var root = doc.RootElement;
                    var type = root.TryGetProperty("type", out var tProp) ? tProp.GetString() : null;

                    if (type == "PROBE_ADV")
                    {
                        // Discovery probe response
                        var reply = new Dictionary<string, object?>
                        {
                            { "type", "PROBE_REPLY" },
                            { "from_host", HostName },
                            { "is_advertising", IsAdvertising },
                            { "token", IsAdvertising ? AdvertisingToken : "" }
                        };
                        var json = JsonSerializer.Serialize(reply) + "\n";
                        client.Send(Encoding.UTF8.GetBytes(json));
                    }
                    else if (type == "PAIR_REQUEST")
                    {
                        var fromHost = root.TryGetProperty("from_host", out var fh) ? fh.GetString() ?? "Partner Host" : "Partner Host";
                        var token = root.TryGetProperty("token", out var tk) ? tk.GetString() ?? "" : "";

                        bool accepted = false;
                        if (IsAdvertising)
                        {
                            if (string.IsNullOrEmpty(AdvertisingToken) || token == AdvertisingToken)
                            {
                                accepted = true;
                                AppLogger.Log("BluetoothPeer", $"Accepted pairing from '{fromHost}' with valid advertising token.");
                            }
                        }

                        if (accepted)
                        {
                            var reply = new Dictionary<string, object?>
                            {
                                { "type", "PAIR_ACCEPT" },
                                { "from_host", HostName },
                                { "session_key", Guid.NewGuid().ToString("N") },
                                { "timestamp", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0 }
                            };
                            var json = JsonSerializer.Serialize(reply) + "\n";
                            client.Send(Encoding.UTF8.GetBytes(json));

                            SetActiveConnection(client);
                            isPairedSession = true;
                        }
                        else
                        {
                            var reply = new Dictionary<string, object?>
                            {
                                { "type", "PAIR_REJECT" },
                                { "from_host", HostName },
                                { "reason", "Host is not in advertising mode or token is invalid" }
                            };
                            var json = JsonSerializer.Serialize(reply) + "\n";
                            client.Send(Encoding.UTF8.GetBytes(json));
                            break;
                        }
                    }
                    else
                    {
                        ProcessMessage(root);
                    }
                }
            }
            catch (Exception ex)
            {
                AppLogger.LogDebug("BluetoothPeer", $"Incoming client connection ended: {ex.Message}");
            }
            finally
            {
                if (isPairedSession)
                {
                    CloseConnection();
                }
                else
                {
                    try { client.Close(); } catch { }
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
                        ulong mac = BluetoothEndPoint.ParseMac(PeerAddress);
                        if (mac != 0)
                        {
                            var sock = new Socket(AF_BTH, SocketType.Stream, BTHPROTO_RFCOMM);
                            var ep = new BluetoothEndPoint(mac, RfcommPort);
                            sock.Connect(ep);

                            AppLogger.Log("BluetoothPeer", $"Connected to partner at {PeerAddress}");
                            SetActiveConnection(sock);

                            using var stream = new NetworkStream(sock, false);
                            using var reader = new StreamReader(stream, Encoding.UTF8);

                            while (_running && sock.Connected)
                            {
                                var line = reader.ReadLine();
                                if (line == null) break;
                                line = line.Trim();
                                if (string.IsNullOrEmpty(line)) continue;

                                using var doc = JsonDocument.Parse(line);
                                ProcessMessage(doc.RootElement);
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        AppLogger.LogDebug("BluetoothPeer", $"Client connection attempt info: {ex.Message}");
                        Thread.Sleep(5000);
                    }
                    finally
                    {
                        CloseConnection();
                    }
                }
                else
                {
                    Thread.Sleep(2000);
                }
            }
        }

        private void ProcessMessage(JsonElement root)
        {
            var type = root.TryGetProperty("type", out var tProp) ? tProp.GetString() : null;

            if (type == "SWITCH_OUT")
            {
                var exitEdge = root.TryGetProperty("exit_edge", out var eProp) ? eProp.GetString() ?? "right" : "right";
                var ratio = root.TryGetProperty("ratio", out var rProp) ? rProp.GetDouble() : 0.5;
                var clip = root.TryGetProperty("clipboard", out var cProp) ? cProp.GetString() : null;

                OnSwitchReceived?.Invoke(exitEdge, ratio, clip);
            }
            else if (type == "CLIPBOARD_SYNC")
            {
                var clip = root.TryGetProperty("clipboard", out var cProp) ? cProp.GetString() : null;
                if (!string.IsNullOrEmpty(clip))
                {
                    OnClipboardReceived?.Invoke(clip);
                }
            }
            else if (type == "ALIGNMENT_EXCHANGE")
            {
                if (root.TryGetProperty("screen_bounds", out var bProp) && bProp.ValueKind == JsonValueKind.Object)
                {
                    var dict = new Dictionary<string, int>();
                    foreach (var prop in bProp.EnumerateObject())
                    {
                        if (prop.Value.TryGetInt32(out var val))
                            dict[prop.Name] = val;
                    }
                    OnAlignmentReceived?.Invoke(dict);
                }
            }
            else if (type == "PAIR_ACCEPT")
            {
                var fromHost = root.TryGetProperty("from_host", out var fh) ? fh.GetString() ?? "Partner" : "Partner";
                AppLogger.Log("BluetoothPeer", $"Pairing SUCCESS! Partner '{fromHost}' accepted handshake.");
                OnPairResponse?.Invoke(true, fromHost, null);
            }
            else if (type == "PAIR_REJECT")
            {
                var reason = root.TryGetProperty("reason", out var r) ? r.GetString() ?? "Rejected" : "Rejected";
                AppLogger.Log("BluetoothPeer", $"Pairing REJECTED by partner: {reason}");
                OnPairResponse?.Invoke(false, string.Empty, reason);
            }
        }

        public Task<(bool Success, string? Message)> RequestPairingAsync(string targetMac, string advToken = "")
        {
            var tcs = new TaskCompletionSource<(bool, string?)>();
            RequestPairing(targetMac, advToken, (ok, msg) => tcs.TrySetResult((ok, msg)));
            return tcs.Task;
        }

        public void RequestPairing(string targetMac, string advToken, Action<bool, string?> onResult)
        {
            Task.Run(() =>
            {
                Socket? sock = null;
                try
                {
                    ulong mac = BluetoothEndPoint.ParseMac(targetMac);
                    if (mac == 0)
                    {
                        onResult(false, "Invalid MAC address format");
                        return;
                    }

                    AppLogger.Log("BluetoothPeer", $"Initiating pairing handshake with {targetMac} (Port {RfcommPort})...");
                    sock = new Socket(AF_BTH, SocketType.Stream, BTHPROTO_RFCOMM);
                    sock.ReceiveTimeout = 6000;
                    sock.SendTimeout = 6000;

                    var ep = new BluetoothEndPoint(mac, RfcommPort);
                    sock.Connect(ep);

                    var req = new Dictionary<string, object?>
                    {
                        { "type", "PAIR_REQUEST" },
                        { "from_host", HostName },
                        { "token", advToken },
                        { "timestamp", DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0 }
                    };
                    var json = JsonSerializer.Serialize(req) + "\n";
                    sock.Send(Encoding.UTF8.GetBytes(json));

                    // Wait for PAIR_ACCEPT
                    using var stream = new NetworkStream(sock, false);
                    using var reader = new StreamReader(stream, Encoding.UTF8);
                    var line = reader.ReadLine();

                    if (!string.IsNullOrEmpty(line))
                    {
                        using var doc = JsonDocument.Parse(line);
                        var root = doc.RootElement;
                        var type = root.TryGetProperty("type", out var tProp) ? tProp.GetString() : null;

                        if (type == "PAIR_ACCEPT")
                        {
                            var partner = root.TryGetProperty("from_host", out var fh) ? fh.GetString() ?? "Partner" : "Partner";
                            PeerAddress = targetMac.ToUpperInvariant();
                            SetActiveConnection(sock);
                            sock = null; // ownership transferred to active connection

                            AppLogger.Log("BluetoothPeer", $"Pairing confirmed with {partner} ({targetMac})!");
                            onResult(true, partner);
                            return;
                        }
                        else if (type == "PAIR_REJECT")
                        {
                            var reason = root.TryGetProperty("reason", out var r) ? r.GetString() ?? "Rejected" : "Rejected";
                            onResult(false, reason);
                            return;
                        }
                    }
                    onResult(false, "No valid response from host");
                }
                catch (Exception ex)
                {
                    AppLogger.Log("BluetoothPeer", $"Pairing request failed: {ex.Message}");
                    onResult(false, ex.Message);
                }
                finally
                {
                    try { sock?.Close(); } catch { }
                }
            });
        }

        public Task<List<DiscoveredPeer>> ScanLunifierPeersAsync(double timeoutSeconds = 4.0)
        {
            var tcs = new TaskCompletionSource<List<DiscoveredPeer>>();
            ScanLunifierPeers(peers => tcs.TrySetResult(peers), timeoutSeconds);
            return tcs.Task;
        }

        public void ScanLunifierPeers(Action<List<DiscoveredPeer>> onComplete, double timeoutSeconds = 4.0)
        {
            Task.Run(() =>
            {
                var discovered = new List<DiscoveredPeer>();
                var candidates = GetCandidateBluetoothDevices();

                if (candidates.Count == 0)
                {
                    onComplete(discovered);
                    return;
                }

                AppLogger.Log("BluetoothPeer", $"Scanning {candidates.Count} candidate Bluetooth device(s) for active Lunifier advertising...");

                Parallel.ForEach(candidates, new ParallelOptions { MaxDegreeOfParallelism = 4 }, cand =>
                {
                    try
                    {
                        ulong mac = BluetoothEndPoint.ParseMac(cand.Key);
                        if (mac == 0) return;

                        using var probeSock = new Socket(AF_BTH, SocketType.Stream, BTHPROTO_RFCOMM);
                        probeSock.ReceiveTimeout = (int)(timeoutSeconds * 1000);
                        probeSock.SendTimeout = 2000;

                        var ep = new BluetoothEndPoint(mac, RfcommPort);
                        var connectTask = Task.Run(() => probeSock.Connect(ep));
                        if (!connectTask.Wait(TimeSpan.FromSeconds(timeoutSeconds)))
                            return;

                        var probeMsg = new Dictionary<string, object?>
                        {
                            { "type", "PROBE_ADV" },
                            { "from_host", HostName }
                        };
                        var json = JsonSerializer.Serialize(probeMsg) + "\n";
                        probeSock.Send(Encoding.UTF8.GetBytes(json));

                        using var stream = new NetworkStream(probeSock, false);
                        using var reader = new StreamReader(stream, Encoding.UTF8);
                        var line = reader.ReadLine();

                        if (!string.IsNullOrEmpty(line))
                        {
                            using var doc = JsonDocument.Parse(line);
                            var root = doc.RootElement;
                            var type = root.TryGetProperty("type", out var tProp) ? tProp.GetString() : null;

                            if (type == "PROBE_REPLY")
                            {
                                var isAdv = root.TryGetProperty("is_advertising", out var aProp) && aProp.GetBoolean();
                                var token = root.TryGetProperty("token", out var tk) ? tk.GetString() ?? "" : "";
                                var fromHost = root.TryGetProperty("from_host", out var fh) ? fh.GetString() ?? cand.Value : cand.Value;

                                if (isAdv)
                                {
                                    lock (discovered)
                                    {
                                        discovered.Add(new DiscoveredPeer
                                        {
                                            Name = fromHost,
                                            MacAddress = cand.Key,
                                            AdvertisingToken = token,
                                            IsAdvertising = true
                                        });
                                    }
                                }
                            }
                        }
                    }
                    catch { }
                });

                AppLogger.Log("BluetoothPeer", $"Scan complete. Found {discovered.Count} active Lunifier advertising peer(s).");
                onComplete(discovered);
            });
        }

        private Dictionary<string, string> GetCandidateBluetoothDevices()
        {
            var dict = new Dictionary<string, string>();
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices");
                if (key != null)
                {
                    foreach (var sub in key.GetSubKeyNames())
                    {
                        if (sub.Length >= 12)
                        {
                            var mac = $"{sub[0..2]}:{sub[2..4]}:{sub[4..6]}:{sub[6..8]}:{sub[8..10]}:{sub[10..12]}".ToUpperInvariant();
                            var name = mac;
                            using var subKey = key.OpenSubKey(sub);
                            var val = subKey?.GetValue("Name");
                            if (val is byte[] b)
                                name = Encoding.UTF8.GetString(b).TrimEnd('\0');
                            else if (val is string s)
                                name = s;

                            dict[mac] = name;
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                AppLogger.LogDebug("BluetoothPeer", $"Read paired devices registry info: {ex.Message}");
            }

            if (!string.IsNullOrEmpty(PeerAddress) && !dict.ContainsKey(PeerAddress))
            {
                dict[PeerAddress] = "Configured Partner";
            }

            return dict;
        }
    }
}
