"""Generate the OG banner image (1200x630) for Agent Eye.
Run once: `python dashboard/_build_og.py`."""
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630

# Dark gradient background — approximate the dashboard palette
img = Image.new("RGB", (W, H), "#0a0a0f")
draw = ImageDraw.Draw(img)

# Vertical gradient: #14141c → #0a0a0f
for y in range(H):
    t = y / H
    r = int(0x14 * (1 - t) + 0x0a * t)
    g = int(0x14 * (1 - t) + 0x0a * t)
    b = int(0x1c * (1 - t) + 0x0f * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# Soft purple glow in top-right corner
for i in range(180, 0, -6):
    a = int(40 * (180 - i) / 180)
    draw.ellipse([W - 320 - i, -180 - i, W + 80 + i, 220 + i], fill=(91 + a, 70 + a, 255))


def font(size, bold=False):
    """Try to load a font, fall back to default if not available."""
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf"  if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            pass
    return ImageFont.load_default()


# Brand mark — gradient circle with eye
cx, cy = 150, 230
r     = 70
# Draw a fake gradient (linear between two colors across the circle)
for i in range(r, 0, -2):
    t = i / r
    col = (
        int(91  * t + 168 * (1 - t)),
        int(140 * t + 85  * (1 - t)),
        int(255 * t + 247 * (1 - t)),
    )
    draw.ellipse([cx - i, cy - i, cx + i, cy + i], outline=col)

# Eye inside the circle (white)
draw.ellipse([cx - 50, cy - 25, cx + 50, cy + 25], outline="white", width=4)
draw.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill="white")
draw.ellipse([cx -  9, cy -  9, cx +  9, cy +  9], fill="#5b8cff")
draw.ellipse([cx +  4, cy -  6, cx +  9, cy -  1], fill="white")

# Title text
f_title  = font(78, bold=True)
f_sub    = font(34)
f_small  = font(22)
f_pill   = font(20, bold=True)

draw.text((270, 165), "Agent Eye", fill="#ffffff", font=f_title)
draw.text((270, 265), "AI Surveillance for Everyone", fill="#9ca3af", font=f_sub)
draw.text((270, 320), "Privacy-first face detection running on your own machine.", fill="#6b7280", font=f_small)

# Feature pills
pills = [("🔒  Privacy by design", "#10b981"),
         ("⚡  Real-time alerts",   "#f59e0b"),
         ("🌐  Multi-tenant",       "#5b8cff")]
x = 270
for text, color in pills:
    bbox = draw.textbbox((0, 0), text, font=f_pill)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x, pad_y = 18, 12
    draw.rounded_rectangle(
        [x, 400, x + tw + pad_x * 2, 400 + th + pad_y * 2],
        radius=22, fill="#1c1c28", outline=color, width=2,
    )
    draw.text((x + pad_x, 400 + pad_y - 2), text, fill="#e5e7eb", font=f_pill)
    x += tw + pad_x * 2 + 14

# URL bottom-right
draw.text((W - 380, H - 60), "agent-eye.live", fill="#5b8cff", font=f_small)

img.save("dashboard/og-image.png", "PNG", optimize=True)
print("OK dashboard/og-image.png")
