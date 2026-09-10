"""
System Autostart Configuration for Lunifier.
Supports Windows Run Registry and Linux XDG Autostart (.desktop).
"""

import os
import sys
from .logger import log

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

LINUX_AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
LINUX_AUTOSTART_FILE = os.path.join(LINUX_AUTOSTART_DIR, "lunifier.desktop")
WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "Lunifier"


def is_autostart_enabled() -> bool:
    """Checks if Lunifier is configured to start on user login."""
    if IS_WINDOWS:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, APP_NAME)
                return bool(val)
        except Exception:
            return False
    elif IS_LINUX:
        if os.path.isfile(LINUX_AUTOSTART_FILE):
            try:
                with open(LINUX_AUTOSTART_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "X-GNOME-Autostart-enabled=false" in content:
                        return False
                    return "lunifier" in content
            except Exception:
                return False
        return False
    return False


def set_autostart_enabled(enabled: bool) -> bool:
    """Enables or disables autostart on system login."""
    if IS_WINDOWS:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
                if enabled:
                    # If frozen executable (.exe)
                    if getattr(sys, "frozen", False):
                        exe_path = sys.executable
                        cmd = f'"{exe_path}" --daemon'
                    else:
                        exe_path = sys.executable
                        cmd = f'"{exe_path}" -m lunifier.app --daemon'
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                    log("Autostart", f"Windows autostart enabled: {cmd}")
                else:
                    try:
                        winreg.DeleteValue(key, APP_NAME)
                        log("Autostart", "Windows autostart disabled.")
                    except FileNotFoundError:
                        pass
            return True
        except Exception as e:
            log("Autostart", f"Failed to set Windows autostart: {e}")
            return False

    elif IS_LINUX:
        try:
            if enabled:
                os.makedirs(LINUX_AUTOSTART_DIR, exist_ok=True)
                # Determine command
                if getattr(sys, "frozen", False):
                    cmd = f"{sys.executable} --daemon"
                else:
                    cmd = "lunifier --daemon"

                content = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    f"Name={APP_NAME}\n"
                    "Comment=Seamless Logitech Easy-Switch Screen Flow\n"
                    f"Exec={cmd}\n"
                    "Icon=lunifier\n"
                    "Terminal=false\n"
                    "Categories=Utility;HardwareSettings;\n"
                    "X-GNOME-Autostart-enabled=true\n"
                )
                with open(LINUX_AUTOSTART_FILE, "w", encoding="utf-8") as f:
                    f.write(content)
                log("Autostart", f"Linux autostart enabled at {LINUX_AUTOSTART_FILE}")
            else:
                if os.path.exists(LINUX_AUTOSTART_FILE):
                    os.remove(LINUX_AUTOSTART_FILE)
                    log("Autostart", f"Linux autostart disabled (removed {LINUX_AUTOSTART_FILE})")
            return True
        except Exception as e:
            log("Autostart", f"Failed to set Linux autostart: {e}")
            return False

    return False
