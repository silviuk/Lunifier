using System;
using System.Threading;
using System.Windows;
using Application = System.Windows.Application;
using MessageBox = System.Windows.MessageBox;
using Lunifier.Windows.Core;

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
                            if (MainWindow != null)
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
