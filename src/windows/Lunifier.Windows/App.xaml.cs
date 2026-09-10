using System;
using System.Windows;
using Lunifier.Windows.Core;

namespace Lunifier.Windows
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
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

            base.OnStartup(e);
        }
    }
}
