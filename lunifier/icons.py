"""
Centralized resource and scalable application icon management for Lunifier.
Provides high-DPI multi-resolution vector rendering and caching across
development mode, installed packages, and PyInstaller / frozen binaries on Windows and Linux.
"""

import os
import sys
import math
from typing import Optional, Tuple, Union, List, Dict
from PIL import Image, ImageDraw, ImageFilter

try:
    from PIL import ImageTk
except ImportError:
    ImageTk = None

try:
    import tkinter as tk
except ImportError:
    tk = None

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

_cached_pil_images: Dict[int, Image.Image] = {}
_cached_photo_images: List = []
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


def _draw_star_vector(draw: ImageDraw.ImageDraw, cx: float, cy: float, outer_r: float, inner_r: float, fill_color, core_color) -> None:
    """Draws a mathematical 4-pointed radiant star with flare curves."""
    points = []
    steps = 120
    for i in range(steps):
        theta = 2 * math.pi * i / steps
        factor = (math.cos(4 * theta) + 1.0) / 2.0
        r = inner_r + (outer_r - inner_r) * (factor ** 2.2)
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        points.append((x, y))

    draw.polygon(points, fill=fill_color)
    cr = inner_r * 0.9
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=core_color)


def render_scalable_icon(size: int = 512) -> Image.Image:
    """
    Renders the official Lunifier icon at any arbitrary resolution using
    Scalable Vector Graphics (SVG) or high-precision vector mathematics.
    """
    size = max(16, min(2048, int(size)))

    # 1. Render from icon.svg via resvg_py or cairosvg
    svg_path = get_resource_path("icon.svg")
    if os.path.exists(svg_path):
        # Try resvg_py
        try:
            import resvg_py
            import io
            with open(svg_path, "r", encoding="utf-8") as f:
                svg_data = f.read()
            png_bytes = resvg_py.svg_to_bytes(svg_data, width=size, height=size)
            if png_bytes:
                return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        except Exception:
            pass

        # Try cairosvg
        try:
            import cairosvg
            import io
            png_bytes = cairosvg.svg2png(url=svg_path, output_width=size, output_height=size)
            if png_bytes:
                return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        except Exception:
            pass

    # 2. If master icon.png is available on disk, scale with high-fidelity Lanczos
    png_path = get_resource_path("icon.png")
    if os.path.exists(png_path):
        try:
            master = Image.open(png_path).convert("RGBA")
            if master.size == (size, size):
                return master
            return master.resize((size, size), Image.Resampling.LANCZOS)
        except Exception:
            pass

    # 3. High-precision mathematical vector rendering fallback
    scale = 2
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = canvas_size / 2.0, canvas_size / 2.0
    r_disc = 198.0 * (canvas_size / 512.0)

    # Outer drop shadow
    shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    dy = 20.0 * (canvas_size / 512.0)
    s_draw.ellipse([cx - r_disc, cy - r_disc + dy, cx + r_disc, cy + r_disc + dy], fill=(0, 0, 0, 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(1.0, 22.0 * (canvas_size / 512.0))))
    img = Image.alpha_composite(shadow, img)
    draw = ImageDraw.Draw(img)

    # Outer disc with border
    border_w = max(1, int(5.0 * (canvas_size / 512.0)))
    draw.ellipse([cx - r_disc, cy - r_disc, cx + r_disc, cy + r_disc], fill=(20, 28, 38, 255), outline=(74, 90, 106, 255), width=border_w)

    # Diagonal bead chain
    u = 1.0 / math.sqrt(2.0)
    bead_r = 11.5 * (canvas_size / 512.0)
    for s_val in range(-176, 177, 16):
        bx = cx + s_val * u * (canvas_size / 512.0)
        by = cy - s_val * u * (canvas_size / 512.0)
        draw.ellipse([bx - bead_r, by - bead_r, bx + bead_r, by + bead_r], fill=(202, 214, 207, 240))

    # 4 Orange lobes
    lobe_len = 149.0 * (canvas_size / 512.0)
    lobe_hw = 24.0 * (canvas_size / 512.0)
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        # Draw curved lobe
        points = []
        for step in range(30):
            t = step / 29.0
            dist = 25.0 * (canvas_size / 512.0) + t * (lobe_len - 25.0 * (canvas_size / 512.0))
            w_factor = math.sin(math.pi * (t ** 0.7)) * lobe_hw
            px = cx + dist * sin_a + w_factor * cos_a
            py = cy - dist * cos_a + w_factor * sin_a
            points.append((px, py))
        for step in range(29, -1, -1):
            t = step / 29.0
            dist = 25.0 * (canvas_size / 512.0) + t * (lobe_len - 25.0 * (canvas_size / 512.0))
            w_factor = -math.sin(math.pi * (t ** 0.7)) * lobe_hw
            px = cx + dist * sin_a + w_factor * cos_a
            py = cy - dist * cos_a + w_factor * sin_a
            points.append((px, py))
        draw.polygon(points, fill=(251, 146, 60, 255))

    # Center white core
    r_core = 27.0 * (canvas_size / 512.0)
    draw.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core], fill=(255, 255, 255, 255))

    return img.resize((size, size), Image.Resampling.LANCZOS)


def get_icon_pil(size: Optional[Union[int, Tuple[int, int]]] = None) -> Optional[Image.Image]:
    """
    Loads or dynamically generates the Lunifier PIL Image at the requested resolution.
    Caches rasterized sizes for instant recall without redrawing overhead.
    """
    global _cached_pil_images
    target_dim = 512
    if size is not None:
        target_dim = size if isinstance(size, int) else max(size)

    if target_dim in _cached_pil_images:
        return _cached_pil_images[target_dim].copy()

    # If asking for 512 and icon.png exists on disk, we can use it or render
    if target_dim == 512:
        png_path = get_resource_path("icon.png")
        if os.path.exists(png_path):
            try:
                img = Image.open(png_path).convert("RGBA")
                _cached_pil_images[512] = img
                return img.copy()
            except Exception:
                pass

    # Dynamically render scalable vector icon
    try:
        rendered = render_scalable_icon(target_dim)
        _cached_pil_images[target_dim] = rendered
        return rendered.copy()
    except Exception:
        # Fallback to master if available
        if 512 in _cached_pil_images:
            return _cached_pil_images[512].resize((target_dim, target_dim), Image.Resampling.LANCZOS)
    return None


def get_icon_ctk(size=(32, 32)) -> Optional["ctk.CTkImage"]:
    """
    Creates a high-DPI CTkImage of the Lunifier logo suitable for CustomTkinter widgets
    and window headers, rendered sharply for high-resolution displays.
    """
    if ctk is None:
        return None
    # Render at 2x resolution for high-DPI / retina displays
    render_dim = max(size[0], size[1]) * 2
    pil_img = get_icon_pil(size=render_dim)
    if pil_img:
        try:
            return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
        except Exception:
            pass
    return None


def set_window_icon(window) -> None:
    """
    Sets the unified scalable Lunifier window icon across Windows and Linux.
    Passes a full suite of multi-resolution mipmaps (16px to 256px) to Tk iconphoto
    and sets the Windows taskbar iconbitmap for crisp display at all DPI scales.
    """
    global _cached_photo_images
    init_windows_app_id()

    ico_path = get_resource_path("icon.ico")
    if sys.platform == "win32" and os.path.exists(ico_path):
        try:
            window.iconbitmap(ico_path)
        except Exception:
            pass

    # Set multi-resolution iconphoto on Tk
    if tk is not None and ImageTk is not None:
        try:
            if not _cached_photo_images:
                resolutions = [16, 24, 32, 48, 64, 128, 256]
                for res in resolutions:
                    pil_res = get_icon_pil(size=res)
                    if pil_res:
                        _cached_photo_images.append(ImageTk.PhotoImage(pil_res))

            if _cached_photo_images:
                window.iconphoto(True, *_cached_photo_images)
                return
        except Exception:
            pass

    # Fallback to single PNG photo
    png_path = get_resource_path("icon.png")
    if tk is not None and os.path.exists(png_path):
        try:
            photo = tk.PhotoImage(file=png_path)
            window.iconphoto(True, photo)
        except Exception:
            pass
