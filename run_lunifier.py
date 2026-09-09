import io
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

# When running with console=False on Windows, sys.stdout and sys.stderr can be None.
# Provide dummy streams to protect external libraries from AttributeError.
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

from lunifier.app import main

if __name__ == "__main__":
    main()

