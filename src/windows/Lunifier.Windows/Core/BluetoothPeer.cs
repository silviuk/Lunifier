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
using Windows.Devices.Bluetooth.Advertisement;
using Windows.Storage.Streams;

namespace Lunifier.Windows.Core
{
    public class DiscoveredPeer
    {
        public string Name { get; set; } = string.Empty;
        public string MacAddress { get; set; } = string.Empty;
        public int Port { get; set; } = 5;
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
        public int RfcommPort { get; set; } = 5;

        public Action<string, double, string?>? OnSwitchReceived { get; set; }
        public Action<bool>? OnPeerStatusChanged { get; set; }
        public Action<bool, int>? OnAdvertisingStateChanged { get; set; }
        public Action<bool, string, string?>? OnPairResponse { get; set; }
        public Action<string>? OnClipboardReceived { get; set; }
        public Action<Dictionary<string, int>>? OnAlignmentReceived { get; set; }

        private static string? _cachedLocalMac;

        public static int FindAvailableRfcommPort(int preferredPort = 5)
        {
            var candidates = new List<int> { preferredPort };
            for (int p = 5; p <= 30; p++)
            {
                if (p != preferredPort) candidates.Add(p);
            }
            foreach (var p in candidates)
            {
                try
                {
                    using var sock = new Socket(AF_BTH, SocketType.Stream, BTHPROTO_RFCOMM);
                    var ep = new BluetoothEndPoint(0, p);
                    sock.Bind(ep);
                    return p;
                }
                catch { }
            }
            return preferredPort;
        }

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
        private BluetoothLEAdvertisementPublisher? _blePublisher;

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

        public BluetoothPeer(string hostName, string peerAddress = "", int rfcommPort = 5)
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

                StartBleBroadcaster();

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

                StopBleBroadcaster();

                AppLogger.Log("BluetoothPeer", "Bluetooth advertising stopped/expired.");
                OnAdvertisingStateChanged?.Invoke(false, 0);
            }
        }

        private void StartBleBroadcaster()
        {
            try
            {
                StopBleBroadcaster();

                var publisher = new BluetoothLEAdvertisementPublisher();
                var writer = new DataWriter();

                string macClean = (GetLocalBluetoothMac() ?? string.Empty).Replace(":", "").Replace("-", "");
                byte[] macBytes = new byte[6];
                if (macClean.Length == 12)
                {
                    try { macBytes = Convert.FromHexString(macClean); } catch { }
                }

                string tokClean = _advToken.Length >= 8 ? _advToken[..8] : _advToken;
                byte[] tokBytes = new byte[4];
                try
                {
                    byte[] parsed = Convert.FromHexString(tokClean);
                    Array.Copy(parsed, tokBytes, Math.Min(parsed.Length, 4));
                }
                catch { }

                byte[] nameBytes = Encoding.UTF8.GetBytes(HostName);
                if (nameBytes.Length > 10) nameBytes = nameBytes[..10];

                var payload = new List<byte>();
                payload.AddRange(Encoding.ASCII.GetBytes("LUNI"));
                payload.Add(1); // Protocol version
                payload.Add((byte)(RfcommPort & 0xFF));
                payload.AddRange(macBytes);
                payload.AddRange(tokBytes);
                payload.AddRange(nameBytes);

                writer.WriteBytes(payload.ToArray());

                var mfg = new BluetoothLEManufacturerData(0xFFFF, writer.DetachBuffer());
                publisher.Advertisement.ManufacturerData.Add(mfg);
                publisher.Start();

                _blePublisher = publisher;
                AppLogger.Log("BluetoothPeer", $"BLE advertisement broadcaster started (WinRT, RFCOMM port {RfcommPort}).");
            }
            catch (Exception ex)
            {
                AppLogger.LogDebug("BluetoothPeer", $"BLE advertisement start notice (WinRT): {ex.Message}");
            }
        }

        private void StopBleBroadcaster()
        {
            if (_blePublisher != null)
            {
                try
                {
                    _blePublisher.Stop();
                    AppLogger.Log("BluetoothPeer", "BLE advertisement broadcaster stopped.");
                }
                catch { }
                finally
                {
                    _blePublisher = null;
                }
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
                    var candidates = new List<int> { RfcommPort };
                    for (int p = 5; p <= 30; p++)
                    {
                        if (p != RfcommPort) candidates.Add(p);
                    }

                    Socket? boundSocket = null;
                    int boundPort = RfcommPort;

                    foreach (var p in candidates)
                    {
                        try
                        {
                            var sock = new Socket(AF_BTH, SocketType.Stream, BTHPROTO_RFCOMM);
                            var ep = new BluetoothEndPoint(0, p);
                            sock.Bind(ep);
                            sock.Listen(4);
                            boundSocket = sock;
                            boundPort = p;
                            break;
                        }
                        catch
                        {
                            // Port unavailable, try next candidate
                        }
                    }

                    if (boundSocket == null)
                    {
                        AppLogger.LogDebug("BluetoothPeer", "Could not bind RFCOMM server to any port in range [5..30]. Retrying in 5s...");
                        Thread.Sleep(5000);
                        continue;
                    }

                    _serverSocket = boundSocket;
                    if (boundPort != RfcommPort)
                    {
                        AppLogger.Log("BluetoothPeer", $"Preferred RFCOMM port {RfcommPort} in use; dynamically bound to port {boundPort}.");
                        RfcommPort = boundPort;
                    }

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
                            { "token", IsAdvertising ? AdvertisingToken : "" },
                            { "port", RfcommPort }
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

        public Task<(bool Success, string? Message)> RequestPairingAsync(string targetMac, string advToken = "", int? port = null)
        {
            var tcs = new TaskCompletionSource<(bool, string?)>();
            RequestPairing(targetMac, advToken, (ok, msg) => tcs.TrySetResult((ok, msg)), port);
            return tcs.Task;
        }

        public void RequestPairing(string targetMac, string advToken, Action<bool, string?> onResult, int? port = null)
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

                    int connectPort = (port.HasValue && port.Value > 0) ? port.Value : RfcommPort;
                    AppLogger.Log("BluetoothPeer", $"Initiating pairing handshake with {targetMac} (Port {connectPort})...");
                    sock = new Socket(AF_BTH, SocketType.Stream, BTHPROTO_RFCOMM);
                    sock.ReceiveTimeout = 6000;
                    sock.SendTimeout = 6000;

                    var ep = new BluetoothEndPoint(mac, connectPort);
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
                            RfcommPort = connectPort;
                            SetActiveConnection(sock);
                            sock = null; // ownership transferred to active connection

                            AppLogger.Log("BluetoothPeer", $"Pairing confirmed with {partner} ({targetMac}) on port {connectPort}!");
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
                BluetoothLEAdvertisementWatcher? bleWatcher = null;

                try
                {
                    bleWatcher = new BluetoothLEAdvertisementWatcher
                    {
                        ScanningMode = BluetoothLEScanningMode.Active
                    };

                    bleWatcher.Received += (w, args) =>
                    {
                        try
                        {
                            foreach (var md in args.Advertisement.ManufacturerData)
                            {
                                if (md.CompanyId == 0xFFFF)
                                {
                                    var reader = DataReader.FromBuffer(md.Data);
                                    if (reader.UnconsumedBufferLength >= 12)
                                    {
                                        byte[] data = new byte[reader.UnconsumedBufferLength];
                                        reader.ReadBytes(data);
                                        if (data[0] == 'L' && data[1] == 'U' && data[2] == 'N' && data[3] == 'I')
                                        {
                                            int port = data[5];
                                            string mac = $"{data[6]:X2}:{data[7]:X2}:{data[8]:X2}:{data[9]:X2}:{data[10]:X2}:{data[11]:X2}";
                                            string tok = "";
                                            if (data.Length >= 16)
                                            {
                                                tok = Convert.ToHexString(data[12..16]).ToUpperInvariant();
                                            }
                                            string hName = "";
                                            if (data.Length > 16)
                                            {
                                                hName = Encoding.UTF8.GetString(data[16..]).TrimEnd('\0');
                                            }
                                            if (string.IsNullOrEmpty(hName)) hName = mac;

                                            lock (discovered)
                                            {
                                                var existing = discovered.Find(d => d.MacAddress.Equals(mac, StringComparison.OrdinalIgnoreCase));
                                                if (existing == null)
                                                {
                                                    discovered.Add(new DiscoveredPeer
                                                    {
                                                        Name = hName,
                                                        MacAddress = mac,
                                                        AdvertisingToken = tok,
                                                        Port = port > 0 ? port : RfcommPort,
                                                        IsAdvertising = true
                                                    });
                                                    AppLogger.Log("BluetoothPeer", $"Discovered via BLE beacon: {hName} ({mac}) on port {port}");
                                                }
                                                else
                                                {
                                                    existing.Port = port > 0 ? port : existing.Port;
                                                    if (!string.IsNullOrEmpty(tok)) existing.AdvertisingToken = tok;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        catch { }
                    };

                    bleWatcher.Start();
                }
                catch (Exception ex)
                {
                    AppLogger.LogDebug("BluetoothPeer", $"BLE scan watcher notice: {ex.Message}");
                }

                var candidates = GetCandidateBluetoothDevices();
                var probePorts = new List<int> { RfcommPort };
                foreach (var p in new[] { 5, 6, 8, 9, 10, 7 })
                {
                    if (!probePorts.Contains(p)) probePorts.Add(p);
                }

                if (candidates.Count > 0)
                {
                    AppLogger.Log("BluetoothPeer", $"Scanning {candidates.Count} candidate Bluetooth device(s) for active Lunifier advertising...");

                    Parallel.ForEach(candidates, new ParallelOptions { MaxDegreeOfParallelism = 4 }, cand =>
                    {
                        try
                        {
                            ulong mac = BluetoothEndPoint.ParseMac(cand.Key);
                            if (mac == 0) return;

                            foreach (var port in probePorts)
                            {
                                try
                                {
                                    using var probeSock = new Socket(AF_BTH, SocketType.Stream, BTHPROTO_RFCOMM);
                                    probeSock.ReceiveTimeout = (int)(Math.Min(timeoutSeconds, 1.5) * 1000);
                                    probeSock.SendTimeout = 1500;

                                    var ep = new BluetoothEndPoint(mac, port);
                                    var connectTask = Task.Run(() => probeSock.Connect(ep));
                                    if (!connectTask.Wait(TimeSpan.FromSeconds(Math.Min(timeoutSeconds, 1.5))))
                                        continue;

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
                                            int replyPort = root.TryGetProperty("port", out var pProp) && pProp.TryGetInt32(out var rp) ? rp : port;

                                            if (isAdv)
                                            {
                                                lock (discovered)
                                                {
                                                    var existing = discovered.Find(d => d.MacAddress.Equals(cand.Key, StringComparison.OrdinalIgnoreCase));
                                                    if (existing == null)
                                                    {
                                                        discovered.Add(new DiscoveredPeer
                                                        {
                                                            Name = fromHost,
                                                            MacAddress = cand.Key,
                                                            AdvertisingToken = token,
                                                            Port = replyPort,
                                                            IsAdvertising = true
                                                        });
                                                    }
                                                    else
                                                    {
                                                        existing.Port = replyPort;
                                                        if (!string.IsNullOrEmpty(token)) existing.AdvertisingToken = token;
                                                    }
                                                }
                                            }
                                            break;
                                        }
                                    }
                                }
                                catch { }
                            }
                        }
                        catch { }
                    });
                }

                // Wait for remainder of timeout to catch BLE beacons
                int remainingWaitMs = Math.Max(500, (int)(timeoutSeconds * 1000) - 1500);
                Thread.Sleep(remainingWaitMs);

                try { bleWatcher?.Stop(); } catch { }

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
