using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;
using Color = System.Windows.Media.Color;
using Application = System.Windows.Application;

namespace Lunifier.Windows.Core
{
    public static class ThemeManager
    {
        [DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int attrValue, int attrSize);

        private const int DWMWA_USE_IMMERSIVE_DARK_MODE = 20;

        public static bool IsDark { get; private set; } = true;
        public static event Action<bool>? ThemeChanged;

        public static void Initialize()
        {
            try
            {
                SystemEvents.UserPreferenceChanged += (s, e) =>
                {
                    if (e.Category == UserPreferenceCategory.General || e.Category == UserPreferenceCategory.Color)
                    {
                        Application.Current?.Dispatcher?.Invoke(() =>
                        {
                            ApplySystemTheme();
                        });
                    }
                };
            }
            catch { }

            ApplySystemTheme();
        }

        public static bool DetectSystemDarkMode()
        {
            try
            {
                using var key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize");
                if (key?.GetValue("AppsUseLightTheme") is int lightVal)
                {
                    return lightVal == 0;
                }
            }
            catch { }
            return true; // Default dark
        }

        public static void ApplySystemTheme()
        {
            ApplyTheme(DetectSystemDarkMode());
        }

        public static void ApplyTheme(bool isDark)
        {
            IsDark = isDark;
            var app = Application.Current;
            if (app == null) return;

            var res = app.Resources;

            if (isDark)
            {
                // Dark Theme Palette (Modern Slate Dark)
                res["WindowBackground"] = new SolidColorBrush(Color.FromRgb(0x0F, 0x17, 0x2A)); // #0F172A
                res["CardBackground"] = new SolidColorBrush(Color.FromRgb(0x1E, 0x29, 0x3B));   // #1E293B
                res["CardBorder"] = new SolidColorBrush(Color.FromRgb(0x33, 0x41, 0x55));       // #334155
                res["SubtleBackground"] = new SolidColorBrush(Color.FromRgb(0x14, 0x1E, 0x33)); // #141E33
                res["InputBackground"] = new SolidColorBrush(Color.FromRgb(0x0F, 0x17, 0x2A));  // #0F172A
                res["InputBorder"] = new SolidColorBrush(Color.FromRgb(0x47, 0x55, 0x69));      // #475569
                res["TextPrimary"] = new SolidColorBrush(Color.FromRgb(0xF8, 0xFA, 0xFC));      // #F8FAFC
                res["TextSecondary"] = new SolidColorBrush(Color.FromRgb(0x94, 0xA3, 0xB8));    // #94A3B8
                res["SectionHeader"] = new SolidColorBrush(Color.FromRgb(0x38, 0xBD, 0xF8));    // #38BDF8
                res["AccentColor"] = new SolidColorBrush(Color.FromRgb(0x02, 0x84, 0xC7));      // #0284C7
                res["AccentHover"] = new SolidColorBrush(Color.FromRgb(0x03, 0x69, 0xA1));      // #0369A1
                res["DropdownBackground"] = new SolidColorBrush(Color.FromRgb(0x1E, 0x29, 0x3B));
                res["DropdownBorder"] = new SolidColorBrush(Color.FromRgb(0x47, 0x55, 0x69));
                res["ItemHoverBackground"] = new SolidColorBrush(Color.FromRgb(0x33, 0x41, 0x55));
                res["ItemSelectedBackground"] = new SolidColorBrush(Color.FromRgb(0x02, 0x84, 0xC7));
                res["LogsBoxForeground"] = new SolidColorBrush(Color.FromRgb(0x90, 0xCA, 0xF9));
            }
            else
            {
                // Light Theme Palette (Clean Slate Light)
                res["WindowBackground"] = new SolidColorBrush(Color.FromRgb(0xF1, 0xF5, 0xF9)); // #F1F5F9
                res["CardBackground"] = new SolidColorBrush(Color.FromRgb(0xFF, 0xFF, 0xFF));   // #FFFFFF
                res["CardBorder"] = new SolidColorBrush(Color.FromRgb(0xCB, 0xD5, 0xE1));       // #CBD5E1
                res["SubtleBackground"] = new SolidColorBrush(Color.FromRgb(0xE2, 0xE8, 0xF0)); // #E2E8F0
                res["InputBackground"] = new SolidColorBrush(Color.FromRgb(0xFF, 0xFF, 0xFF));  // #FFFFFF
                res["InputBorder"] = new SolidColorBrush(Color.FromRgb(0x94, 0xA3, 0xB8));      // #94A3B8
                res["TextPrimary"] = new SolidColorBrush(Color.FromRgb(0x0F, 0x17, 0x2A));      // #0F172A
                res["TextSecondary"] = new SolidColorBrush(Color.FromRgb(0x47, 0x55, 0x69));    // #475569
                res["SectionHeader"] = new SolidColorBrush(Color.FromRgb(0x02, 0x84, 0xC7));    // #0284C7
                res["AccentColor"] = new SolidColorBrush(Color.FromRgb(0x02, 0x84, 0xC7));      // #0284C7
                res["AccentHover"] = new SolidColorBrush(Color.FromRgb(0x03, 0x69, 0xA1));      // #0369A1
                res["DropdownBackground"] = new SolidColorBrush(Color.FromRgb(0xFF, 0xFF, 0xFF));
                res["DropdownBorder"] = new SolidColorBrush(Color.FromRgb(0xCB, 0xD5, 0xE1));
                res["ItemHoverBackground"] = new SolidColorBrush(Color.FromRgb(0xE2, 0xE8, 0xF0));
                res["ItemSelectedBackground"] = new SolidColorBrush(Color.FromRgb(0x02, 0x84, 0xC7));
                res["LogsBoxForeground"] = new SolidColorBrush(Color.FromRgb(0x03, 0x69, 0xA1));
            }

            ThemeChanged?.Invoke(isDark);
        }

        public static void ApplyTitleBarTheme(IntPtr hwnd, bool isDark)
        {
            try
            {
                int val = isDark ? 1 : 0;
                DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ref val, sizeof(int));
            }
            catch { }
        }
    }
}
