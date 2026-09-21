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
    native vector mathematics and 2x supersampled anti-aliasing.
    """
    size = max(16, min(2048, int(size)))

    # Check if CairoSVG is available to render SVG directly
    svg_path = get_resource_path("icon.svg")
    if os.path.exists(svg_path):
        try:
            import cairosvg
            import io
            png_bytes = cairosvg.svg2png(url=svg_path, output_width=size, output_height=size)
            if png_bytes:
                return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        except Exception:
            pass

    # High-precision mathematical vector rendering fallback
    scale = 2
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 56 * (canvas_size / 1024.0)
    rect_box = [margin, margin, canvas_size - margin, canvas_size - margin]
    radius = 190 * (canvas_size / 1024.0)

    # 1. Background Rounded Squircle with Drop Shadow
    shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_y_off = 18 * (canvas_size / 1024.0)
    shadow_box = [margin, margin + shadow_y_off, canvas_size - margin, canvas_size - margin + shadow_y_off]
    shadow_draw.rounded_rectangle(shadow_box, radius=radius, fill=(0, 0, 0, 140))
    blur_r = max(1.0, 24 * (canvas_size / 1024.0))
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur_r))
    img = Image.alpha_composite(shadow, img)
    draw = ImageDraw.Draw(img)

    # Base squircle container
    border_w = max(1, int(9 * (canvas_size / 1024.0)))
    draw.rounded_rectangle(rect_box, radius=radius, fill=(15, 23, 42, 255), outline=(71, 85, 105, 200), width=border_w)

    # 2. Dotted Wall (Separating diagonal)
    diag_off = 80 * (canvas_size / 1024.0)
    x1, y1 = margin + diag_off, canvas_size - margin - diag_off
    x2, y2 = canvas_size - margin - diag_off, margin + diag_off
    num_dots = 15
    for i in range(num_dots):
        t = i / (num_dots - 1)
        dx = x1 + t * (x2 - x1)
        dy = y1 + t * (y2 - y1)
        dist_from_center = abs(t - 0.5)
        dot_r = max(1.5, (14.0 - dist_from_center * 5.0) * (canvas_size / 1024.0))
        alpha = int(255 - dist_from_center * 70)
        draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r], fill=(226, 232, 240, alpha))

    # 3. Top-Left Star (System 1: Cyan / Azure)
    s1_off = 200 * (canvas_size / 1024.0)
    s1_cx = margin + s1_off
    s1_cy = margin + s1_off

    glow1 = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    glow1_draw = ImageDraw.Draw(glow1)
    g1_r = 180 * (canvas_size / 1024.0)
    glow1_draw.ellipse([s1_cx - g1_r, s1_cy - g1_r, s1_cx + g1_r, s1_cy + g1_r], fill=(0, 240, 255, 60))
    glow1 = glow1.filter(ImageFilter.GaussianBlur(max(1.0, 36 * (canvas_size / 1024.0))))
    img = Image.alpha_composite(img, glow1)
    draw = ImageDraw.Draw(img)

    _draw_star_vector(
        draw, s1_cx, s1_cy,
        outer_r=150 * (canvas_size / 1024.0),
        inner_r=30 * (canvas_size / 1024.0),
        fill_color=(56, 189, 248, 255),
        core_color=(255, 255, 255, 255)
    )
    m1_r = max(1.0, 6 * (canvas_size / 1024.0))
    draw.ellipse([s1_cx + 105 * (canvas_size / 1024.0) - m1_r, s1_cy - 85 * (canvas_size / 1024.0) - m1_r,
                  s1_cx + 105 * (canvas_size / 1024.0) + m1_r, s1_cy - 85 * (canvas_size / 1024.0) + m1_r],
                 fill=(125, 211, 252, 240))

    # 4. Bottom-Right Star (System 2: Orange / Amber)
    s2_cx = canvas_size - margin - s1_off
    s2_cy = canvas_size - margin - s1_off

    glow2 = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    glow2_draw = ImageDraw.Draw(glow2)
    g2_r = 180 * (canvas_size / 1024.0)
    glow2_draw.ellipse([s2_cx - g2_r, s2_cy - g2_r, s2_cx + g2_r, s2_cy + g2_r], fill=(255, 109, 0, 60))
    glow2 = glow2.filter(ImageFilter.GaussianBlur(max(1.0, 36 * (canvas_size / 1024.0))))
    img = Image.alpha_composite(img, glow2)
    draw = ImageDraw.Draw(img)

    _draw_star_vector(
        draw, s2_cx, s2_cy,
        outer_r=150 * (canvas_size / 1024.0),
        inner_r=30 * (canvas_size / 1024.0),
        fill_color=(251, 146, 60, 255),
        core_color=(255, 255, 255, 255)
    )
    m2_r = max(1.0, 6 * (canvas_size / 1024.0))
    draw.ellipse([s2_cx - 105 * (canvas_size / 1024.0) - m2_r, s2_cy + 85 * (canvas_size / 1024.0) - m2_r,
                  s2_cx - 105 * (canvas_size / 1024.0) + m2_r, s2_cy + 85 * (canvas_size / 1024.0) + m2_r],
                 fill=(253, 186, 116, 240))

    final_img = img.resize((size, size), Image.Resampling.LANCZOS)
    return final_img


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
