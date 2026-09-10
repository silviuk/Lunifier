"""
Global Hotkey Manager for Lunifier.
Allows quick hardware channel switching across the entire OS (e.g. Ctrl+Alt+1/2/3)
using pynput with Windows RegisterHotKey fallback.
"""

import sys
import threading
from typing import Callable, Optional
from .logger import log

try:
    from pynput import keyboard
except ImportError:
    keyboard = None


class GlobalHotKeyManager:
    """
    Registers and listens for system-wide keyboard shortcuts to switch Easy-Switch channels.
    """
    def __init__(self, on_switch_channel: Callable[[int], None]):
        self.on_switch_channel = on_switch_channel
        self._listener = None
        self._win_thread: Optional[threading.Thread] = None
        self._win_running: bool = False

    def start(self,
              combo_ch1: str = "<ctrl>+<alt>+1",
              combo_ch2: str = "<ctrl>+<alt>+2",
              combo_ch3: str = "<ctrl>+<alt>+3") -> bool:
        """Starts listening for global hotkeys."""
        self.stop()

        # Primary method: pynput GlobalHotKeys
        if keyboard is not None:
            try:
                hotkey_map = {
                    combo_ch1: lambda: self._on_hotkey_triggered(1),
                    combo_ch2: lambda: self._on_hotkey_triggered(2),
                    combo_ch3: lambda: self._on_hotkey_triggered(3),
                }
                self._listener = keyboard.GlobalHotKeys(hotkey_map)
                self._listener.daemon = True
                self._listener.start()
                log("HotKeys", f"Registered global shortcuts: [1] {combo_ch1} | [2] {combo_ch2} | [3] {combo_ch3}")
                return True
            except Exception as e:
                log("HotKeys", f"pynput hotkeys registration failed: {e}")

        # Fallback for Windows: native ctypes RegisterHotKey
        if sys.platform == "win32":
            return self._start_windows_native_hotkeys()

        return False

    def _on_hotkey_triggered(self, channel: int) -> None:
        log("HotKeys", f"Global hotkey triggered -> Switch to Channel {channel}")
        if self.on_switch_channel:
            self.on_switch_channel(channel)

    def _start_windows_native_hotkeys(self) -> bool:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        MOD_NOREPEAT = 0x4000
        WM_HOTKEY = 0x0312

        self._win_running = True

        def win_msg_loop():
            # Register Hotkeys: ID 1 = Ch1, ID 2 = Ch2, ID 3 = Ch3
            # VK_1 = 0x31, VK_2 = 0x32, VK_3 = 0x33
            mods = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
            registered = []
            for ch, vk in [(1, 0x31), (2, 0x32), (3, 0x33)]:
                if user32.RegisterHotKey(None, ch, mods, vk):
                    registered.append(ch)
                else:
                    log("HotKeys", f"Windows native RegisterHotKey failed for Channel {ch}")

            if not registered:
                log("HotKeys", "Failed to register any Windows native hotkeys.")
                return

            log("HotKeys", f"Windows native hotkeys active: Ctrl+Alt+1/2/3")

            msg = wintypes.MSG()
            while self._win_running:
                # Peek and dispatch messages
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                if msg.message == WM_HOTKEY:
                    channel = msg.wParam
                    self._on_hotkey_triggered(channel)
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            for ch in [1, 2, 3]:
                user32.UnregisterHotKey(None, ch)

        self._win_thread = threading.Thread(target=win_msg_loop, name="WinHotkeys", daemon=True)
        self._win_thread.start()
        return True

    def stop(self) -> None:
        """Stops and unregisters all hotkeys."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

        if self._win_running:
            self._win_running = False
            # Post quit message to unblock GetMessageW on Windows
            if sys.platform == "win32":
                try:
                    import ctypes
                    # Post WM_QUIT (0x0012) to thread if needed
                    ctypes.windll.user32.PostQuitMessage(0)
                except Exception:
                    pass
            self._win_thread = None

        log("HotKeys", "Global hotkeys stopped.")
