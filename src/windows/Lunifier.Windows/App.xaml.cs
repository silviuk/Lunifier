using System;
using System.Threading;
using System.Windows;
using Application = System.Windows.Application;
using MessageBox = System.Windows.MessageBox;
using Lunifier.Windows.Core;
using Lunifier.Windows.Config;

namespace Lunifier.Windows
{
    public partial class App : Application
    {
        private const string MutexName = "Global\\Lunifier_SingleInstance_Mutex";
        private const string EventName = "Global\\Lunifier_ShowWindow_Event";

        private Mutex? _singleInstanceMutex;
        private EventWaitHandle? _showWindowEvent;
        private Thread? _eventListenerThread;
        private bool _isPrimaryInstance;

        private static bool? _isNoBtSync;
        public static bool IsNoBtSync
        {
            get
            {
                if (_isNoBtSync.HasValue) return _isNoBtSync.Value;
#if NO_BTSYNC
                _isNoBtSync = true;
                return true;
#else
                var processPath = Environment.ProcessPath ?? "";
                if (processPath.IndexOf("nobtsync", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    _isNoBtSync = true;
                    return true;
                }
                var env = Environment.GetEnvironmentVariable("LUNIFIER_NO_BTSYNC");
                if (!string.IsNullOrEmpty(env) && env != "0" && !env.Equals("false", StringComparison.OrdinalIgnoreCase))
                {
                    _isNoBtSync = true;
                    return true;
                }
                var args = Environment.GetCommandLineArgs();
                foreach (var arg in args)
                {
                    if (arg.Equals("--no-btsync", StringComparison.OrdinalIgnoreCase) ||
                        arg.Equals("-nobtsync", StringComparison.OrdinalIgnoreCase) ||
                        arg.Equals("/nobtsync", StringComparison.OrdinalIgnoreCase))
                    {
                        _isNoBtSync = true;
                        return true;
                    }
                }
                _isNoBtSync = false;
                return false;
#endif
            }
        }

        protected override void OnStartup(StartupEventArgs e)
        {
            try
            {
                _singleInstanceMutex = new Mutex(true, MutexName, out _isPrimaryInstance);
            }
            catch
            {
                _isPrimaryInstance = true;
            }

            if (!_isPrimaryInstance)
            {
                // Signal existing instance to restore and show its window
                try
                {
                    using var evt = EventWaitHandle.OpenExisting(EventName);
                    evt.Set();
                }
                catch { }

                Shutdown();
                return;
            }

            // Primary instance: create wait handle and listener thread
            try
            {
                _showWindowEvent = new EventWaitHandle(false, EventResetMode.AutoReset, EventName);
                _eventListenerThread = new Thread(() =>
                {
                    while (_showWindowEvent.WaitOne())
                    {
                        Dispatcher.Invoke(() =>
                        {
                            if (MainWindow is MainWindow mw)
                            {
                                mw.RestoreFromTray();
                            }
                            else if (MainWindow != null)
                            {
                                if (MainWindow.WindowState == WindowState.Minimized)
                                    MainWindow.WindowState = WindowState.Normal;
                                MainWindow.Show();
                                MainWindow.Activate();
                                MainWindow.Focus();
                            }
                        });
                    }
                })
                {
                    IsBackground = true,
                    Name = "SingleInstanceEventListener"
                };
                _eventListenerThread.Start();
            }
            catch { }

            AppDomain.CurrentDomain.UnhandledException += (s, args) =>
            {
                var ex = args.ExceptionObject as Exception;
                AppLogger.Log("Crash", $"Unhandled Domain Exception: {ex}");
                MessageBox.Show($"Lunifier encountered an unhandled error:\n\n{ex?.Message}\n\nStack Trace:\n{ex?.StackTrace}",
                    "Lunifier - Critical Error", MessageBoxButton.OK, MessageBoxImage.Error);
            };

            DispatcherUnhandledException += (s, args) =>
            {
                AppLogger.Log("Crash", $"Unhandled Dispatcher Exception: {args.Exception}");
                MessageBox.Show($"Lunifier encountered an error:\n\n{args.Exception.Message}\n\nStack Trace:\n{args.Exception.StackTrace}",
                    "Lunifier - Error", MessageBoxButton.OK, MessageBoxImage.Error);
                args.Handled = true;
            };

            ThemeManager.Initialize();

            base.OnStartup(e);

            var cfg = AppConfig.Load();
            bool startMinimized = cfg.StartMinimized;
            if (e.Args != null)
            {
                foreach (var arg in e.Args)
                {
                    var a = arg.Trim().ToLowerInvariant();
                    if (a is "--minimized" or "-minimized" or "/minimized" or "--daemon" or "-d" or "/daemon")
                    {
                        startMinimized = true;
                        break;
                    }
                    if (a is "--gui" or "-gui" or "/gui" or "--show" or "-show")
                    {
                        startMinimized = false;
                        break;
                    }
                }
            }

            var mainWindow = new MainWindow(startMinimized);
            MainWindow = mainWindow;

            if (startMinimized)
            {
                mainWindow.WindowState = WindowState.Minimized;
                mainWindow.ShowInTaskbar = false;
                mainWindow.Visibility = Visibility.Hidden;
                mainWindow.Show();
                mainWindow.Hide();
            }
            else
            {
                mainWindow.Show();
            }
        }

        protected override void OnExit(ExitEventArgs e)
        {
            try
            {
                if (_isPrimaryInstance)
                {
                    _singleInstanceMutex?.ReleaseMutex();
                    _singleInstanceMutex?.Dispose();
                    _showWindowEvent?.Dispose();
                }
            }
            catch { }

            base.OnExit(e);
        }
    }
}
