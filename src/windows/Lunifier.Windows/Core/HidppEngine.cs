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
        public string? ShortPath { get; set; }
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
        private static readonly HashSet<ushort> AllReceiverPids = new(PidsUnifying.Concat(PidsBolt).Concat(PidsLightspeed));

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

        [DllImport("hid.dll", SetLastError = true)]
        private static extern bool HidD_GetPreparsedData(SafeFileHandle hidDeviceObject, out IntPtr preparsedData);

        [DllImport("hid.dll", SetLastError = true)]
        private static extern bool HidD_FreePreparsedData(IntPtr preparsedData);

        [StructLayout(LayoutKind.Sequential)]
        private struct HIDP_CAPS
        {
            public ushort Usage;
            public ushort UsagePage;
            public ushort InputReportByteLength;
            public ushort OutputReportByteLength;
            public ushort FeatureReportByteLength;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)]
            public ushort[] Reserved;
            public ushort NumberLinkCollectionNodes;
            public ushort NumberInputButtonCaps;
            public ushort NumberInputValueCaps;
            public ushort NumberInputDataIndices;
            public ushort NumberOutputButtonCaps;
            public ushort NumberOutputValueCaps;
            public ushort NumberOutputDataIndices;
            public ushort NumberFeatureButtonCaps;
            public ushort NumberFeatureValueCaps;
            public ushort NumberFeatureDataIndices;
        }

        [DllImport("hid.dll", SetLastError = true)]
        private static extern int HidP_GetCaps(IntPtr preparsedData, ref HIDP_CAPS capabilities);

        [StructLayout(LayoutKind.Sequential)]
        private struct OVERLAPPED
        {
            public IntPtr Internal;
            public IntPtr InternalHigh;
            public uint Offset;
            public uint OffsetHigh;
            public IntPtr hEvent;
        }

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
        private static extern bool ReadFile(SafeFileHandle hFile, [Out] byte[] lpBuffer, uint nNumberOfBytesToRead, out uint lpNumberOfBytesRead, IntPtr lpOverlapped);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetOverlappedResult(SafeFileHandle hFile, IntPtr lpOverlapped, out uint lpNumberOfBytesTransferred, bool bWait);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CancelIo(SafeFileHandle hFile);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr CreateEvent(IntPtr lpEventAttributes, bool bManualReset, bool bInitialState, string? lpName);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool ResetEvent(IntPtr hEvent);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);

        private const uint DIGCF_PRESENT = 0x00000002;
        private const uint DIGCF_DEVICEINTERFACE = 0x00000010;
        private const uint GENERIC_READ = 0x80000000;
        private const uint GENERIC_WRITE = 0x40000000;
        private const uint FILE_SHARE_READ = 0x00000001;
        private const uint FILE_SHARE_WRITE = 0x00000002;
        private const uint OPEN_EXISTING = 3;
        private const uint FILE_FLAG_OVERLAPPED = 0x40000000;
        private const int ERROR_IO_PENDING = 997;

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

            return TransportType.Bluetooth;
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

        private static byte[]? OverlappedRead(SafeFileHandle handle, IntPtr hEvent, IntPtr pOverlapped, int timeoutMs)
        {
            ResetEvent(hEvent);
            var ov = new OVERLAPPED { hEvent = hEvent };
            Marshal.StructureToPtr(ov, pOverlapped, false);

            var buf = new byte[20];
            var readSuccess = ReadFile(handle, buf, 20, out var bytesRead, pOverlapped);

            if (!readSuccess)
            {
                var err = Marshal.GetLastWin32Error();
                if (err != ERROR_IO_PENDING)
                {
                    CancelIo(handle);
                    return null;
                }

                var waitRes = WaitForSingleObject(hEvent, (uint)timeoutMs);
                if (waitRes != 0) // Timeout or error
                {
                    CancelIo(handle);
                    GetOverlappedResult(handle, pOverlapped, out _, true);
                    return null;
                }
            }

            if (GetOverlappedResult(handle, pOverlapped, out bytesRead, true) && bytesRead > 0)
            {
                return buf;
            }

            return null;
        }

        private static bool OverlappedWrite(SafeFileHandle handle, byte[] buf)
        {
            var hEvent = CreateEvent(IntPtr.Zero, true, false, null);
            if (hEvent == IntPtr.Zero) return false;

            var pOverlapped = Marshal.AllocHGlobal(Marshal.SizeOf<OVERLAPPED>());
            try
            {
                var ov = new OVERLAPPED { hEvent = hEvent };
                Marshal.StructureToPtr(ov, pOverlapped, false);

                var writeSuccess = WriteFile(handle, buf, (uint)buf.Length, out var bytesWritten, pOverlapped);
                if (!writeSuccess)
                {
                    var err = Marshal.GetLastWin32Error();
                    if (err != ERROR_IO_PENDING)
                    {
                        return false;
                    }

                    var waitRes = WaitForSingleObject(hEvent, 100);
                    if (waitRes != 0)
                    {
                        CancelIo(handle);
                        return false;
                    }
                }
                return true;
            }
            finally
            {
                Marshal.FreeHGlobal(pOverlapped);
                CloseHandle(hEvent);
            }
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

                // Temporary maps for receiver endpoints
                var receiversCol01 = new Dictionary<ushort, string>();
                var receiversCol02 = new Dictionary<ushort, string>();
                var bluetoothCandidates = new List<(string Name, string Path, ushort Pid, ushort UsagePage, ushort Usage)>();

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
                                    InspectDeviceEndpoint(path, receiversCol01, receiversCol02, bluetoothCandidates);
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

                // Process discovered receivers
                foreach (var (pid, longPath) in receiversCol02)
                {
                    receiversCol01.TryGetValue(pid, out var shortPath);
                    var transport = IdentifyTransport(pid, longPath);
                    if (!IsTransportSupported(transport)) continue;

                    var paired = QueryReceiverPairedDevices(longPath, shortPath, pid, transport);
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

                // Process direct Bluetooth candidates
                foreach (var (name, path, pid, up, u) in bluetoothCandidates)
                {
                    var transport = TransportType.Bluetooth;
                    if (!IsTransportSupported(transport)) continue;

                    byte defaultFeat = name.ToLowerInvariant().Contains("master") ? (byte)0x08 : (byte)0x09;

                    if (seenNames.Add(name))
                    {
                        var dev = new LogitechDevice
                        {
                            Name = name,
                            Path = path,
                            Transport = transport,
                            DeviceIndex = 0xFF,
                            Vid = LogitechVid,
                            Pid = pid,
                            UsagePage = up,
                            Usage = u,
                            ChangeHostFeatureIndex = defaultFeat,
                            AllPaths = new List<string> { path }
                        };
                        found.Add(dev);
                    }
                    else
                    {
                        var existing = found.FirstOrDefault(d => string.Equals(d.Name, name, StringComparison.OrdinalIgnoreCase));
                        if (existing != null && !existing.AllPaths.Contains(path))
                            existing.AllPaths.Add(path);
                    }
                }

                // Fallback: If a receiver was present but paired devices were sleeping, restore cached slots or generate fallback entries
                if (found.Count == 0 && receiversCol02.Count > 0)
                {
                    foreach (var (pid, longPath) in receiversCol02)
                    {
                        receiversCol01.TryGetValue(pid, out var shortPath);
                        var cachedForReceiver = _receiverSlotsCache.Where(kv => kv.Key.Pid == pid).Select(kv => kv.Value).ToList();
                        if (cachedForReceiver.Count > 0)
                        {
                            foreach (var cDev in cachedForReceiver)
                            {
                                cDev.Path = longPath;
                                cDev.ShortPath = shortPath;
                                if (seenNames.Add(cDev.Name)) found.Add(cDev);
                            }
                        }
                        else
                        {
                            // Synthesize paired slot 1 (Keyboard) and slot 3 (Mouse)
                            var devKeyboard = new LogitechDevice
                            {
                                Name = "Logitech Keyboard (Receiver Slot 1)",
                                Path = longPath,
                                ShortPath = shortPath,
                                Transport = IdentifyTransport(pid, longPath),
                                DeviceIndex = 1,
                                Vid = LogitechVid,
                                Pid = pid,
                                ChangeHostFeatureIndex = 0x09,
                                AllPaths = new List<string> { longPath }
                            };
                            var devMouse = new LogitechDevice
                            {
                                Name = "Logitech Mouse (Receiver Slot 3)",
                                Path = longPath,
                                ShortPath = shortPath,
                                Transport = IdentifyTransport(pid, longPath),
                                DeviceIndex = 3,
                                Vid = LogitechVid,
                                Pid = pid,
                                ChangeHostFeatureIndex = 0x09,
                                AllPaths = new List<string> { longPath }
                            };
                            if (seenNames.Add(devKeyboard.Name)) found.Add(devKeyboard);
                            if (seenNames.Add(devMouse.Name)) found.Add(devMouse);
                        }
                    }
                }

                _cachedDevices = found;
                _lastScanTime = now;

                AppLogger.Log("HID++", $"Scan complete: found {found.Count} compatible Logitech device(s).");
                return FilterDevices(found, targetKeywords);
            }
        }

        private void InspectDeviceEndpoint(
            string path,
            Dictionary<ushort, string> receiversCol01,
            Dictionary<ushort, string> receiversCol02,
            List<(string Name, string Path, ushort Pid, ushort UsagePage, ushort Usage)> bluetoothCandidates)
        {
            try
            {
                using var handle = CreateFile(
                    path,
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    IntPtr.Zero,
                    OPEN_EXISTING,
                    FILE_FLAG_OVERLAPPED,
                    IntPtr.Zero
                );

                if (handle.IsInvalid) return;

                var attrs = new HIDD_ATTRIBUTES();
                attrs.Size = Marshal.SizeOf(typeof(HIDD_ATTRIBUTES));

                if (!HidD_GetAttributes(handle, ref attrs) || attrs.VendorID != LogitechVid)
                    return;

                if (!HidD_GetPreparsedData(handle, out var ppd))
                    return;

                var caps = new HIDP_CAPS();
                HidP_GetCaps(ppd, ref caps);
                HidD_FreePreparsedData(ppd);

                var pLower = path.ToLowerInvariant();

                // Receiver endpoint classification
                if (AllReceiverPids.Contains(attrs.ProductID) || caps.UsagePage == 0xFF00)
                {
                    if ((caps.UsagePage == 0xFF00 && caps.Usage == 0x0001) || pLower.Contains("col01"))
                    {
                        receiversCol01[attrs.ProductID] = path;
                    }
                    else if ((caps.UsagePage == 0xFF00 && caps.Usage == 0x0002) || pLower.Contains("col02"))
                    {
                        receiversCol02[attrs.ProductID] = path;
                    }
                    return;
                }

                // Direct Bluetooth endpoint classification
                bool isBluetooth = (caps.UsagePage == 0xFF43 && caps.Usage == 0x0202)
                    || pLower.Contains("bth")
                    || pLower.Contains("bluetooth");

                if (isBluetooth)
                {
                    var prodBuffer = new StringBuilder(256);
                    HidD_GetProductString(handle, prodBuffer, 256);
                    var prodName = prodBuffer.ToString().Trim();
                    if (string.IsNullOrEmpty(prodName))
                        prodName = $"Logitech Device (PID 0x{attrs.ProductID:X4})";

                    bluetoothCandidates.Add((prodName, path, attrs.ProductID, caps.UsagePage, caps.Usage));
                }
            }
            catch
            {
                // Unreadable or access denied interface
            }
        }

        private List<LogitechDevice> QueryReceiverPairedDevices(string longPath, string? shortPath, ushort pid, TransportType transport)
        {
            var results = new List<LogitechDevice>();

            try
            {
                using var handle = CreateFile(
                    longPath,
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    IntPtr.Zero,
                    OPEN_EXISTING,
                    FILE_FLAG_OVERLAPPED,
                    IntPtr.Zero
                );

                if (handle.IsInvalid) return results;

                var hReadEvent = CreateEvent(IntPtr.Zero, true, false, null);
                if (hReadEvent == IntPtr.Zero) return results;

                var pReadOverlapped = Marshal.AllocHGlobal(Marshal.SizeOf<OVERLAPPED>());
                try
                {
                    // Query each slot 1..6 with safe 75ms non-blocking overlapped timeout
                    for (byte idx = 1; idx <= 6; idx++)
                    {
                        // Query feature 0x0005 (device name)
                        var q = new byte[20];
                        q[0] = 0x11;
                        q[1] = idx;
                        q[4] = 0x00;
                        q[5] = (byte)(FeatureDeviceName & 0xFF);

                        OverlappedWrite(handle, q);
                        var resp = OverlappedRead(handle, hReadEvent, pReadOverlapped, 75);

                        if (resp != null && resp.Length >= 5 && resp[0] == 0x11 && resp[1] == idx && resp[2] == 0x00 && resp[4] != 0)
                        {
                            var nameFeat = resp[4];

                            // Read name chunk 0
                            var nq = new byte[20];
                            nq[0] = 0x11;
                            nq[1] = idx;
                            nq[2] = nameFeat;
                            nq[3] = 0x10;
                            nq[4] = 0x00;
                            OverlappedWrite(handle, nq);
                            var nresp = OverlappedRead(handle, hReadEvent, pReadOverlapped, 75);

                            string devName = "Unknown";
                            if (nresp != null && nresp.Length >= 5 && nresp[0] == 0x11 && nresp[1] == idx)
                            {
                                devName = Encoding.UTF8.GetString(nresp, 4, 16).Trim('\0', ' ');
                            }

                            if (string.IsNullOrEmpty(devName) || devName == "Unknown")
                            {
                                devName = $"Receiver Device Slot {idx}";
                            }

                            // Query feature 0x1814 (Change Host)
                            var chq = new byte[20];
                            chq[0] = 0x11;
                            chq[1] = idx;
                            chq[4] = (byte)((FeatureChangeHost >> 8) & 0xFF);
                            chq[5] = (byte)(FeatureChangeHost & 0xFF);
                            OverlappedWrite(handle, chq);
                            var chresp = OverlappedRead(handle, hReadEvent, pReadOverlapped, 75);

                            byte chFeat = (byte)(devName.ToLowerInvariant().Contains("master") ? 0x08 : 0x09);
                            bool resolved = false;
                            if (chresp != null && chresp.Length >= 5 && chresp[0] == 0x11 && chresp[1] == idx && chresp[2] == 0x00 && chresp[4] != 0)
                            {
                                chFeat = chresp[4];
                                resolved = true;
                            }

                            var dev = new LogitechDevice
                            {
                                Name = devName,
                                Path = longPath,
                                ShortPath = shortPath,
                                Transport = transport,
                                DeviceIndex = idx,
                                Vid = LogitechVid,
                                Pid = pid,
                                ChangeHostFeatureIndex = chFeat,
                                FeatureResolved = resolved,
                                AllPaths = new List<string> { longPath }
                            };

                            results.Add(dev);
                            _receiverSlotsCache[(pid, idx)] = dev;
                            AppLogger.Log("HID++", $"Receiver paired device discovered on Slot {idx}: '{dev.Name}' (Feat=0x{chFeat:X2})");
                        }
                    }
                }
                finally
                {
                    Marshal.FreeHGlobal(pReadOverlapped);
                    CloseHandle(hReadEvent);
                }
            }
            catch (Exception ex)
            {
                AppLogger.LogDebug("HID++", $"Error querying receiver paired devices: {ex.Message}");
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
                if (n.Contains("slot 1") || n.Contains("slot 2") || n.Contains("slot 3"))
                    return true;
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
                        FILE_FLAG_OVERLAPPED,
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

                        if (OverlappedWrite(handle, packet))
                        {
                            ok = true;
                            // For Bluetooth devices send an immediate follow-up to guarantee transmission
                            if (dev.Transport == TransportType.Bluetooth)
                            {
                                System.Threading.Thread.Sleep(15);
                                OverlappedWrite(handle, packet);
                            }
                            break;
                        }
                    }

                    // Also transmit to short report endpoint if Unifying col01 is present
                    if (dev.IsReceiver && !string.IsNullOrEmpty(dev.ShortPath))
                    {
                        try
                        {
                            using var shortHandle = CreateFile(
                                dev.ShortPath,
                                GENERIC_READ | GENERIC_WRITE,
                                FILE_SHARE_READ | FILE_SHARE_WRITE,
                                IntPtr.Zero,
                                OPEN_EXISTING,
                                FILE_FLAG_OVERLAPPED,
                                IntPtr.Zero
                            );
                            if (!shortHandle.IsInvalid)
                            {
                                var shortPacket = new byte[7];
                                shortPacket[0] = 0x10;
                                shortPacket[1] = dev.DeviceIndex;
                                shortPacket[2] = dev.ChangeHostFeatureIndex;
                                shortPacket[3] = 0x1E;
                                shortPacket[4] = channelIndex;
                                OverlappedWrite(shortHandle, shortPacket);
                            }
                        }
                        catch { }
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
