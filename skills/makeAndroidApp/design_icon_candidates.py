#!/usr/bin/env python3
"""Generate app-icon design candidates for the N2 Vocabulary Android app.

Renders several flat/minimal launcher-icon concepts at 1024x1024 into
output/_icon_candidates/, plus a labelled contact sheet. Pick one, then the
chosen design is baked into generate_app_icons.py.
"""

import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 1024
SS = 4
BIG = S * SS

RED_TOP = (224, 74, 50)
RED_BOT = (178, 58, 38)
CREAM = (247, 241, 230)
INK = (60, 55, 52)
DARK_TOP = (46, 44, 54)
DARK_BOT = (30, 29, 37)
WAVE_BG = (31, 35, 48)

FONT_SEAL = "C:/Windows/Fonts/meiryo.ttc"
FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"

OUT = r"D:/n2Prepare/N2Vocabulary/output/_icon_candidates"
os.makedirs(OUT, exist_ok=True)


def gradient(size, top, bottom):
    img = Image.new("RGB", (1, size[1]))
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        img.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return img.resize(size)


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1], radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def glyph_img(size, fraction=0.56, color=(255, 255, 255, 255), char="印"):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_SEAL, int(size * fraction))
    bbox = d.textbbox((0, 0), char, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), char, font=font, fill=color)
    return img


def seal_square(size, fill, glyph_fraction=0.56, rotation=0, char="印"):
    sq = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(sq).rounded_rectangle([0, 0, size - 1, size - 1], int(size * 0.16), fill=fill)
    sq.alpha_composite(glyph_img(size, glyph_fraction, char=char))
    if rotation:
        sq = sq.rotate(rotation, resample=Image.BICUBIC)
    return sq


def text_img(size, text, font_path, fraction, color, weight=None):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, int(size * fraction))
    bbox = d.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), text, font=font, fill=color)
    return img


def candidate_a(char="印"):
    """Cinnabar gradient seal — refined version of the current flat seal."""
    bg = gradient((BIG, BIG), RED_TOP, RED_BOT).convert("RGBA")
    # cream inner ring
    ring = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    r = int(BIG * 0.085)
    ImageDraw.Draw(ring).rounded_rectangle([r, r, BIG - 1 - r, BIG - 1 - r], int(BIG * 0.20), outline=CREAM, width=int(BIG * 0.022))
    bg.alpha_composite(ring)
    # glyph with a soft drop shadow
    g = glyph_img(BIG, 0.5, char=char)
    shadow = glyph_img(BIG, 0.5, (150, 40, 30, 200), char=char)
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(BIG * 0.012)))
    bg.alpha_composite(shadow, (0, int(BIG * 0.012)))
    bg.alpha_composite(g)
    return rounded(bg, int(BIG * 0.21))


def candidate_b(char="印"):
    """Cream paper + tilted red stamp, with an ink N2 mark."""
    bg = Image.new("RGBA", (BIG, BIG), CREAM + (255,))
    seal = seal_square(int(BIG * 0.56), RED_TOP, glyph_fraction=0.54, rotation=-4, char=char)
    seal_x = int((BIG - seal.size[0]) / 2)
    seal_y = int(BIG * 0.17)
    bg.alpha_composite(seal, (seal_x, seal_y))
    n2 = text_img(BIG, "N2", FONT_BOLD, 0.16, INK + (255,))
    bg.alpha_composite(n2, (0, int(BIG * 0.72)))
    return rounded(bg, int(BIG * 0.21))


def candidate_c(char="印"):
    """Dark ink field with a cinnabar seal accent."""
    bg = gradient((BIG, BIG), DARK_TOP, DARK_BOT).convert("RGBA")
    seal = seal_square(int(BIG * 0.52), RED_TOP, glyph_fraction=0.54, char=char)
    bg.alpha_composite(seal, (int((BIG - seal.size[0]) / 2), int(BIG * 0.24)))
    ring = Image.new("RGBA", (BIG, BIG), (0, 0, 0, 0))
    r = int(BIG * 0.085)
    ImageDraw.Draw(ring).rounded_rectangle([r, r, BIG - 1 - r, BIG - 1 - r], int(BIG * 0.20), outline=(180, 176, 190, 255), width=int(BIG * 0.014))
    bg.alpha_composite(ring)
    return rounded(bg, int(BIG * 0.21))


def candidate_d(char="印"):
    """Audio study — waveform bars under a seal mark."""
    bg = Image.new("RGBA", (BIG, BIG), WAVE_BG + (255,))
    seal = seal_square(int(BIG * 0.40), RED_TOP, glyph_fraction=0.54, char=char)
    bg.alpha_composite(seal, (int((BIG - seal.size[0]) / 2), int(BIG * 0.10)))
    # waveform bars across the lower third
    bar_w = int(BIG * 0.045)
    gap = int(BIG * 0.032)
    n_bars = 14
    total = n_bars * bar_w + (n_bars - 1) * gap
    x0 = int((BIG - total) / 2)
    base_y = int(BIG * 0.78)
    heights = [0.20, 0.45, 0.32, 0.62, 0.40, 0.75, 0.55, 0.85, 0.50, 0.70, 0.42, 0.60, 0.35, 0.25]
    d = ImageDraw.Draw(bg)
    for i, h in enumerate(heights):
        bh = int(BIG * 0.34 * h)
        x = x0 + i * (bar_w + gap)
        d.rounded_rectangle([x, base_y - bh, x + bar_w, base_y + int(BIG * 0.06)], int(bar_w / 2), fill=CREAM + (255,))
    return rounded(bg, int(BIG * 0.21))


def main():
    cands = [("A · Cinnabar · 語", candidate_a("語")), ("B · Paper & stamp · 語", candidate_b("語")),
             ("C · Ink dark · 語", candidate_c("語")), ("D · Audio · 覚", candidate_d("覚"))]
    for name, img in cands:
        img.resize((S, S), Image.LANCZOS).save(os.path.join(OUT, name.split("·")[0].strip().lower().replace(" ", "_") + ".png"))
    # contact sheet 2x2
    cell = S + 40
    sheet = Image.new("RGB", (cell * 2, cell * 2), (240, 240, 240))
    d = ImageDraw.Draw(sheet)
    label_font = ImageFont.truetype(FONT_BOLD, 36)
    for i, (name, img) in enumerate(cands):
        small = img.resize((S, S), Image.LANCZOS)
        cx = (i % 2) * cell
        cy = (i // 2) * cell
        sheet.paste(small, (cx + 20, cy + 20), small if small.mode == "RGBA" else None)
        d.text((cx + 20, cy + S + 30), name, fill=(60, 60, 60), font=label_font)
    sheet.save(os.path.join(OUT, "contact_sheet.png"))
    print("wrote candidates to", OUT)


if __name__ == "__main__":
    main()
