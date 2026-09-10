using System;
using System.Runtime.InteropServices;
using System.Threading;

namespace Lunifier.Windows.Core
{
    public static class ClipboardHelper
    {
        private const uint CF_UNICODETEXT = 13;
        private const uint GMEM_MOVEABLE = 0x0002;

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool OpenClipboard(IntPtr hWndNewOwner);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool CloseClipboard();

        [DllImport("user32.dll", SetLastError = true)]
        private static extern bool EmptyClipboard();

        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr GetClipboardData(uint uFormat);

        [DllImport("user32.dll", SetLastError = true)]
        private static extern IntPtr SetClipboardData(uint uFormat, IntPtr hMem);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr GlobalAlloc(uint uFlags, UIntPtr dwBytes);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr GlobalLock(IntPtr hMem);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GlobalUnlock(IntPtr hMem);

        public static string GetText()
        {
            for (int attempt = 0; attempt < 5; attempt++)
            {
                if (OpenClipboard(IntPtr.Zero))
                {
                    try
                    {
                        var hData = GetClipboardData(CF_UNICODETEXT);
                        if (hData != IntPtr.Zero)
                        {
                            var pData = GlobalLock(hData);
                            if (pData != IntPtr.Zero)
                            {
                                try
                                {
                                    return Marshal.PtrToStringUni(pData) ?? string.Empty;
                                }
                                finally
                                {
                                    GlobalUnlock(hData);
                                }
                            }
                        }
                        return string.Empty;
                    }
                    finally
                    {
                        CloseClipboard();
                    }
                }
                Thread.Sleep(20);
            }
            return string.Empty;
        }

        public static bool SetText(string text)
        {
            if (string.IsNullOrEmpty(text))
                return false;

            for (int attempt = 0; attempt < 5; attempt++)
            {
                if (OpenClipboard(IntPtr.Zero))
                {
                    try
                    {
                        EmptyClipboard();
                        var bytes = (text.Length + 1) * 2;
                        var hMem = GlobalAlloc(GMEM_MOVEABLE, (UIntPtr)bytes);
                        if (hMem == IntPtr.Zero)
                            return false;

                        var pMem = GlobalLock(hMem);
                        if (pMem == IntPtr.Zero)
                            return false;

                        try
                        {
                            Marshal.Copy(text.ToCharArray(), 0, pMem, text.Length);
                            Marshal.WriteInt16(pMem, text.Length * 2, 0); // Null terminator
                        }
                        finally
                        {
                            GlobalUnlock(hMem);
                        }

                        SetClipboardData(CF_UNICODETEXT, hMem);
                        return true;
                    }
                    finally
                    {
                        CloseClipboard();
                    }
                }
                Thread.Sleep(20);
            }
            return false;
        }
    }

    public static class CursorHelper
    {
        [DllImport("user32.dll")]
        private static extern bool SetCursorPos(int X, int Y);

        public static bool SetPosition(int x, int y)
        {
            try
            {
                return SetCursorPos(x, y);
            }
            catch (Exception ex)
            {
                AppLogger.Log("Cursor", $"SetCursorPos error: {ex.Message}");
                return false;
            }
        }

        public static void PositionAtEntry(string entryEdge, double ratio, (int Left, int Top, int Right, int Bottom) bounds)
        {
            ratio = Math.Clamp(ratio, 0.0, 1.0);
            const int margin = 60; // Safe inward margin from edge to prevent bounceback

            int w = Math.Max(1, bounds.Right - bounds.Left);
            int h = Math.Max(1, bounds.Bottom - bounds.Top);

            var e = (entryEdge ?? "left").ToLowerInvariant();
            int targetX, targetY;

            switch (e)
            {
                case "left":
                    targetX = bounds.Left + margin;
                    targetY = bounds.Top + (int)(ratio * h);
                    break;
                case "right":
                    targetX = bounds.Right - margin;
                    targetY = bounds.Top + (int)(ratio * h);
                    break;
                case "top":
                    targetX = bounds.Left + (int)(ratio * w);
                    targetY = bounds.Top + margin;
                    break;
                case "bottom":
                    targetX = bounds.Left + (int)(ratio * w);
                    targetY = bounds.Bottom - margin;
                    break;
                default:
                    targetX = bounds.Left + (w / 2);
                    targetY = bounds.Top + (h / 2);
                    break;
            }

            SetPosition(targetX, targetY);
        }
    }
}
