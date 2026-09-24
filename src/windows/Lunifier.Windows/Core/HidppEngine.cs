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

        [DllImport("hid.dll", SetLastError = true)]
        private static extern bool HidD_SetOutputReport(SafeFileHandle hidDeviceObject, byte[] reportBuffer, uint reportBufferLength);

        [DllImport("hid.dll", SetLastError = true)]
        private static extern bool HidD_SetFeature(SafeFileHandle hidDeviceObject, byte[] reportBuffer, uint reportBufferLength);

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

        public static string GuessNameFromPid(ushort pid) => pid switch
        {
            // Bluetooth PIDs
            0xB012 => "Logitech MX Master",
            0xB015 => "Logitech M720 Triathlon",
            0xB016 => "Logitech M585 / M590 Mouse",
            0xB017 => "Logitech MX Master 2S",
            0xB01B => "Logitech MX Ergo",
            0xB01D => "Logitech Pebble M350",
            0xB01E => "Logitech MX Anywhere 2S",
            0xB01F => "Logitech M330 Silent Plus",
            0xB023 => "Logitech MX Master 3",
            0xB025 => "Logitech MX Vertical",
            0xB028 => "Logitech MX Master 3S",
            0xB02A => "Logitech Lift Vertical Mouse",
            0xB02F => "Logitech POP Mouse",
            0xB034 or 0xB035 => "Logitech Signature M650",
            0xB342 => "Logitech K380 Multi-Device Keyboard",
            0xB34B => "Logitech K375s Multi-Device Keyboard",
            0xB350 => "Logitech Craft Keyboard",
            0xB352 => "Logitech K850 Performance Keyboard",
            0xB354 => "Logitech ERGO K860 Keyboard",
            0xB359 => "Logitech K780 Multi-Device Keyboard",
            0xB35B => "Logitech MX Keys",
            0xB366 => "Logitech Signature K650",
            0xB367 => "Logitech POP Keys",
            0xB369 => "Logitech MX Keys Mini",
            // Unifying / Bolt Wireless PIDs (WPID)
            0x405E => "Logitech M720 Triathlon",
            0x4069 => "Logitech MX Master 2S",
            0x406B => "Logitech K375s Keyboard",
            0x407A => "Logitech K780 Keyboard",
            0x407B => "Logitech K850 Keyboard",
            0x4082 => "Logitech Craft Keyboard",
            0x4086 => "Logitech ERGO K860 Keyboard",
            0x4088 => "Logitech MX Master 3",
            0x408A => "Logitech MX Keys Keyboard",
            0x408D => "Logitech MX Anywhere 3",
            0x408F => "Logitech POP Keys",
            0x4090 => "Logitech POP Mouse",
            0x4091 or 0x4095 => "Logitech MX Keys Mini",
            0x4092 or 0x4094 => "Logitech Lift Vertical Mouse",
            0x4093 => "Logitech MX Master 3S",
            _ => $"Logitech Device (PID 0x{pid:X4})"
        };

        public static TransportType IdentifyTransport(ushort pid, string path)
        {
            if (PidsUnifying.Contains(pid)) return TransportType.Unifying;
            if (PidsBolt.Contains(pid)) return TransportType.Bolt;
            if (PidsLightspeed.Contains(pid)) return TransportType.Lightspeed;

            var p = path.ToLowerInvariant();
            if (p.Contains("1812") || p.Contains("bth") || p.Contains("bluetooth"))
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

        private static SafeFileHandle OpenDeviceHandle(string path)
        {
            // Try 1: Overlapped GENERIC_READ | GENERIC_WRITE
            var h = CreateFile(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, IntPtr.Zero);
            if (!h.IsInvalid) return h;

            // Try 2: Overlapped GENERIC_WRITE only (Windows allows this for keyboard/mouse endpoints)
            h = CreateFile(path, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, IntPtr.Zero);
            if (!h.IsInvalid) return h;

            // Try 3: Non-overlapped GENERIC_WRITE
            h = CreateFile(path, GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, 0, IntPtr.Zero);
            return h;
        }

        private static bool WriteHidReport(SafeFileHandle handle, byte[] packet)
        {
            // Method 1: Overlapped WriteFile
            if (OverlappedWrite(handle, packet)) return true;

            // Method 2: Synchronous WriteFile
            if (WriteFile(handle, packet, (uint)packet.Length, out var written, IntPtr.Zero) && written > 0)
                return true;

            // Method 3: HidD_SetOutputReport
            if (HidD_SetOutputReport(handle, packet, (uint)packet.Length))
                return true;

            // Method 4: HidD_SetFeature
            if (HidD_SetFeature(handle, packet, (uint)packet.Length))
                return true;

            return false;
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
                var bluetoothCandidates = new List<(string Name, string Path, ushort Pid, ushort UsagePage, ushort Usage, ushort OutLen, ushort FeatLen)>();

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
                var bluetoothGroups = bluetoothCandidates.GroupBy(c => (c.Pid, c.Name));
                foreach (var group in bluetoothGroups)
                {
                    var transport = TransportType.Bluetooth;
                    if (!IsTransportSupported(transport)) continue;

                    var sorted = group.OrderByDescending(c =>
                    {
                        if (c.UsagePage == 0xFF43 && c.Usage == 0x0202) return 1000;
                        if (c.UsagePage >= 0xFF00) return 500;
                        if (c.OutLen >= 20 || c.FeatLen >= 20) return 200;
                        return 10;
                    }).ToList();

                    var primary = sorted[0];
                    byte defaultFeat = primary.Name.ToLowerInvariant().Contains("master") ? (byte)0x08 : (byte)0x09;

                    if (seenNames.Add(primary.Name))
                    {
                        var dev = new LogitechDevice
                        {
                            Name = primary.Name,
                            Path = primary.Path,
                            Transport = transport,
                            DeviceIndex = 0xFF,
                            Vid = LogitechVid,
                            Pid = primary.Pid,
                            UsagePage = primary.UsagePage,
                            Usage = primary.Usage,
                            ChangeHostFeatureIndex = defaultFeat,
                            AllPaths = sorted.Select(s => s.Path).Distinct().ToList()
                        };
                        found.Add(dev);
                    }
                    else
                    {
                        var existing = found.FirstOrDefault(d => string.Equals(d.Name, primary.Name, StringComparison.OrdinalIgnoreCase));
                        if (existing != null)
                        {
                            foreach (var s in sorted)
                            {
                                if (!existing.AllPaths.Contains(s.Path))
                                    existing.AllPaths.Add(s.Path);
                            }
                        }
                    }
                }

                // Restore any previously cached paired devices for discovered receivers so sleeping devices are never lost
                foreach (var (pid, longPath) in receiversCol02)
                {
                    receiversCol01.TryGetValue(pid, out var shortPath);
                    var cachedForReceiver = _receiverSlotsCache.Where(kv => kv.Key.Pid == pid).Select(kv => kv.Value).ToList();
                    foreach (var cDev in cachedForReceiver)
                    {
                        cDev.Path = longPath;
                        cDev.ShortPath = shortPath;
                        if (seenNames.Add(cDev.Name))
                        {
                            found.Add(cDev);
                            AppLogger.Log("HID++", $"Retained sleeping receiver device on Slot {cDev.DeviceIndex}: '{cDev.Name}'");
                        }
                    }

                    if (found.Count == 0 && cachedForReceiver.Count == 0)
                    {
                        var allPaths = new List<string> { longPath };
                        if (!string.IsNullOrEmpty(shortPath) && !allPaths.Contains(shortPath))
                            allPaths.Add(shortPath);

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
                            FeatureResolved = false,
                            AllPaths = new List<string>(allPaths)
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
                            FeatureResolved = false,
                            AllPaths = new List<string>(allPaths)
                        };
                        if (seenNames.Add(devKeyboard.Name)) found.Add(devKeyboard);
                        if (seenNames.Add(devMouse.Name)) found.Add(devMouse);
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
            List<(string Name, string Path, ushort Pid, ushort UsagePage, ushort Usage, ushort OutLen, ushort FeatLen)> bluetoothCandidates)
        {
            try
            {
                using var handle = CreateFile(
                    path,
                    0, // Query access: Windows NEVER denies this even for mouse/keyboard endpoints!
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
                bool isReceiverPid = AllReceiverPids.Contains(attrs.ProductID);
                bool isHidppPage = caps.UsagePage == 0xFF00 || caps.UsagePage == 0xFF43;

                if (isReceiverPid)
                {
                    if (isHidppPage)
                    {
                        if (caps.Usage == 0x0001 || caps.OutputReportByteLength == 7 || pLower.Contains("col01"))
                        {
                            receiversCol01[attrs.ProductID] = path;
                        }
                        else if (caps.Usage == 0x0002 || caps.OutputReportByteLength == 20 || (pLower.Contains("col02") && !pLower.Contains("col03")))
                        {
                            receiversCol02[attrs.ProductID] = path;
                        }
                    }
                    return; // Never let standard keyboard/mouse collections of a receiver become bluetooth candidates
                }

                // Direct Bluetooth / USB endpoint classification
                var prodBuffer = new StringBuilder(256);
                HidD_GetProductString(handle, prodBuffer, 256);
                var prodName = prodBuffer.ToString().Trim();
                if (string.IsNullOrEmpty(prodName) || prodName.Equals("Logitech Device", StringComparison.OrdinalIgnoreCase))
                {
                    prodName = GuessNameFromPid(attrs.ProductID);
                }

                bluetoothCandidates.Add((prodName, path, attrs.ProductID, caps.UsagePage, caps.Usage, caps.OutputReportByteLength, caps.FeatureReportByteLength));
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

                using var shortHandle = !string.IsNullOrEmpty(shortPath)
                    ? CreateFile(shortPath, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, IntPtr.Zero, OPEN_EXISTING, FILE_FLAG_OVERLAPPED, IntPtr.Zero)
                    : null;

                var hReadEvent = CreateEvent(IntPtr.Zero, true, false, null);
                if (hReadEvent == IntPtr.Zero) return results;

                var pReadOverlapped = Marshal.AllocHGlobal(Marshal.SizeOf<OVERLAPPED>());
                try
                {
                    var allPaths = new List<string> { longPath };
                    if (!string.IsNullOrEmpty(shortPath) && !allPaths.Contains(shortPath))
                        allPaths.Add(shortPath);

                    // 1. Query receiver NVRAM pairing table (instant internal memory, no RF timeout)
                    var pairedSlots = new Dictionary<byte, (byte Type, ushort Wpid)>();
                    var nvramWriteHandle = (shortHandle != null && !shortHandle.IsInvalid) ? shortHandle : handle;

                    for (byte slot = 0; slot < 6; slot++)
                    {
                        var req = new byte[7];
                        req[0] = 0x10;
                        req[1] = 0xFF; // Receiver
                        req[2] = 0x83;
                        req[3] = 0xB5;
                        req[4] = (byte)(0x20 | slot);
                        req[5] = 0x00;
                        req[6] = 0x00;
                        OverlappedWrite(nvramWriteHandle, req);
                        var rresp = OverlappedRead(handle, hReadEvent, pReadOverlapped, 40);
                        if (rresp != null && rresp.Length >= 12 && rresp[0] == 0x11 && rresp[1] == 0xFF && rresp[2] == 0x83 && rresp[3] == 0xB5)
                        {
                            ushort wpid = (ushort)((rresp[7] << 8) | rresp[8]);
                            byte devType = rresp[11];
                            if (wpid != 0)
                            {
                                pairedSlots[(byte)(slot + 1)] = (devType, wpid);
                            }
                        }
                    }

                    // 2. Query each slot 1..6 over RF
                    for (byte idx = 1; idx <= 6; idx++)
                    {
                        bool foundLive = false;

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
                                AllPaths = new List<string>(allPaths)
                            };

                            results.Add(dev);
                            _receiverSlotsCache[(pid, idx)] = dev;
                            foundLive = true;
                            AppLogger.Log("HID++", $"Receiver paired device discovered on Slot {idx}: '{dev.Name}' (Feat=0x{chFeat:X2})");
                        }

                        // Fallback: If device is sleeping and didn't respond to RF query, but NVRAM confirms it's paired
                        if (!foundLive && pairedSlots.TryGetValue(idx, out var pInfo))
                        {
                            string synthName = GuessNameFromPid(pInfo.Wpid);
                            if (synthName.StartsWith("Logitech Device", StringComparison.OrdinalIgnoreCase))
                            {
                                synthName = (pInfo.Type == 1 || pInfo.Type == 3)
                                    ? $"Logitech Keyboard (Receiver Slot {idx})"
                                    : $"Logitech Mouse (Receiver Slot {idx})";
                            }
                            else
                            {
                                synthName += $" (Receiver Slot {idx})";
                            }

                            byte chFeat = (byte)(synthName.ToLowerInvariant().Contains("master") ? 0x08 : 0x09);
                            var dev = new LogitechDevice
                            {
                                Name = synthName,
                                Path = longPath,
                                ShortPath = shortPath,
                                Transport = transport,
                                DeviceIndex = idx,
                                Vid = LogitechVid,
                                Pid = pid,
                                ChangeHostFeatureIndex = chFeat,
                                FeatureResolved = false,
                                AllPaths = new List<string>(allPaths)
                            };

                            results.Add(dev);
                            _receiverSlotsCache[(pid, idx)] = dev;
                            AppLogger.Log("HID++", $"Receiver paired device (NVRAM, sleeping) on Slot {idx}: '{dev.Name}' (WPID=0x{pInfo.Wpid:X4})");
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
            if (!string.IsNullOrEmpty(dev.ShortPath) && !pathsToTry.Contains(dev.ShortPath))
            {
                pathsToTry.Add(dev.ShortPath);
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
                    using var handle = OpenDeviceHandle(devPath);
                    if (handle.IsInvalid) continue;

                    bool ok = false;
                    bool isShortEndpoint = devPath.ToLowerInvariant().Contains("col01");

                    if (!isShortEndpoint)
                    {
                        foreach (var featIdx in featureIndices)
                        {
                            var packet = new byte[20];
                            packet[0] = 0x11;
                            packet[1] = dev.DeviceIndex;
                            packet[2] = featIdx;
                            packet[3] = 0x10;          // Function 1: set_current_host
                            packet[4] = channelIndex;

                            if (WriteHidReport(handle, packet))
                            {
                                ok = true;
                                // For keyboards and Bluetooth devices, send follow-up bursts to wake sleeping RF transceivers
                                bool isKeyboard = dev.Name.ToLowerInvariant().Contains("keyboard");
                                if (isKeyboard || dev.Transport == TransportType.Bluetooth)
                                {
                                    for (int burst = 0; burst < 2; burst++)
                                    {
                                        Thread.Sleep(25);
                                        WriteHidReport(handle, packet);
                                    }
                                }
                                break;
                            }
                        }
                    }
                    else
                    {
                        foreach (var featIdx in featureIndices)
                        {
                            var shortPacket = new byte[7];
                            shortPacket[0] = 0x10;
                            shortPacket[1] = dev.DeviceIndex;
                            shortPacket[2] = featIdx;
                            shortPacket[3] = 0x1E;
                            shortPacket[4] = channelIndex;
                            if (WriteHidReport(handle, shortPacket))
                            {
                                ok = true;
                                if (dev.Name.ToLowerInvariant().Contains("keyboard"))
                                {
                                    Thread.Sleep(25);
                                    WriteHidReport(handle, shortPacket);
                                }
                                break;
                            }
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

            AppLogger.Log("HID++", $"switch_all_to_channel: Initiating switch for {devices.Count} device(s) -> Channel {targetChannel}");

            var results = new ConcurrentDictionary<string, bool>();

            // Group receiver devices by receiver endpoint so devices sharing the same physical dongle
            // are switched sequentially with 40ms spacing to prevent RF packet collision.
            // Prioritize keyboards first so sleeping keyboards receive wake/switch bursts before the active mouse.
            var receiverGroups = devices.Where(d => d.IsReceiver).GroupBy(d => d.Path ?? d.Name);
            var directDevices = devices.Where(d => !d.IsReceiver).ToList();

            var tasks = new List<Task>();

            foreach (var group in receiverGroups)
            {
                var groupList = group.OrderBy(d => d.Name.ToLowerInvariant().Contains("keyboard") ? 0 : 1).ToList();
                tasks.Add(Task.Run(() =>
                {
                    for (int i = 0; i < groupList.Count; i++)
                    {
                        var dev = groupList[i];
                        var ok = SwitchDeviceHost(dev, targetChannel);
                        results[$"{dev.Name} ({dev.Transport})"] = ok;

                        if (i < groupList.Count - 1)
                        {
                            Thread.Sleep(40);
                        }
                    }
                }));
            }

            foreach (var dev in directDevices)
            {
                tasks.Add(Task.Run(() =>
                {
                    var ok = SwitchDeviceHost(dev, targetChannel);
                    results[$"{dev.Name} ({dev.Transport})"] = ok;
                }));
            }

            Task.WaitAll(tasks.ToArray());

            return new Dictionary<string, bool>(results);
        }
    }
}
