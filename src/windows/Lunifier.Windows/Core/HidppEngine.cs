using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using Microsoft.Win32.SafeHandles;

namespace Lunifier.Windows.Core
{
    public enum TransportType
    {
        Bluetooth,
        Unifying,
        Bolt,
        Lightspeed,
        GenericHid
    }

    public class LogitechDevice
    {
        public string Name { get; set; } = string.Empty;
        public string Path { get; set; } = string.Empty;
        public TransportType Transport { get; set; } = TransportType.GenericHid;
        public byte DeviceIndex { get; set; } = 0x01;
        public ushort Vid { get; set; } = 0x046D;
        public ushort Pid { get; set; }
        public ushort UsagePage { get; set; }
        public ushort Usage { get; set; }
        public byte ChangeHostFeatureIndex { get; set; } = 0x09;
        public bool FeatureResolved { get; set; }
        public bool IsActive { get; set; } = true;
        public List<string> AllPaths { get; set; } = new();

        public bool IsReceiver => Transport is TransportType.Unifying or TransportType.Bolt or TransportType.Lightspeed;

        public override string ToString()
        {
            return $"{Name} [{Transport}, DevIdx=0x{DeviceIndex:X2}, Feat=0x{ChangeHostFeatureIndex:X2}]";
        }
    }

    public class HidppEngine
    {
        public const ushort LogitechVid = 0x046D;
        public const ushort FeatureRoot = 0x0000;
        public const ushort FeatureChangeHost = 0x1814;
        public const ushort FeatureDeviceName = 0x0005;

        private static readonly HashSet<ushort> PidsUnifying = new() { 0xC52B, 0xC532, 0xC52F };
        private static readonly HashSet<ushort> PidsBolt = new() { 0xC548, 0xC547 };
        private static readonly HashSet<ushort> PidsLightspeed = new() { 0xC539, 0xC53A, 0xC541, 0xC542, 0xC53F, 0xC545 };

        public string ConnectionSupport { get; set; } = "both"; // "both", "unifying", "bluetooth"

        private readonly ConcurrentDictionary<(ushort Pid, byte Slot), LogitechDevice> _receiverSlotsCache = new();
        private List<LogitechDevice> _cachedDevices = new();
        private double _lastScanTime;
        private readonly object _scanLock = new();

        #region Win32 P/Invoke Definitions

        [DllImport("hid.dll", SetLastError = true)]
        private static extern void HidD_GetHidGuid(out Guid hidGuid);

        [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
        private static extern IntPtr SetupDiGetClassDevs(ref Guid classGuid, IntPtr enumerator, IntPtr hwndParent, uint flags);

        [DllImport("setupapi.dll", SetLastError = true)]
        private static extern bool SetupDiDestroyDeviceInfoList(IntPtr deviceInfoSet);

        [StructLayout(LayoutKind.Sequential)]
        private struct SP_DEVICE_INTERFACE_DATA
        {
            public int cbSize;
            public Guid interfaceClassGuid;
            public int flags;
            public IntPtr reserved;
        }

        [DllImport("setupapi.dll", SetLastError = true)]
        private static extern bool SetupDiEnumDeviceInterfaces(IntPtr deviceInfoSet, IntPtr deviceInfoData, ref Guid interfaceClassGuid, uint memberIndex, ref SP_DEVICE_INTERFACE_DATA deviceInterfaceData);

        [DllImport("setupapi.dll", SetLastError = true, CharSet = CharSet.Auto)]
        private static extern bool SetupDiGetDeviceInterfaceDetail(IntPtr deviceInfoSet, ref SP_DEVICE_INTERFACE_DATA deviceInterfaceData, IntPtr deviceInterfaceDetailData, uint deviceInterfaceDetailDataSize, out uint requiredSize, IntPtr deviceInfoData);

        [StructLayout(LayoutKind.Sequential)]
        private struct HIDD_ATTRIBUTES
        {
            public int Size;
            public ushort VendorID;
            public ushort ProductID;
            public ushort VersionNumber;
        }

        [DllImport("hid.dll", SetLastError = true)]
        private static extern bool HidD_GetAttributes(SafeFileHandle hidDeviceObject, ref HIDD_ATTRIBUTES attributes);

        [DllImport("hid.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        private static extern bool HidD_GetProductString(SafeFileHandle hidDeviceObject, StringBuilder buffer, uint bufferLength);

        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Auto)]
        private static extern SafeFileHandle CreateFile(
            string lpFileName,
            uint dwDesiredAccess,
            uint dwShareMode,
            IntPtr lpSecurityAttributes,
            uint dwCreationDisposition,
            uint dwFlagsAndAttributes,
            IntPtr hTemplateFile
        );

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool WriteFile(SafeFileHandle hFile, byte[] lpBuffer, uint nNumberOfBytesToWrite, out uint lpNumberOfBytesWritten, IntPtr lpOverlapped);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool ReadFile(SafeFileHandle hFile, byte[] lpBuffer, uint nNumberOfBytesToRead, out uint lpNumberOfBytesRead, IntPtr lpOverlapped);

        private const uint DIGCF_PRESENT = 0x00000002;
        private const uint DIGCF_DEVICEINTERFACE = 0x00000010;
        private const uint GENERIC_READ = 0x80000000;
        private const uint GENERIC_WRITE = 0x40000000;
        private const uint FILE_SHARE_READ = 0x00000001;
        private const uint FILE_SHARE_WRITE = 0x00000002;
        private const uint OPEN_EXISTING = 3;
        private const uint FILE_FLAG_OVERLAPPED = 0x40000000;

        #endregion

        public void ClearCache()
        {
            lock (_scanLock)
            {
                _cachedDevices.Clear();
                _receiverSlotsCache.Clear();
                _lastScanTime = 0;
            }
            AppLogger.Log("HID++", "Device cache cleared.");
        }

        public static TransportType IdentifyTransport(ushort pid, string path)
        {
            if (PidsUnifying.Contains(pid)) return TransportType.Unifying;
            if (PidsBolt.Contains(pid)) return TransportType.Bolt;
            if (PidsLightspeed.Contains(pid)) return TransportType.Lightspeed;

            var p = path.ToLowerInvariant();
            if (p.Contains("bth") || p.Contains("bluetooth"))
                return TransportType.Bluetooth;

            return TransportType.Bluetooth; // Most non-dongle Logitech peripherals connected to PC
        }

        public bool IsTransportSupported(TransportType transport, string? connSupport = null)
        {
            var mode = (connSupport ?? ConnectionSupport ?? "both").ToLowerInvariant();
            return mode switch
            {
                "unifying" => transport is TransportType.Unifying or TransportType.Bolt or TransportType.Lightspeed,
                "bluetooth" => transport == TransportType.Bluetooth,
                _ => true
            };
        }

        public List<LogitechDevice> ScanDevices(List<string>? targetKeywords = null, bool forceRescan = false, string? connectionSupport = null)
        {
            lock (_scanLock)
            {
                if (connectionSupport != null && connectionSupport != ConnectionSupport)
                {
                    ClearCache();
                    ConnectionSupport = connectionSupport;
                }

                var now = Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;
                if (_cachedDevices.Count > 0 && !forceRescan && (now - _lastScanTime < 60.0))
                {
                    return FilterDevices(_cachedDevices, targetKeywords);
                }

                var found = new List<LogitechDevice>();
                var seenNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

                HidD_GetHidGuid(out var hidGuid);
                var devInfoSet = SetupDiGetClassDevs(ref hidGuid, IntPtr.Zero, IntPtr.Zero, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);

                if (devInfoSet == IntPtr.Zero || devInfoSet == new IntPtr(-1))
                {
                    AppLogger.Log("HID++", "Failed to retrieve HID device info set.");
                    return found;
                }

                try
                {
                    var ifaceData = new SP_DEVICE_INTERFACE_DATA();
                    ifaceData.cbSize = Marshal.SizeOf(typeof(SP_DEVICE_INTERFACE_DATA));

                    uint memberIndex = 0;
                    while (SetupDiEnumDeviceInterfaces(devInfoSet, IntPtr.Zero, ref hidGuid, memberIndex++, ref ifaceData))
                    {
                        SetupDiGetDeviceInterfaceDetail(devInfoSet, ref ifaceData, IntPtr.Zero, 0, out var requiredSize, IntPtr.Zero);
                        if (requiredSize == 0) continue;

                        var detailDataBuffer = Marshal.AllocHGlobal((int)requiredSize);
                        try
                        {
                            Marshal.WriteInt32(detailDataBuffer, IntPtr.Size == 8 ? 8 : 4 + Marshal.SystemDefaultCharSize);

                            if (SetupDiGetDeviceInterfaceDetail(devInfoSet, ref ifaceData, detailDataBuffer, requiredSize, out _, IntPtr.Zero))
                            {
                                var pDevicePath = new IntPtr(detailDataBuffer.ToInt64() + 4);
                                var path = Marshal.PtrToStringAuto(pDevicePath);

                                if (!string.IsNullOrEmpty(path))
                                {
                                    InspectDevicePath(path, found, seenNames, targetKeywords);
                                }
                            }
                        }
                        finally
                        {
                            Marshal.FreeHGlobal(detailDataBuffer);
                        }
                    }
                }
                finally
                {
                    SetupDiDestroyDeviceInfoList(devInfoSet);
                }

                _cachedDevices = found;
                _lastScanTime = now;

                AppLogger.Log("HID++", $"Scan complete: found {found.Count} compatible Logitech device(s).");
                return FilterDevices(found, targetKeywords);
            }
        }

        private void InspectDevicePath(string path, List<LogitechDevice> found, HashSet<string> seenNames, List<string>? targetKeywords)
        {
            try
            {
                using var handle = CreateFile(
                    path,
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    IntPtr.Zero,
                    OPEN_EXISTING,
                    0,
                    IntPtr.Zero
                );

                if (handle.IsInvalid) return;

                var attrs = new HIDD_ATTRIBUTES();
                attrs.Size = Marshal.SizeOf(typeof(HIDD_ATTRIBUTES));

                if (!HidD_GetAttributes(handle, ref attrs) || attrs.VendorID != LogitechVid)
                    return;

                var prodBuffer = new StringBuilder(256);
                HidD_GetProductString(handle, prodBuffer, 256);
                var prodName = prodBuffer.ToString().Trim();

                var transport = IdentifyTransport(attrs.ProductID, path);
                if (!IsTransportSupported(transport))
                    return;

                if (transport is TransportType.Unifying or TransportType.Bolt or TransportType.Lightspeed)
                {
                    // Query paired devices behind receiver
                    var paired = QueryReceiverPairedDevices(handle, path, attrs.ProductID, transport);
                    foreach (var pDev in paired)
                    {
                        if (seenNames.Add(pDev.Name))
                        {
                            found.Add(pDev);
                        }
                        else
                        {
                            var existing = found.FirstOrDefault(d => string.Equals(d.Name, pDev.Name, StringComparison.OrdinalIgnoreCase));
                            if (existing != null && !existing.AllPaths.Contains(pDev.Path))
                                existing.AllPaths.Add(pDev.Path);
                        }
                    }
                }
                else
                {
                    // Direct Bluetooth / HID device
                    var name = !string.IsNullOrEmpty(prodName) ? prodName : $"Logitech Device (PID 0x{attrs.ProductID:X4})";
                    byte defaultFeat = name.ToLowerInvariant().Contains("master") ? (byte)0x08 : (byte)0x09;

                    var dev = new LogitechDevice
                    {
                        Name = name,
                        Path = path,
                        Transport = transport,
                        DeviceIndex = 0xFF, // Bluetooth devices listen on index 0xFF
                        Vid = attrs.VendorID,
                        Pid = attrs.ProductID,
                        ChangeHostFeatureIndex = defaultFeat,
                        AllPaths = new List<string> { path }
                    };

                    if (seenNames.Add(dev.Name))
                    {
                        found.Add(dev);
                    }
                    else
                    {
                        var existing = found.FirstOrDefault(d => string.Equals(d.Name, dev.Name, StringComparison.OrdinalIgnoreCase));
                        if (existing != null && !existing.AllPaths.Contains(path))
                            existing.AllPaths.Add(path);
                    }
                }
            }
            catch
            {
                // Access denied or unreadable interface
            }
        }

        private List<LogitechDevice> QueryReceiverPairedDevices(SafeFileHandle handle, string receiverPath, ushort pid, TransportType transport)
        {
            var results = new List<LogitechDevice>();

            // Query each paired slot (1..6)
            for (byte idx = 1; idx <= 6; idx++)
            {
                try
                {
                    // Wake ping to slot
                    var ping = new byte[20];
                    ping[0] = 0x11;
                    ping[1] = idx;
                    WriteFile(handle, ping, 20, out _, IntPtr.Zero);

                    // Query Feature 0x0005 (Device Name)
                    var queryName = new byte[20];
                    queryName[0] = 0x11;
                    queryName[1] = idx;
                    queryName[4] = 0x00;
                    queryName[5] = (byte)(FeatureDeviceName & 0xFF);

                    WriteFile(handle, queryName, 20, out _, IntPtr.Zero);

                    // Fast read attempt
                    var resp = new byte[20];
                    byte nameFeat = 0;
                    for (int i = 0; i < 3; i++)
                    {
                        if (ReadFile(handle, resp, 20, out var readBytes, IntPtr.Zero) && readBytes >= 5)
                        {
                            if (resp[0] == 0x11 && resp[1] == idx && resp[2] == 0x00 && resp[4] != 0)
                            {
                                nameFeat = resp[4];
                                break;
                            }
                        }
                    }

                    if (nameFeat == 0) continue;

                    // Read name chunks
                    var nameChunk = new byte[20];
                    nameChunk[0] = 0x11;
                    nameChunk[1] = idx;
                    nameChunk[2] = nameFeat;
                    nameChunk[3] = 0x10; // get_device_name_type chunk 0

                    WriteFile(handle, nameChunk, 20, out _, IntPtr.Zero);

                    var nameBytes = new List<byte>();
                    for (int i = 0; i < 3; i++)
                    {
                        if (ReadFile(handle, resp, 20, out var readBytes, IntPtr.Zero) && readBytes >= 5)
                        {
                            if (resp[0] == 0x11 && resp[1] == idx && resp[2] == nameFeat)
                            {
                                for (int b = 4; b < readBytes && resp[b] != 0; b++)
                                    nameBytes.Add(resp[b]);
                                break;
                            }
                        }
                    }

                    var devName = Encoding.UTF8.GetString(nameBytes.ToArray()).Trim();
                    if (string.IsNullOrEmpty(devName))
                        devName = $"Receiver Device Slot {idx}";

                    // Query Change Host feature index (0x1814)
                    byte chFeat = (byte)(devName.ToLowerInvariant().Contains("master") ? 0x08 : 0x09);
                    bool resolved = false;

                    var queryCh = new byte[20];
                    queryCh[0] = 0x11;
                    queryCh[1] = idx;
                    queryCh[4] = (byte)((FeatureChangeHost >> 8) & 0xFF);
                    queryCh[5] = (byte)(FeatureChangeHost & 0xFF);

                    WriteFile(handle, queryCh, 20, out _, IntPtr.Zero);

                    for (int i = 0; i < 3; i++)
                    {
                        if (ReadFile(handle, resp, 20, out var readBytes, IntPtr.Zero) && readBytes >= 5)
                        {
                            if (resp[0] == 0x11 && resp[1] == idx && resp[2] == 0x00 && resp[4] != 0)
                            {
                                chFeat = resp[4];
                                resolved = true;
                                break;
                            }
                        }
                    }

                    var dev = new LogitechDevice
                    {
                        Name = devName,
                        Path = receiverPath,
                        Transport = transport,
                        DeviceIndex = idx,
                        Vid = LogitechVid,
                        Pid = pid,
                        ChangeHostFeatureIndex = chFeat,
                        FeatureResolved = resolved,
                        AllPaths = new List<string> { receiverPath }
                    };

                    results.Add(dev);
                    _receiverSlotsCache[(pid, idx)] = dev;
                }
                catch
                {
                    // Slot not responding or receiver handle busy
                }
            }

            return results;
        }

        private List<LogitechDevice> FilterDevices(List<LogitechDevice> devices, List<string>? keywords)
        {
            if (keywords == null || keywords.Count == 0)
                return devices;

            return devices.Where(d =>
            {
                var n = d.Name.ToLowerInvariant();
                return keywords.Any(k => n.Contains(k.ToLowerInvariant()));
            }).ToList();
        }

        public bool SwitchDeviceHost(LogitechDevice dev, int targetChannel)
        {
            if (!IsTransportSupported(dev.Transport))
            {
                AppLogger.Log("HID++", $"Skipping switch for '{dev.Name}': {dev.Transport} not enabled in setting '{ConnectionSupport}'");
                return false;
            }

            var channelIndex = (byte)Math.Clamp(targetChannel - 1, 0, 2);
            var t0 = Stopwatch.GetTimestamp();

            AppLogger.Log("HID++", $"switch_device_host: '{dev.Name}' [{dev.Transport}] -> Channel {targetChannel} (Host Index: {channelIndex})");

            var pathsToTry = new List<string>();
            if (!string.IsNullOrEmpty(dev.Path)) pathsToTry.Add(dev.Path);
            foreach (var p in dev.AllPaths)
            {
                if (!pathsToTry.Contains(p)) pathsToTry.Add(p);
            }

            var featureIndices = new List<byte> { dev.ChangeHostFeatureIndex };
            if (!dev.FeatureResolved)
            {
                foreach (byte f in new byte[] { 0x09, 0x08, 0x0A, 0x0B, 0x07 })
                {
                    if (!featureIndices.Contains(f)) featureIndices.Add(f);
                }
            }

            foreach (var devPath in pathsToTry)
            {
                try
                {
                    using var handle = CreateFile(
                        devPath,
                        GENERIC_READ | GENERIC_WRITE,
                        FILE_SHARE_READ | FILE_SHARE_WRITE,
                        IntPtr.Zero,
                        OPEN_EXISTING,
                        0,
                        IntPtr.Zero
                    );

                    if (handle.IsInvalid) continue;

                    bool ok = false;
                    foreach (var featIdx in featureIndices)
                    {
                        var packet = new byte[20];
                        packet[0] = 0x11;
                        packet[1] = dev.DeviceIndex;
                        packet[2] = featIdx;
                        packet[3] = 0x10;          // Function 1: set_current_host
                        packet[4] = channelIndex;

                        if (WriteFile(handle, packet, 20, out var written, IntPtr.Zero) && written > 0)
                        {
                            ok = true;
                            // For Bluetooth devices send an immediate follow-up to guarantee transmission
                            if (dev.Transport == TransportType.Bluetooth)
                            {
                                Thread.Sleep(15);
                                WriteFile(handle, packet, 20, out _, IntPtr.Zero);
                            }
                            break;
                        }
                    }

                    if (ok)
                    {
                        var elapsed = (Stopwatch.GetTimestamp() - t0) * 1000.0 / Stopwatch.Frequency;
                        AppLogger.Log("HID++", $"Fast Win32 switch for '{dev.Name}' -> Channel {targetChannel} [{elapsed:F1}ms]");
                        return true;
                    }
                }
                catch (Exception ex)
                {
                    AppLogger.LogDebug("HID++", $"Error writing to device path {devPath}: {ex.Message}");
                }
            }

            var failElapsed = (Stopwatch.GetTimestamp() - t0) * 1000.0 / Stopwatch.Frequency;
            AppLogger.Log("HID++", $"switch_device_host: FAILED for '{dev.Name}' -> Channel {targetChannel} after {failElapsed:F1}ms");
            return false;
        }

        public Dictionary<string, bool> SwitchAllToChannel(int targetChannel, List<string>? targetKeywords = null)
        {
            var devices = ScanDevices(targetKeywords);
            if (devices.Count == 0)
            {
                devices = ScanDevices(targetKeywords, forceRescan: true);
            }

            AppLogger.Log("HID++", $"switch_all_to_channel: Initiating concurrent switch for {devices.Count} device(s) -> Channel {targetChannel}");

            var results = new ConcurrentDictionary<string, bool>();

            // Concurrent parallel switch
            Parallel.ForEach(devices, dev =>
            {
                var ok = SwitchDeviceHost(dev, targetChannel);
                results[$"{dev.Name} ({dev.Transport})"] = ok;
            });

            return new Dictionary<string, bool>(results);
        }
    }
}
