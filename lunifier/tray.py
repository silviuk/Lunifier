"""
System Tray and Quick-Switch Mini Window for Lunifier.
Provides continuous system tray presence with 1-click simultaneous and individual
device channel switching, configurable tray double-click action, plus a sleek quick-control mini window.
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

IS_LINUX = sys.platform.startswith("linux")
BTN_RADIUS = 0 if IS_LINUX else 6
CARD_RADIUS = 0 if IS_LINUX else 8


class QuickSwitchWindow(ctk.CTkToplevel):
    """
    Compact modern popup window allowing instant switching of Logitech devices
    to Channel 1, 2, or 3 (both devices simultaneously or individually).
    Automatically closes when clicking outside, clicking Escape, or triggering a switch.
    """
    def __init__(self, parent: ctk.CTk, on_switch_callback: Callable[[int, str], None], on_open_main: Optional[Callable] = None):
        super().__init__(parent)
        self.parent = parent
        self.on_switch_callback = on_switch_callback
        self.on_open_main = on_open_main

        self.title("Lunifier - Quick Switch")
        self.geometry("380x330")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        # Position near bottom right (above taskbar) if possible, otherwise centered
        self._position_window()

        self._build_ui()

        # Keyboard shortcuts and dismiss handlers
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<FocusOut>", self._on_focus_out)
        self.focus_force()

    def _position_window(self) -> None:
        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = 380, 330
            # Place near bottom right margin (x: sw - w - 30, y: sh - h - 80)
            x = max(10, sw - w - 30)
            y = max(10, sh - h - 80)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _on_focus_out(self, event=None) -> None:
        """Closes window when focus is lost (clicking outside)."""
        self.after(150, self._check_focus_and_close)

    def _check_focus_and_close(self) -> None:
        try:
            focused = self.focus_get()
            if focused is None or not str(focused).startswith(str(self)):
                self.destroy()
        except Exception:
            pass

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self, corner_radius=CARD_RADIUS)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # Header
        hdr = ctk.CTkFrame(container, fg_color="transparent")
        hdr.pack(fill="x", padx=10, pady=(6, 4))
        ctk.CTkLabel(
            hdr,
            text="⚡ Quick Switch Channel",
            font=ctk.CTkFont(family="Segoe UI" if sys.platform == "win32" else None, size=15, weight="bold")
        ).pack(side="left")

        # Section 1: Switch Both Devices
        both_frame = ctk.CTkFrame(container, corner_radius=CARD_RADIUS, fg_color=("#e1f5fe", "#263238"))
        both_frame.pack(fill="x", padx=8, pady=5, ipady=3)

        ctk.CTkLabel(
            both_frame,
            text="Switch BOTH Devices Together:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#01579b", "#80d8ff")
        ).pack(anchor="w", padx=10, pady=(4, 4))

        both_btns = ctk.CTkFrame(both_frame, fg_color="transparent")
        both_btns.pack(fill="x", padx=10, pady=(0, 6))

        for ch in [1, 2, 3]:
            btn = ctk.CTkButton(
                both_btns,
                text=f"Channel {ch}",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#0277bd" if ch == 1 else ("#2e7d32" if ch == 2 else "#ef6c00"),
                hover_color="#01579b" if ch == 1 else ("#1b5e20" if ch == 2 else "#e65100"),
                width=96,
                height=32,
                corner_radius=BTN_RADIUS,
                command=lambda c=ch: self._trigger_switch(c, "both")
            )
            btn.pack(side="left", expand=True, padx=2)

        # Section 2: Individual Devices
        indiv_frame = ctk.CTkFrame(container, corner_radius=CARD_RADIUS, fg_color=("#f5f5f5", "#1e1e1e"))
        indiv_frame.pack(fill="x", padx=8, pady=5, ipady=3)

        ctk.CTkLabel(
            indiv_frame,
            text="Individual Device Switching:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray30", "#b0bec5")
        ).pack(anchor="w", padx=10, pady=(4, 4))

        # Keyboard row
        kb_row = ctk.CTkFrame(indiv_frame, fg_color="transparent")
        kb_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(kb_row, text="Keyboard:", font=ctk.CTkFont(size=11), width=70, anchor="w").pack(side="left")
        for ch in [1, 2, 3]:
            ctk.CTkButton(
                kb_row,
                text=f"Ch {ch}",
                font=ctk.CTkFont(size=11),
                width=72,
                height=25,
                fg_color=("#cfd8dc", "#37474f"),
                hover_color=("#b0bec5", "#455a64"),
                text_color=("#263238", "#eceff1"),
                corner_radius=BTN_RADIUS,
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
                width=72,
                height=25,
                fg_color=("#cfd8dc", "#37474f"),
                hover_color=("#b0bec5", "#455a64"),
                text_color=("#263238", "#eceff1"),
                corner_radius=BTN_RADIUS,
                command=lambda c=ch: self._trigger_switch(c, "mouse")
            ).pack(side="left", expand=True, padx=2)

        # Feedback label
        self.status_lbl = ctk.CTkLabel(container, text="Ready", font=ctk.CTkFont(size=11), text_color=("gray40", "#90a4ae"))
        self.status_lbl.pack(pady=3)

        # Bottom row
        bot_row = ctk.CTkFrame(container, fg_color="transparent")
        bot_row.pack(fill="x", padx=8, pady=(2, 4))

        if self.on_open_main:
            ctk.CTkButton(
                bot_row,
                text="Open Lunifier",
                font=ctk.CTkFont(size=11),
                width=110,
                height=28,
                fg_color=("#bdbdbd", "#424242"),
                hover_color=("#9e9e9e", "#616161"),
                text_color=("#212121", "#ffffff"),
                corner_radius=BTN_RADIUS,
                command=self._open_main_window
            ).pack(side="left")

        ctk.CTkButton(
            bot_row,
            text="Close (Esc)",
            font=ctk.CTkFont(size=11),
            width=90,
            height=28,
            fg_color=("#cfd8dc", "#37474f"),
            hover_color=("#b0bec5", "#455a64"),
            text_color=("#263238", "#ffffff"),
            corner_radius=BTN_RADIUS,
            command=self.destroy
        ).pack(side="right")

    def _open_main_window(self) -> None:
        self.destroy()
        if self.on_open_main:
            self.on_open_main()

    def _trigger_switch(self, channel: int, target_type: str) -> None:
        target_name = "Both Devices" if target_type == "both" else target_type.capitalize()
        self.status_lbl.configure(text=f"Switching {target_name} to Channel {channel}...", text_color=("#0277bd", "#80d8ff"))
        self.update_idletasks()

        def worker():
            try:
                self.on_switch_callback(channel, target_type)
            except Exception as e:
                log("Tray", f"Error during quick-switch: {e}")

        threading.Thread(target=worker, daemon=True).start()
        # Automatically close popup after initiating switch to avoid screen clutter
        self.after(250, self.destroy)


class LunifierTray:
    """
    Manages the system tray icon, context menu, double-click behavior, and quick-switch mini window.
    """
    def __init__(self,
                 root: ctk.CTk,
                 on_switch_channel: Callable[[int, str], None],
                 on_show_main: Callable[[], None],
                 on_toggle_daemon: Optional[Callable[[], None]] = None,
                 on_exit: Optional[Callable[[], None]] = None,
                 double_click_action: str = "open_gui"):
        self.root = root
        self.on_switch_channel = on_switch_channel
        self.on_show_main = on_show_main
        self.on_toggle_daemon = on_toggle_daemon
        self.on_exit = on_exit
        self.double_click_action = double_click_action

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

    def set_double_click_action(self, action: str) -> None:
        """Updates double-click action and reconfigures menu."""
        self.double_click_action = action
        if self._icon:
            try:
                self._icon.menu = self._build_menu()
            except Exception as e:
                log("Tray", f"Failed to update tray menu: {e}")

    def _build_menu(self) -> menu:
        act = self.double_click_action
        return menu(
            item("⚡ Quick Switch: Both -> Channel 1", lambda: self._on_quick_switch_both(1), default=(act == "switch_1")),
            item("⚡ Quick Switch: Both -> Channel 2", lambda: self._on_quick_switch_both(2), default=(act == "switch_2")),
            item("⚡ Quick Switch: Both -> Channel 3", lambda: self._on_quick_switch_both(3), default=(act == "switch_3")),
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
            item("Quick Switch Window...", lambda: self.open_mini_window(), default=(act == "mini_window")),
            item("Open Lunifier", lambda: self._on_show_main_clicked(), default=(act == "open_gui")),
            item("---", None),
            item("Exit Lunifier", lambda: self._on_exit_clicked())
        )

    def start(self) -> None:
        if pystray is None:
            log("Tray", "pystray not installed, system tray disabled.")
            return

        def setup_and_run():
            try:
                image = self._create_icon_image()
                tray_menu = self._build_menu()
                self._icon = pystray.Icon("Lunifier", image, "Lunifier - Logitech Easy-Switch", tray_menu)
                log("Tray", "System tray icon running.")
                self._icon.run()
            except Exception as e:
                log("Tray", f"Could not run system tray icon: {e}")

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
