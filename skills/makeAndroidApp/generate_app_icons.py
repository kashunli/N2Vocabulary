#!/usr/bin/env python3
"""Generate the Android launcher icons for wordService/mobile.

Concept: dark blue field, a cinnabar seal with 覚 (memorize), and a cream
audio waveform — "Japanese word memorization with audio". Overwrites the
Capacitor default icons in place, at every density.

Densities -> legacy px / adaptive foreground px (Android standard sizes).
"""

import os
from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/meiryo.ttc"
WAVE_BG = (31, 35, 48)          # adaptive-icon background color
SEAL_RED = (199, 57, 44)
CREAM = (247, 241, 230)

DENSITIES = {
    "mdpi": (48, 108),
    "hdpi": (72, 162),
    "xhdpi": (96, 216),
    "xxhdpi": (144, 324),
    "xxxhdpi": (192, 432),
}

HEIGHTS = [0.20, 0.45, 0.32, 0.62, 0.40, 0.75, 0.55, 0.85, 0.50, 0.70, 0.42, 0.60, 0.35, 0.25]

RES_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "wordService", "mobile", "android", "app", "src", "main", "res")
)
BG_COLOR_XML = os.path.join(RES_ROOT, "values", "ic_launcher_background.xml")


def glyph(size, fraction=0.56, color=(255, 255, 255, 255)):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(size * fraction))
    bbox = draw.textbbox((0, 0), "覚", font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), "覚", font=font, fill=color)
    return img


def seal(size, glyph_fraction=0.54):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle([0, 0, size - 1, size - 1], int(size * 0.16), fill=SEAL_RED)
    img.alpha_composite(glyph(size, glyph_fraction))
    return img


def bars(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    bar_w = int(size * 0.040)
    gap = int(size * 0.028)
    count = len(HEIGHTS)
    total = count * bar_w + (count - 1) * gap
    x0 = (size - total) // 2
    base = int(size * 0.78)
    for i, h in enumerate(HEIGHTS):
        bh = int(size * 0.34 * h)
        x = x0 + i * (bar_w + gap)
        draw.rounded_rectangle([x, base - bh, x + bar_w, base + int(size * 0.06)], max(1, int(bar_w / 2)), fill=CREAM)
    return img


def artwork(size):
    """Transparent composition of the seal + waveform at a given canvas size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    s = int(size * 0.40)
    img.alpha_composite(seal(s, 0.54), ((size - s) // 2, int(size * 0.10)))
    img.alpha_composite(bars(size))
    return img


def legacy(size):
    """Full-color launcher icon: dark field + seal + waveform."""
    img = Image.new("RGBA", (size, size), WAVE_BG + (255,))
    img.alpha_composite(artwork(size))
    return img


def foreground(size):
    """Adaptive foreground: artwork scaled into the safe zone on transparent."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    art = artwork(int(size * 0.72)).resize((int(size * 0.72), int(size * 0.72)), Image.LANCZOS)
    offset = (size - art.size[0]) // 2
    img.alpha_composite(art, (offset, offset))
    return img


def write_pngs() -> int:
    written = 0
    for density, (legacy_size, fg_size) in DENSITIES.items():
        mip = os.path.join(RES_ROOT, f"mipmap-{density}")
        if not os.path.isdir(mip):
            print(f"skip (no dir): {mip}")
            continue
        legacy_img = legacy(legacy_size)
        for name in ("ic_launcher.png", "ic_launcher_round.png"):
            legacy_img.convert("RGB").save(os.path.join(mip, name))
            written += 1
        foreground(fg_size).save(os.path.join(mip, "ic_launcher_foreground.png"))
        written += 1
    return written


def write_background_color() -> None:
    with open(BG_COLOR_XML, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n')
        f.write(f'    <color name="ic_launcher_background">#{WAVE_BG[0]:02X}{WAVE_BG[1]:02X}{WAVE_BG[2]:02X}</color>\n')
        f.write("</resources>\n")


if __name__ == "__main__":
    n = write_pngs()
    write_background_color()
    print(f"wrote {n} icon files; adaptive background = #{WAVE_BG[0]:02X}{WAVE_BG[1]:02X}{WAVE_BG[2]:02X}")
