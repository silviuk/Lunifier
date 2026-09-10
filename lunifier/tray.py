"""
System Tray and Quick-Switch Mini Window for Lunifier.
Provides continuous system tray presence with 1-click simultaneous and individual
device channel switching, plus a sleek quick-control mini window.
"""

import os
import sys
import threading
from typing import Optional, Callable
from PIL import Image, ImageDraw

try:
    import pystray
    from pystray import MenuItem as item, Menu as menu
except ImportError:
    pystray = None

import customtkinter as ctk
from .logger import log


class QuickSwitchWindow(ctk.CTkToplevel):
    """
    Compact modern popup window allowing instant switching of Logitech devices
    to Channel 1, 2, or 3 (both devices simultaneously or individually).
    """
    def __init__(self, parent: ctk.CTk, on_switch_callback: Callable[[int, str], None], on_open_main: Optional[Callable] = None):
        super().__init__(parent)
        self.parent = parent
        self.on_switch_callback = on_switch_callback
        self.on_open_main = on_open_main

        self.title("Lunifier - Quick Switch")
        self.geometry("380x320")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        # Position near bottom right (above taskbar) if possible, otherwise centered
        self._position_window()

        self._build_ui()

        # Keyboard shortcuts
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_force()

    def _position_window(self) -> None:
        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 380, 320
            # Place near bottom right margin (x: sw - w - 30, y: sh - h - 80)
            x = max(10, sw - w - 30)
            y = max(10, sh - h - 80)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self, corner_radius=8)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        # Header
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(hdr, text="⚡ Quick Switch Channel", font=ctk.CTkFont(family="Segoe UI" if sys.platform == "win32" else None, size=15, weight="bold")).pack(side="left")

        # Section 1: Switch Both Devices
        both_frame = ctk.CTkFrame(container, corner_radius=6, fg_color="#263238")
        both_frame.pack(fill="x", padx=10, pady=6, ipady=4)

        ctk.CTkLabel(both_frame, text="Switch BOTH Devices Together:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#80d8ff").pack(anchor="w", padx=10, pady=(6, 4))

        both_btns = ctk.CTkFrame(both_frame, fg_color="transparent")
        both_btns.pack(fill="x", padx=10, pady=(0, 6))

        for ch in [1, 2, 3]:
            btn = ctk.CTkButton(
                both_btns,
                text=f"Channel {ch}",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#0277bd" if ch == 1 else ("#2e7d32" if ch == 2 else "#ef6c00"),
                hover_color="#01579b" if ch == 1 else ("#1b5e20" if ch == 2 else "#e65100"),
                width=100,
                height=34,
                command=lambda c=ch: self._trigger_switch(c, "both")
            )
            btn.pack(side="left", expand=True, padx=3)

        # Section 2: Individual Devices
        indiv_frame = ctk.CTkFrame(container, corner_radius=6, fg_color="#1e1e1e")
        indiv_frame.pack(fill="x", padx=10, pady=6, ipady=4)

        ctk.CTkLabel(indiv_frame, text="Individual Device Switching:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#b0bec5").pack(anchor="w", padx=10, pady=(6, 4))

        # Keyboard row
        kb_row = ctk.CTkFrame(indiv_frame, fg_color="transparent")
        kb_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(kb_row, text="Keyboard:", font=ctk.CTkFont(size=11), width=70, anchor="w").pack(side="left")
        for ch in [1, 2, 3]:
            ctk.CTkButton(
                kb_row,
                text=f"Ch {ch}",
                font=ctk.CTkFont(size=11),
                width=75,
                height=26,
                fg_color="#37474f",
                hover_color="#455a64",
                command=lambda c=ch: self._trigger_switch(c, "keyboard")
            ).pack(side="left", expand=True, padx=2)

        # Mouse row
        mouse_row = ctk.CTkFrame(indiv_frame, fg_color="transparent")
        mouse_row.pack(fill="x", padx=10, pady=(2, 6))
        ctk.CTkLabel(mouse_row, text="Mouse:", font=ctk.CTkFont(size=11), width=70, anchor="w").pack(side="left")
        for ch in [1, 2, 3]:
            ctk.CTkButton(
                mouse_row,
                text=f"Ch {ch}",
                font=ctk.CTkFont(size=11),
                width=75,
                height=26,
                fg_color="#37474f",
                hover_color="#455a64",
                command=lambda c=ch: self._trigger_switch(c, "mouse")
            ).pack(side="left", expand=True, padx=2)

        # Feedback label
        self.status_lbl = ctk.CTkLabel(container, text="Ready", font=ctk.CTkFont(size=11), text_color="#90a4ae")
        self.status_lbl.pack(pady=4)

        # Bottom row
        bot_row = ctk.CTkFrame(container, fg_color="transparent")
        bot_row.pack(fill="x", padx=10, pady=(2, 4))

        if self.on_open_main:
            ctk.CTkButton(bot_row, text="Open Lunifier", font=ctk.CTkFont(size=11), width=110, height=28, fg_color="#424242", hover_color="#616161", command=self._open_main_window).pack(side="left")

        ctk.CTkButton(bot_row, text="Close (Esc)", font=ctk.CTkFont(size=11), width=90, height=28, fg_color="#37474f", hover_color="#455a64", command=self.destroy).pack(side="right")

    def _open_main_window(self) -> None:
        self.destroy()
        if self.on_open_main:
            self.on_open_main()

    def _trigger_switch(self, channel: int, target_type: str) -> None:
        target_name = "Both Devices" if target_type == "both" else target_type.capitalize()
        self.status_lbl.configure(text=f"Switching {target_name} to Channel {channel}...", text_color="#80d8ff")
        self.update_idletasks()

        def worker():
            try:
                self.on_switch_callback(channel, target_type)
                self.parent.after(0, lambda: self.status_lbl.configure(text=f"✓ Switched {target_name} to Channel {channel}", text_color="#81c784"))
            except Exception as e:
                self.parent.after(0, lambda: self.status_lbl.configure(text=f"Error: {e}", text_color="#ef5350"))

        threading.Thread(target=worker, daemon=True).start()


class LunifierTray:
    """
    Manages the system tray icon, context menu, and quick-switch mini window.
    """
    def __init__(self,
                 root: ctk.CTk,
                 on_switch_channel: Callable[[int, str], None],
                 on_show_main: Callable[[], None],
                 on_toggle_daemon: Optional[Callable[[], None]] = None,
                 on_exit: Optional[Callable[[], None]] = None):
        self.root = root
        self.on_switch_channel = on_switch_channel
        self.on_show_main = on_show_main
        self.on_toggle_daemon = on_toggle_daemon
        self.on_exit = on_exit

        self._icon: Optional[pystray.Icon] = None
        self._mini_window: Optional[QuickSwitchWindow] = None
        self._thread: Optional[threading.Thread] = None

    def _create_icon_image(self) -> Image.Image:
        base_dir = os.path.dirname(__file__)
        png_path = os.path.join(base_dir, "resources", "icon.png")
        if os.path.exists(png_path):
            try:
                return Image.open(png_path)
            except Exception:
                pass

        # Fallback generated icon: orange circle with white "L"
        img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((4, 4, 60, 60), fill="#FF5722")
        draw.rectangle((22, 16, 28, 48), fill="white")
        draw.rectangle((22, 42, 44, 48), fill="white")
        return img

    def open_mini_window(self) -> None:
        """Opens or raises the Quick Switch mini window on the main GUI thread."""
        def _show():
            if self._mini_window and self._mini_window.winfo_exists():
                self._mini_window.deiconify()
                self._mini_window.lift()
                self._mini_window.focus_force()
            else:
                self._mini_window = QuickSwitchWindow(
                    self.root,
                    on_switch_callback=self.on_switch_channel,
                    on_open_main=self.on_show_main
                )

        self.root.after(0, _show)

    def _on_quick_switch_both(self, channel: int) -> None:
        threading.Thread(target=self.on_switch_channel, args=(channel, "both"), daemon=True).start()

    def _on_quick_switch_device(self, channel: int, target_type: str) -> None:
        threading.Thread(target=self.on_switch_channel, args=(channel, target_type), daemon=True).start()

    def _on_show_main_clicked(self) -> None:
        self.root.after(0, self.on_show_main)

    def _on_exit_clicked(self) -> None:
        self.stop()
        if self.on_exit:
            self.root.after(0, self.on_exit)
        else:
            self.root.after(0, self.root.destroy)

    def start(self) -> None:
        if pystray is None:
            log("Tray", "pystray not installed, system tray disabled.")
            return

        def setup_and_run():
            image = self._create_icon_image()

            tray_menu = menu(
                item("⚡ Quick Switch: Both -> Channel 1", lambda: self._on_quick_switch_both(1)),
                item("⚡ Quick Switch: Both -> Channel 2", lambda: self._on_quick_switch_both(2)),
                item("⚡ Quick Switch: Both -> Channel 3", lambda: self._on_quick_switch_both(3)),
                item("---", None),
                item("⌨ Keyboard Only", menu(
                    item("Channel 1", lambda: self._on_quick_switch_device(1, "keyboard")),
                    item("Channel 2", lambda: self._on_quick_switch_device(2, "keyboard")),
                    item("Channel 3", lambda: self._on_quick_switch_device(3, "keyboard")),
                )),
                item("🖱 Mouse Only", menu(
                    item("Channel 1", lambda: self._on_quick_switch_device(1, "mouse")),
                    item("Channel 2", lambda: self._on_quick_switch_device(2, "mouse")),
                    item("Channel 3", lambda: self._on_quick_switch_device(3, "mouse")),
                )),
                item("---", None),
                item("Quick Switch Window...", lambda: self.open_mini_window(), default=True),
                item("Open Lunifier", lambda: self._on_show_main_clicked()),
                item("---", None),
                item("Exit", lambda: self._on_exit_clicked())
            )

            self._icon = pystray.Icon("Lunifier", image, "Lunifier - Logitech Easy-Switch", tray_menu)
            log("Tray", "System tray icon running.")
            self._icon.run()

        self._thread = threading.Thread(target=setup_and_run, name="TrayThread", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
        log("Tray", "System tray icon stopped.")
