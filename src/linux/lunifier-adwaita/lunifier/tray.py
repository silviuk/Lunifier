"""
System tray integration for Lunifier on Linux.
Supports:
1. Native D-Bus StatusNotifierItem (SNI) + DBusMenu (standard on GNOME Shell AppIndicator, KDE Plasma, XFCE, Waybar)
2. Direct IconPixmap export (ARGB32 network byte order) for pixel-perfect fallback on any desktop
3. Dynamic icon theme resolution and panel-compatible status icon names
"""

import os
import sys
import threading
from typing import Callable, Optional, List, Tuple

import gi
from gi.repository import Gio, GLib

try:
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
except Exception:
    GdkPixbuf = None

from .logger import log

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="u" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <method name="ContextMenu">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="Activate">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg type="i" name="x" direction="in"/>
      <arg type="i" name="y" direction="in"/>
    </method>
    <method name="Scroll">
      <arg type="i" name="delta" direction="in"/>
      <arg type="s" name="orientation" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewIconThemePath"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus">
      <arg type="s" name="status"/>
    </signal>
  </interface>
</node>
"""

DBUSMENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="Status" type="s" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
  </interface>
</node>
"""


def _find_best_icon_file() -> Optional[str]:
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        # System installed icons
        "/usr/share/icons/hicolor/32x32/apps/lunifier.png",
        "/usr/share/icons/hicolor/24x24/apps/lunifier.png",
        "/usr/share/icons/hicolor/48x48/apps/lunifier.png",
        "/usr/share/icons/hicolor/32x32/status/lunifier.png",
        "/usr/share/icons/hicolor/24x24/status/lunifier.png",
        "/usr/share/pixmaps/lunifier.png",
        # Local resources (bundled in package or source tree)
        os.path.join(pkg_dir, "resources", "icons", "32x32.png"),
        os.path.join(pkg_dir, "..", "resources", "icons", "32x32.png"),
        os.path.join(pkg_dir, "resources", "icons", "24x24.png"),
        os.path.join(pkg_dir, "..", "resources", "icons", "24x24.png"),
        os.path.join(pkg_dir, "resources", "icons", "48x48.png"),
        os.path.join(pkg_dir, "..", "resources", "icons", "48x48.png"),
        os.path.join(pkg_dir, "resources", "icon.png"),
        os.path.join(pkg_dir, "..", "resources", "icon.png"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return os.path.normpath(os.path.abspath(c))
    return None


def _pixbuf_to_argb(pb) -> Tuple[int, int, bytes]:
    w = pb.get_width()
    h = pb.get_height()
    n_ch = pb.get_n_channels()
    stride = pb.get_rowstride()
    pixels = pb.get_pixels()

    # Convert to ARGB network byte order: byte 0=A, 1=R, 2=G, 3=B
    argb = bytearray(w * h * 4)
    for y in range(h):
        row_in = y * stride
        row_out = y * w * 4
        for x in range(w):
            pin = row_in + x * n_ch
            pout = row_out + x * 4
            r = pixels[pin]
            g = pixels[pin + 1]
            b = pixels[pin + 2]
            a = pixels[pin + 3] if n_ch == 4 else 255
            argb[pout] = a
            argb[pout + 1] = r
            argb[pout + 2] = g
            argb[pout + 3] = b
    return (w, h, bytes(argb))


def _generate_icon_pixmaps() -> GLib.Variant:
    if GdkPixbuf is None:
        return GLib.Variant("a(iiay)", [])

    icon_path = _find_best_icon_file()
    if not icon_path:
        return GLib.Variant("a(iiay)", [])

    pixmaps = []
    try:
        base_pb = GdkPixbuf.Pixbuf.new_from_file(icon_path)
        for sz in (16, 22, 24, 32, 48):
            scaled = base_pb.scale_simple(sz, sz, GdkPixbuf.InterpType.BILINEAR)
            if scaled:
                pixmaps.append(_pixbuf_to_argb(scaled))
    except Exception as ex:
        log("Tray", f"Error generating icon pixmaps from '{icon_path}': {ex}")

    return GLib.Variant("a(iiay)", pixmaps)


def _determine_icon_name() -> str:
    # 1. Check if 'lunifier' is found in GTK icon theme
    try:
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk, Gdk
        display = Gdk.Display.get_default()
        if display:
            theme = Gtk.IconTheme.get_for_display(display)
            if theme and theme.has_icon("lunifier"):
                return "lunifier"
    except Exception:
        pass

    # 2. Check if installed in standard system icon directories
    if os.path.isfile("/usr/share/icons/hicolor/32x32/apps/lunifier.png") or \
       os.path.isfile("/usr/share/icons/hicolor/scalable/apps/lunifier.svg") or \
       os.path.isfile("/usr/share/pixmaps/lunifier.png"):
        return "lunifier"

    # 3. If running standalone/uninstalled, GNOME AppIndicator supports absolute file paths directly
    local_file = _find_best_icon_file()
    if local_file:
        return local_file

    return "lunifier"


class LunifierTray:
    def __init__(self, on_show: Callable[[], None], on_quit: Callable[[], None]):
        self.on_show = on_show
        self.on_quit = on_quit
        self.connection: Optional[Gio.DBusConnection] = None
        self.sni_reg_id = 0
        self.menu_reg_id = 0
        self.service_status = "Active"

        self.icon_name = _determine_icon_name()
        self.pixmaps_variant = _generate_icon_pixmaps()
        log("Tray", f"Initialized tray icon: name='{self.icon_name}', pixmaps={self.pixmaps_variant.n_children()}")

        self._init_sni()

    def _init_sni(self):
        try:
            self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            if not self.connection:
                log("Tray", "Unable to connect to D-Bus Session bus.")
                return

            sni_node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
            sni_iface = sni_node.lookup_interface("org.kde.StatusNotifierItem")

            self.sni_reg_id = self.connection.register_object(
                "/StatusNotifierItem",
                sni_iface,
                self._handle_sni_method_call,
                self._handle_sni_get_property,
                None
            )

            menu_node = Gio.DBusNodeInfo.new_for_xml(DBUSMENU_XML)
            menu_iface = menu_node.lookup_interface("com.canonical.dbusmenu")

            self.menu_reg_id = self.connection.register_object(
                "/MenuBar",
                menu_iface,
                self._handle_menu_method_call,
                self._handle_menu_get_property,
                None
            )

            # Register with StatusNotifierWatcher
            self._register_with_watcher()
            log("Tray", "StatusNotifierItem registered on D-Bus (/StatusNotifierItem).")
        except Exception as ex:
            log("Tray", f"Error setting up StatusNotifierItem: {ex}")

    def _register_with_watcher(self):
        try:
            self.connection.call(
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", ("/StatusNotifierItem",)),
                None,
                Gio.DBusCallFlags.NONE,
                1000,
                None,
                self._on_register_finished
            )
        except Exception as ex:
            log("Tray", f"Watcher registration invocation error: {ex}")

    def _on_register_finished(self, conn, res):
        try:
            conn.call_finish(res)
            log("Tray", "Successfully registered with StatusNotifierWatcher.")
        except Exception as ex:
            log("Tray", f"StatusNotifierWatcher registration finished with note: {ex}")

    def _handle_sni_method_call(self, conn, sender, path, iface, method, params, invocation):
        if method in ("Activate", "SecondaryActivate"):
            GLib.idle_add(self.on_show)
            invocation.return_value(None)
        elif method == "ContextMenu":
            GLib.idle_add(self.on_show)
            invocation.return_value(None)
        elif method == "Scroll":
            invocation.return_value(None)
        else:
            invocation.return_value(None)

    def _handle_sni_get_property(self, conn, sender, path, iface, prop_name):
        if prop_name == "Category":
            return GLib.Variant("s", "ApplicationStatus")
        elif prop_name == "Id":
            return GLib.Variant("s", "lunifier")
        elif prop_name == "Title":
            return GLib.Variant("s", "Lunifier")
        elif prop_name == "Status":
            return GLib.Variant("s", self.service_status)
        elif prop_name == "WindowId":
            return GLib.Variant("u", 0)
        elif prop_name == "IconName":
            return GLib.Variant("s", self.icon_name)
        elif prop_name == "IconPixmap":
            return self.pixmaps_variant
        elif prop_name == "OverlayIconName":
            return GLib.Variant("s", "")
        elif prop_name == "OverlayIconPixmap":
            return GLib.Variant("a(iiay)", [])
        elif prop_name == "AttentionIconName":
            return GLib.Variant("s", "")
        elif prop_name == "AttentionIconPixmap":
            return GLib.Variant("a(iiay)", [])
        elif prop_name == "AttentionMovieName":
            return GLib.Variant("s", "")
        elif prop_name == "IconThemePath":
            return GLib.Variant("s", "")
        elif prop_name == "ToolTip":
            return GLib.Variant("(sa(iiay)ss)", ("lunifier", [], "Lunifier", "Seamless Logitech Easy-Switch Flow"))
        elif prop_name == "Menu":
            return GLib.Variant("o", "/MenuBar")
        elif prop_name == "ItemIsMenu":
            return GLib.Variant("b", False)
        return None

    def _handle_menu_method_call(self, conn, sender, path, iface, method, params, invocation):
        if method == "GetLayout":
            # Return root menu with items: 1: Show Lunifier, 2: Quit
            parent_id, depth, prop_names = params.unpack()

            # Children of root (id 0)
            item1 = (
                1,
                {"label": GLib.Variant("s", "Show Lunifier"), "type": GLib.Variant("s", "standard")},
                []
            )
            item2 = (
                2,
                {"label": GLib.Variant("s", "Quit Lunifier"), "type": GLib.Variant("s", "standard")},
                []
            )
            root = (
                0,
                {"children-display": GLib.Variant("s", "submenu")},
                [GLib.Variant("(ia{sv}av)", item1), GLib.Variant("(ia{sv}av)", item2)]
            )
            invocation.return_value(GLib.Variant("(u(ia{sv}av))", (1, root)))

        elif method == "GetGroupProperties":
            ids, props = params.unpack()
            result = []
            for i in ids:
                if i == 1:
                    result.append((1, {"label": GLib.Variant("s", "Show Lunifier")}))
                elif i == 2:
                    result.append((2, {"label": GLib.Variant("s", "Quit Lunifier")}))
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (result,)))

        elif method == "GetProperty":
            item_id, prop_name = params.unpack()
            if prop_name == "label":
                lbl = "Show Lunifier" if item_id == 1 else "Quit Lunifier"
                invocation.return_value(GLib.Variant("(v)", (GLib.Variant("s", lbl),)))
            else:
                invocation.return_value(None)

        elif method == "Event":
            item_id, event_id, data, ts = params.unpack()
            if event_id == "clicked":
                if item_id == 1:
                    GLib.idle_add(self.on_show)
                elif item_id == 2:
                    GLib.idle_add(self.on_quit)
            invocation.return_value(None)
        else:
            invocation.return_value(None)

    def _handle_menu_get_property(self, conn, sender, path, iface, prop_name):
        if prop_name == "Version":
            return GLib.Variant("u", 3)
        elif prop_name == "Status":
            return GLib.Variant("s", "notice")
        return None
