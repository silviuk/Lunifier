"""
Lunifier - Seamless Cross-Platform Logitech Easy-Switch Screen Flow
Autonomous multi-border screen switching for Logitech keyboards and mice.
"""

import sys

# Ensure Xlib multi-threading is initialized before Tkinter or any X11 client connects
if sys.platform.startswith("linux"):
    try:
        import ctypes
        x11 = ctypes.cdll.LoadLibrary("libX11.so.6")
        if hasattr(x11, "XInitThreads"):
            x11.XInitThreads.restype = ctypes.c_int
            x11.XInitThreads()
    except Exception:
        pass

__version__ = "1.0.5"

