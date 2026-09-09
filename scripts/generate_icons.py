"""
Generates high-resolution, multi-layer application icons for Lunifier.
Design:
Two distinct stars in a square (one top-left, one bottom-right) separated by a dotted wall.
Represents two autonomous systems controlled in a unified way with zero shared data connection.
Outputs:
- lunifier/resources/icon.svg
- lunifier/resources/icon.png (512x512, 256x256, 128x128, 64x64, 48x48, 32x32, 16x16)
- lunifier/resources/icon.ico (embedded Windows multi-resolution mipmaps)
"""

import math
import os
from PIL import Image, ImageDraw, ImageFilter

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "lunifier", "resources")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_svg() -> str:
    svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <defs>
    <!-- Background rounded squircle gradient -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a" />
      <stop offset="100%" stop-color="#1e293b" />
    </linearGradient>

    <!-- Squircle Border gradient -->
    <linearGradient id="borderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4" />
      <stop offset="50%" stop-color="#64748b" stop-opacity="0.3" />
      <stop offset="100%" stop-color="#fb923c" stop-opacity="0.4" />
    </linearGradient>

    <!-- Star 1 (Top-Left) Cyan/Azure Glow -->
    <radialGradient id="star1Glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#00f0ff" stop-opacity="0.4" />
      <stop offset="100%" stop-color="#00f0ff" stop-opacity="0" />
    </radialGradient>
    <linearGradient id="star1Grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="40%" stop-color="#38bdf8" />
      <stop offset="100%" stop-color="#0284c7" />
    </linearGradient>

    <!-- Star 2 (Bottom-Right) Orange/Amber Glow -->
    <radialGradient id="star2Glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ff6d00" stop-opacity="0.4" />
      <stop offset="100%" stop-color="#ff6d00" stop-opacity="0" />
    </radialGradient>
    <linearGradient id="star2Grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="40%" stop-color="#fb923c" />
      <stop offset="100%" stop-color="#ea580c" />
    </linearGradient>

    <!-- Dotted Wall Dot Gradient -->
    <radialGradient id="dotGrad" cx="35%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#ffffff" />
      <stop offset="45%" stop-color="#94a3b8" />
      <stop offset="100%" stop-color="#475569" />
    </radialGradient>

    <filter id="softShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#000000" flood-opacity="0.5" />
    </filter>
  </defs>

  <!-- Base Squircle Container -->
  <rect x="28" y="28" width="456" height="456" rx="100" ry="100"
        fill="url(#bgGrad)" stroke="url(#borderGrad)" stroke-width="5" filter="url(#softShadow)" />

  <!-- Dotted Wall (Separating Diagonal) -->
  <!-- Line from (76, 436) to (436, 76) with discrete circular dots -->
  <g id="dotted-wall">
    <circle cx="96"  cy="416" r="6.5" fill="url(#dotGrad)" />
    <circle cx="123" cy="389" r="6.5" fill="url(#dotGrad)" />
    <circle cx="150" cy="362" r="6.5" fill="url(#dotGrad)" />
    <circle cx="177" cy="335" r="6.5" fill="url(#dotGrad)" />
    <circle cx="204" cy="308" r="6.5" fill="url(#dotGrad)" />
    <circle cx="231" cy="281" r="7.5" fill="url(#dotGrad)" />
    <circle cx="256" cy="256" r="8.5" fill="#e2e8f0" />
    <circle cx="281" cy="231" r="7.5" fill="url(#dotGrad)" />
    <circle cx="308" cy="204" r="6.5" fill="url(#dotGrad)" />
    <circle cx="335" cy="177" r="6.5" fill="url(#dotGrad)" />
    <circle cx="362" cy="150" r="6.5" fill="url(#dotGrad)" />
    <circle cx="389" cy="123" r="6.5" fill="url(#dotGrad)" />
    <circle cx="416" cy="96"  r="6.5" fill="url(#dotGrad)" />
  </g>

  <!-- Top-Left Star (System 1) -->
  <!-- Soft Glow Behind Star 1 -->
  <circle cx="160" cy="160" r="100" fill="url(#star1Glow)" />
  <!-- 4-pointed radiant Star 1 with curved flares -->
  <path d="M 160 82
           C 160 132, 132 160, 82 160
           C 132 160, 160 188, 160 238
           C 160 188, 188 160, 238 160
           C 188 160, 160 132, 160 82 Z"
        fill="url(#star1Grad)" />
  <!-- Bright core center -->
  <circle cx="160" cy="160" r="14" fill="#ffffff" />
  <!-- Small secondary sparkle -->
  <circle cx="215" cy="115" r="4.5" fill="#38bdf8" />
  <circle cx="108" cy="210" r="3.5" fill="#38bdf8" />

  <!-- Bottom-Right Star (System 2) -->
  <!-- Soft Glow Behind Star 2 -->
  <circle cx="352" cy="352" r="100" fill="url(#star2Glow)" />
  <!-- 4-pointed radiant Star 2 with curved flares -->
  <path d="M 352 274
           C 352 324, 324 352, 274 352
           C 324 352, 352 380, 352 430
           C 352 380, 380 352, 430 352
           C 380 352, 352 324, 352 274 Z"
        fill="url(#star2Grad)" />
  <!-- Bright core center -->
  <circle cx="352" cy="352" r="14" fill="#ffffff" />
  <!-- Small secondary sparkle -->
  <circle cx="297" cy="397" r="4.5" fill="#fb923c" />
  <circle cx="404" cy="302" r="3.5" fill="#fb923c" />
</svg>
"""
    return svg


def draw_star(draw: ImageDraw.ImageDraw, cx: float, cy: float, outer_r: float, inner_r: float, fill_color, core_color):
    """Draws a 4-pointed curved star."""
    points = []
    steps = 120
    for i in range(steps):
        theta = 2 * math.pi * i / steps
        # Astroid / squircle-like radius modulation
        # r(theta) = outer_r * inner_r / sqrt((inner_r*cos)^4 + (outer_r*sin)^4)
        cos2 = math.cos(2 * theta)
        # 4 points at 0, pi/2, pi, 3pi/2
        cos4 = math.cos(4 * theta)
        # Interpolate between outer_r (at theta = 0, pi/2...) and inner_r (at theta = pi/4, 3pi/4...)
        # A clean formula for 4-point flare:
        factor = (math.cos(4 * theta) + 1.0) / 2.0  # 1.0 at peaks, 0.0 at valleys
        r = inner_r + (outer_r - inner_r) * (factor ** 2.2)
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        points.append((x, y))

    draw.polygon(points, fill=fill_color)
    # Bright center core
    cr = inner_r * 0.9
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=core_color)


def generate_bitmap(size: int = 1024) -> Image.Image:
    """Renders high-resolution raster image with supersampling for anti-aliased perfection."""
    scale = 2
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 56 * scale
    rect_box = [margin, margin, canvas_size - margin, canvas_size - margin]
    radius = 190 * scale

    # 1. Background Rounded Square (Squircle)
    # Draw soft outer shadow
    shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_box = [margin, margin + 18 * scale, canvas_size - margin, canvas_size - margin + 18 * scale]
    shadow_draw.rounded_rectangle(shadow_box, radius=radius, fill=(0, 0, 0, 140))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24 * scale))
    img = Image.alpha_composite(shadow, img)
    draw = ImageDraw.Draw(img)

    # Base container
    draw.rounded_rectangle(rect_box, radius=radius, fill=(15, 23, 42, 255), outline=(71, 85, 105, 200), width=9 * scale)

    # 2. Dotted Wall (Separating line from bottom-left to top-right)
    # Start: ~18% from bottom-left, End: ~18% from top-right
    x1, y1 = margin + 80 * scale, canvas_size - margin - 80 * scale
    x2, y2 = canvas_size - margin - 80 * scale, margin + 80 * scale
    num_dots = 15
    for i in range(num_dots):
        t = i / (num_dots - 1)
        dx = x1 + t * (x2 - x1)
        dy = y1 + t * (y2 - y1)
        # Center dot is slightly larger / brighter
        dist_from_center = abs(t - 0.5)
        dot_r = (14.0 - dist_from_center * 5.0) * scale
        alpha = int(255 - dist_from_center * 70)
        draw.ellipse([dx - dot_r, dy - dot_r, dx + dot_r, dy + dot_r], fill=(226, 232, 240, alpha))

    # 3. Top-Left Star (System 1: Cyan / Azure Glow & Flare)
    s1_cx = margin + 200 * scale
    s1_cy = margin + 200 * scale

    # Glow layer
    glow1 = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    glow1_draw = ImageDraw.Draw(glow1)
    g1_r = 180 * scale
    glow1_draw.ellipse([s1_cx - g1_r, s1_cy - g1_r, s1_cx + g1_r, s1_cy + g1_r], fill=(0, 240, 255, 60))
    glow1 = glow1.filter(ImageFilter.GaussianBlur(36 * scale))
    img = Image.alpha_composite(img, glow1)
    draw = ImageDraw.Draw(img)

    # Star 1 shape
    draw_star(draw, s1_cx, s1_cy, outer_r=150 * scale, inner_r=30 * scale,
              fill_color=(56, 189, 248, 255), core_color=(255, 255, 255, 255))
    # Accompanying mini sparkles
    draw.ellipse([s1_cx + 105 * scale, s1_cy - 85 * scale, s1_cx + 117 * scale, s1_cy - 73 * scale], fill=(125, 211, 252, 240))
    draw.ellipse([s1_cx - 100 * scale, s1_cy + 95 * scale, s1_cx - 90 * scale, s1_cy + 105 * scale], fill=(125, 211, 252, 220))

    # 4. Bottom-Right Star (System 2: Orange / Amber Glow & Flare)
    s2_cx = canvas_size - margin - 200 * scale
    s2_cy = canvas_size - margin - 200 * scale

    # Glow layer
    glow2 = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    glow2_draw = ImageDraw.Draw(glow2)
    g2_r = 180 * scale
    glow2_draw.ellipse([s2_cx - g2_r, s2_cy - g2_r, s2_cx + g2_r, s2_cy + g2_r], fill=(255, 109, 0, 60))
    glow2 = glow2.filter(ImageFilter.GaussianBlur(36 * scale))
    img = Image.alpha_composite(img, glow2)
    draw = ImageDraw.Draw(img)

    # Star 2 shape
    draw_star(draw, s2_cx, s2_cy, outer_r=150 * scale, inner_r=30 * scale,
              fill_color=(251, 146, 60, 255), core_color=(255, 255, 255, 255))
    # Accompanying mini sparkles
    draw.ellipse([s2_cx - 105 * scale, s2_cy + 85 * scale, s2_cx - 93 * scale, s2_cy + 97 * scale], fill=(253, 186, 116, 240))
    draw.ellipse([s2_cx + 100 * scale, s2_cy - 95 * scale, s2_cx + 110 * scale, s2_cy - 85 * scale], fill=(253, 186, 116, 220))

    # Downsample with Lanczos for anti-aliasing
    final_img = img.resize((size, size), Image.Resampling.LANCZOS)
    return final_img


def main():
    # 1. Write SVG
    svg_content = generate_svg()
    svg_path = os.path.join(OUTPUT_DIR, "icon.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"Generated SVG: {svg_path}")

    # 2. Render 512x512 Master PNG
    master = generate_bitmap(512)
    png_path = os.path.join(OUTPUT_DIR, "icon.png")
    master.save(png_path, format="PNG")
    print(f"Generated PNG: {png_path} ({master.size})")

    # 3. Create Windows Multi-Resolution ICO
    # Mipmaps: 256x256, 128x128, 64x64, 48x48, 32x32, 16x16
    sizes = [256, 128, 64, 48, 32, 16]
    mipmaps = [master.resize((s, s), Image.Resampling.LANCZOS) for s in sizes]
    ico_path = os.path.join(OUTPUT_DIR, "icon.ico")
    mipmaps[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=mipmaps[1:]
    )
    print(f"Generated Multi-Layer ICO: {ico_path} (Sizes: {sizes})")


if __name__ == "__main__":
    main()
