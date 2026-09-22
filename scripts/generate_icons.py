"""
Generates high-resolution, multi-layer scalable vector and raster application icons for Lunifier.
The official Lunifier icon represents cross-device Easy-Switch flow:
A dark metallic circular badge with a diagonal inter-host communication link (beads with status indicators),
a vibrant 4-petal orange propeller/star, and a pure white core.

Outputs:
- lunifier/resources/icon.svg (Scalable Vector Graphics master)
- lunifier/resources/icon.png (512x512 high-DPI master raster)
- lunifier/resources/icon.ico (Windows multi-resolution embedded mipmaps: 256, 128, 64, 48, 32, 24, 16)
"""

import math
import os
import io
from PIL import Image, ImageDraw, ImageFilter

try:
    import resvg_py
except ImportError:
    resvg_py = None

try:
    import cairosvg
except ImportError:
    cairosvg = None

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "lunifier", "resources"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_svg_content() -> str:
    """Returns the master Scalable Vector Graphics (SVG) definition of the official Lunifier icon."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <!-- Dark slate radial background with subtle greenish/sage core tint -->
    <radialGradient id="discBg" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#44554b" />
      <stop offset="35%" stop-color="#384740" />
      <stop offset="70%" stop-color="#232c37" />
      <stop offset="100%" stop-color="#141c26" />
    </radialGradient>

    <!-- Metallic border ring gradient -->
    <linearGradient id="borderGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#556677" />
      <stop offset="50%" stop-color="#414f5e" />
      <stop offset="100%" stop-color="#303b47" />
    </linearGradient>

    <!-- Bead gradient -->
    <radialGradient id="beadGrad" cx="35%" cy="30%" r="65%">
      <stop offset="0%" stop-color="#f0f7f3" />
      <stop offset="55%" stop-color="#cad7cf" />
      <stop offset="100%" stop-color="#9cb0a6" />
    </radialGradient>

    <!-- Soft outer drop shadow -->
    <filter id="dropShadow" x="-25%" y="-20%" width="150%" height="155%">
      <feDropShadow dx="0" dy="20" stdDeviation="22" flood-color="#000000" flood-opacity="0.55" />
    </filter>

    <!-- Lobe gradient -->
    <linearGradient id="lobeGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#fb923c" />
      <stop offset="100%" stop-color="#f97316" />
    </linearGradient>

    <!-- 4-lobe propeller path component -->
    <path id="lobe" d="M 256 107
             C 246 107, 237 122, 234 148
             C 231 168, 232 188, 235 210
             C 237 226, 241 242, 246 256
             L 266 256
             C 271 242, 275 226, 277 210
             C 280 188, 281 168, 278 148
             C 275 122, 266 107, 256 107 Z"
          fill="url(#lobeGrad)" />
  </defs>

  <!-- Outer Disc with Shadow and Border -->
  <circle cx="256" cy="256" r="198" fill="url(#discBg)" stroke="url(#borderGrad)" stroke-width="5" filter="url(#dropShadow)" />

  <!-- Diagonal Bead Chain (Inter-host link) -->
  <g id="beads">
    <circle cx="132" cy="380" r="10.5" fill="url(#beadGrad)" opacity="0.92" />
    <circle cx="144" cy="368" r="11" fill="url(#beadGrad)" opacity="0.94" />
    <circle cx="156" cy="356" r="11.5" fill="url(#beadGrad)" />
    <circle cx="168" cy="344" r="11.5" fill="url(#beadGrad)" />
    <circle cx="180" cy="332" r="11.5" fill="url(#beadGrad)" />
    <circle cx="192" cy="320" r="11.5" fill="url(#beadGrad)" />
    <circle cx="204" cy="308" r="11.5" fill="url(#beadGrad)" />
    <circle cx="216" cy="296" r="11.5" fill="url(#beadGrad)" />
    <circle cx="228" cy="284" r="11.5" fill="url(#beadGrad)" />
    <circle cx="240" cy="272" r="11.5" fill="url(#beadGrad)" />
    <circle cx="256" cy="256" r="11.5" fill="url(#beadGrad)" />
    <circle cx="272" cy="240" r="11.5" fill="url(#beadGrad)" />
    <circle cx="284" cy="228" r="11.5" fill="url(#beadGrad)" />
    <circle cx="296" cy="216" r="11.5" fill="url(#beadGrad)" />
    <circle cx="308" cy="204" r="11.5" fill="url(#beadGrad)" />
    <circle cx="320" cy="192" r="11.5" fill="url(#beadGrad)" />
    <circle cx="332" cy="180" r="11.5" fill="url(#beadGrad)" />
    <circle cx="344" cy="168" r="11.5" fill="url(#beadGrad)" />
    <circle cx="356" cy="156" r="11.5" fill="url(#beadGrad)" />
    <circle cx="368" cy="144" r="11" fill="url(#beadGrad)" opacity="0.94" />
    <circle cx="380" cy="132" r="10.5" fill="url(#beadGrad)" opacity="0.92" />

    <!-- Accent dots -->
    <!-- Bottom left -->
    <circle cx="154" cy="349" r="4.2" fill="#fb923c" />
    <circle cx="160" cy="357" r="5.6" fill="#87b4c8" />

    <!-- Top right -->
    <circle cx="358" cy="163" r="4.2" fill="#fb923c" />
    <circle cx="367" cy="173" r="5.6" fill="#87b4c8" />
  </g>

  <!-- 4 Lobes of the Propeller/Star -->
  <g id="propeller">
    <use href="#lobe" />
    <use href="#lobe" transform="rotate(90 256 256)" />
    <use href="#lobe" transform="rotate(180 256 256)" />
    <use href="#lobe" transform="rotate(270 256 256)" />
  </g>

  <!-- Center Core White Disc -->
  <circle cx="256" cy="256" r="27" fill="#ffffff" />
</svg>"""


def render_svg_to_pil(svg_text: str, size: int) -> Image.Image:
    """Renders the SVG to a PIL RGBA Image at the specified dimension using resvg or cairosvg."""
    if resvg_py is not None:
        png_bytes = resvg_py.svg_to_bytes(svg_text, width=size, height=size)
        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    if cairosvg is not None:
        png_bytes = cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), output_width=size, output_height=size)
        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    raise RuntimeError("Neither resvg_py nor cairosvg is available.")


def main():
    svg_content = get_svg_content()
    svg_path = os.path.join(OUTPUT_DIR, "icon.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f" [OK] Generated Scalable Vector Graphics: {svg_path}")

    # Render 512x512 Master PNG from SVG
    master_png = render_svg_to_pil(svg_content, 512)
    png_path = os.path.join(OUTPUT_DIR, "icon.png")
    master_png.save(png_path, format="PNG")
    print(f" [OK] Generated Master PNG: {png_path} ({master_png.size})")

    # Generate multi-layer Windows ICO
    sizes = [256, 128, 64, 48, 32, 24, 16]
    mipmaps = [master_png.resize((s, s), Image.Resampling.LANCZOS) for s in sizes]
    ico_path = os.path.join(OUTPUT_DIR, "icon.ico")
    mipmaps[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=mipmaps[1:]
    )
    print(f" [OK] Generated Multi-Resolution ICO: {ico_path} (Sizes: {sizes})")

    # Generate discrete PNG mipmaps for Linux packaging & high-DPI scaling
    icons_dir = os.path.join(OUTPUT_DIR, "icons")
    os.makedirs(icons_dir, exist_ok=True)
    all_sizes = [16, 24, 32, 48, 64, 128, 256, 512]
    for s in all_sizes:
        sub_img = master_png.resize((s, s), Image.Resampling.LANCZOS)
        sub_path = os.path.join(icons_dir, f"{s}x{s}.png")
        sub_img.save(sub_path, format="PNG")
    print(f" [OK] Generated discrete PNG mipmaps: {icons_dir} ({all_sizes})")


if __name__ == "__main__":
    main()
