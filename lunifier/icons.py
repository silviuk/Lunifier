"""
Centralized resource and application icon management for Lunifier.
Provides reliable icon loading across development mode, installed packages,
and PyInstaller / frozen binaries on Windows and Linux.
"""

import os
import sys
from typing import Optional
from PIL import Image

try:
    import tkinter as tk
except ImportError:
    tk = None

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

_cached_png_photo = None
_cached_pil_image = None
_app_user_model_id_set = False


def get_resource_path(filename: str) -> str:
    """
    Resolves the absolute path to a resource file.
    Supports PyInstaller frozen bundles (sys._MEIPASS) and standard source distributions.
    """
    if hasattr(sys, "_MEIPASS"):
        p = os.path.join(sys._MEIPASS, "lunifier", "resources", filename)
        if os.path.exists(p):
            return p
        p2 = os.path.join(sys._MEIPASS, filename)
        if os.path.exists(p2):
            return p2
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "resources", filename))


def init_windows_app_id(app_id: str = "silviuk.lunifier.app.1.0") -> None:
    """
    Configures Windows Application User Model ID so the OS taskbar and Alt+Tab
    properly display the application icon and group windows under Lunifier.
    """
    global _app_user_model_id_set
    if sys.platform == "win32" and not _app_user_model_id_set:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            _app_user_model_id_set = True
        except Exception:
            pass


def get_icon_pil() -> Optional[Image.Image]:
    """
    Loads and returns the official Lunifier master PIL Image.
    """
    global _cached_pil_image
    if _cached_pil_image is not None:
        return _cached_pil_image.copy()

    png_path = get_resource_path("icon.png")
    if os.path.exists(png_path):
        try:
            img = Image.open(png_path)
            _cached_pil_image = img
            return img.copy()
        except Exception:
            pass
    return None


def get_icon_ctk(size=(32, 32)) -> Optional["ctk.CTkImage"]:
    """
    Creates a CTkImage of the Lunifier logo suitable for CustomTkinter widgets and window headers.
    """
    if ctk is None:
        return None
    pil_img = get_icon_pil()
    if pil_img:
        try:
            return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
        except Exception:
            pass
    return None


def set_window_icon(window) -> None:
    """
    Sets the unified Lunifier window icon across Windows and Linux.
    Sets both iconbitmap (.ico) and iconphoto (Tk PhotoImage) for maximum
    compatibility with taskbar, window title bar, and Alt+Tab switchers.
    """
    global _cached_png_photo
    init_windows_app_id()

    ico_path = get_resource_path("icon.ico")
    png_path = get_resource_path("icon.png")

    if sys.platform == "win32" and os.path.exists(ico_path):
        try:
            window.iconbitmap(ico_path)
        except Exception:
            pass

    if tk is not None and os.path.exists(png_path):
        try:
            if _cached_png_photo is None:
                _cached_png_photo = tk.PhotoImage(file=png_path)
            window.iconphoto(True, _cached_png_photo)
        except Exception:
            pass
