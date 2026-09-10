#!/usr/bin/env python3
"""
Lunifier 2.0 Native Launcher for Linux (Ubuntu 24.04+).
Starts the native GTK4 + Libadwaita GUI or runs the daemon headless.
"""

import sys
import os
import signal
import argparse

# Ensure local package path is prioritized
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from lunifier.config import AppConfig
from lunifier.logger import log, set_log_level
from lunifier.app import LunifierApp


def run_gui():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from lunifier.window import LunifierAdwaitaApp

        app = LunifierAdwaitaApp()
        return app.run(sys.argv[:1])
    except Exception as ex:
        log("Launcher", f"Error launching GTK4/Libadwaita GUI: {ex}")
        log("Launcher", "Falling back to headless daemon mode.")
        run_daemon()


def run_daemon():
    cfg = AppConfig.load()
    app = LunifierApp(cfg)
    app.start()

    def sig_handler(sig, frame):
        log("Launcher", "Shutdown signal received. Stopping daemon...")
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    try:
        while True:
            signal.pause()
    except (KeyboardInterrupt, SystemExit):
        app.stop()
    except AttributeError:
        # Windows or non-POSIX pause fallback
        import time
        while True:
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(
        prog="lunifier",
        description="Lunifier 2.0: Seamless Logitech Easy-Switch Flow for Linux"
    )
    parser.add_argument("--gui", action="store_true", help="Launch native GNOME Libadwaita GUI")
    parser.add_argument("--daemon", action="store_true", help="Run background daemon service without GUI")
    parser.add_argument("--log-level", choices=["none", "normal", "debug"], default=None, help="Override log level")

    args = parser.parse_args()

    if args.log_level:
        set_log_level(args.log_level)

    if args.gui:
        sys.exit(run_gui())
    elif args.daemon:
        run_daemon()
    else:
        # If DISPLAY or WAYLAND_DISPLAY is set, launch GUI by default; otherwise daemon
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            sys.exit(run_gui())
        else:
            run_daemon()


if __name__ == "__main__":
    main()
