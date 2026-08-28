"""Generate the Windows ICO from the N2 Vocabulary tanuki favicon design.

The geometry mirrors ``wordService/static/favicon.svg``. Drawing at a large
working resolution before downsampling gives the small Windows icon sizes
clean rounded edges and keeps this generated binary reproducible.
"""

from pathlib import Path

from PIL import Image, ImageDraw


VIEWBOX_SIZE = 64
WORKING_SIZE = 1024
SCALE = WORKING_SIZE // VIEWBOX_SIZE
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

CREAM = "#f7f1e6"
DARK_BROWN = "#332725"
TANUKI_BROWN = "#b96d38"
TANUKI_TAN = "#d9995b"
MUZZLE = "#f7d5a7"
VERMILION = "#d44735"

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "wordService" / "assets" / "n2-vocabulary.ico"
ANDROID_RESOURCES = ROOT / "wordService" / "mobile" / "android" / "app" / "src" / "main" / "res"
ANDROID_ICON_SIZES = {
    "mdpi": (48, 108),
    "hdpi": (72, 162),
    "xhdpi": (96, 216),
    "xxhdpi": (144, 324),
    "xxxhdpi": (192, 432),
}


def px(value: float) -> int:
    return round(value * SCALE)


def scaled_points(points: list[tuple[float, float]]) -> list[tuple[int, int]]:
    return [(px(x), px(y)) for x, y in points]


def build_icon() -> Image.Image:
    """Build the tanuki-with-book mark, retaining the SVG's bold small-icon geometry."""

    image = Image.new("RGBA", (WORKING_SIZE, WORKING_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (0, 0, WORKING_SIZE - 1, WORKING_SIZE - 1), radius=px(14), fill=CREAM
    )
    # Ears sit behind the face, as in the SVG.
    draw.polygon(scaled_points([(8, 29), (10, 12), (24, 21)]), fill=DARK_BROWN)
    draw.polygon(scaled_points([(56, 29), (54, 12), (40, 21)]), fill=DARK_BROWN)
    draw.ellipse((px(11), px(8), px(53), px(58)), fill=TANUKI_BROWN)
    draw.polygon(scaled_points([(16, 20), (22, 14), (42, 14), (48, 20), (45, 27), (19, 27)]), fill=TANUKI_TAN)

    # The two dark pages deliberately form the tanuki eye mask.
    draw.polygon(scaled_points([(14, 28), (20, 25), (27, 26), (32, 30), (32, 47), (26, 44), (20, 44), (14, 45)]), fill=DARK_BROWN)
    draw.polygon(scaled_points([(50, 28), (44, 25), (37, 26), (32, 30), (32, 47), (38, 44), (44, 44), (50, 45)]), fill=DARK_BROWN)
    # White page borders and centre seam match the graphic contrast of the SVG.
    draw.line(scaled_points([(14, 28), (20, 25), (27, 26), (32, 30), (32, 47), (26, 44), (20, 44), (14, 45), (14, 28)]), fill="#fffaf2", width=px(2.7), joint="curve")
    draw.line(scaled_points([(50, 28), (44, 25), (37, 26), (32, 30), (32, 47), (38, 44), (44, 44), (50, 45), (50, 28)]), fill="#fffaf2", width=px(2.7), joint="curve")
    draw.line(scaled_points([(32, 30), (32, 47)]), fill="#fffaf2", width=px(2.2))

    for center in ((24, 37), (40, 37)):
        x, y = center
        draw.ellipse((px(x - 3.6), px(y - 3.6), px(x + 3.6), px(y + 3.6)), fill="#fffaf2")
        draw.ellipse((px(x - 1.7), px(y - 1.7), px(x + 1.7), px(y + 1.7)), fill=DARK_BROWN)
    draw.polygon(scaled_points([(42, 27), (47, 27), (47, 36), (44.5, 34), (42, 36)]), fill=VERMILION)
    draw.ellipse((px(25), px(49), px(39), px(56)), fill=MUZZLE)
    draw.arc((px(29), px(48), px(35), px(53)), start=0, end=180, fill=DARK_BROWN, width=px(1.6))

    return image


def build_adaptive_foreground() -> Image.Image:
    """Build an Android-safe 108 dp foreground from the same tanuki mark.

    Android applies device-specific masks to adaptive icons. Keeping the mark
    inside the central 74 dp gives the ears and bookmark room on circular,
    squircle, and rounded-square launchers.
    """

    mark = build_icon()
    pixels = mark.load()
    for y in range(mark.height):
        for x in range(mark.width):
            red, green, blue, alpha = pixels[x, y]
            if (red, green, blue) == (247, 241, 230):
                pixels[x, y] = (red, green, blue, 0)

    canvas = Image.new("RGBA", (px(108), px(108)), (0, 0, 0, 0))
    mark = mark.resize((px(74), px(74)), Image.Resampling.LANCZOS)
    canvas.alpha_composite(mark, (px(17), px(17)))
    return canvas


def save_android_icons() -> None:
    """Write legacy and adaptive Android launcher PNGs from the shared artwork."""

    icon = build_icon()
    foreground = build_adaptive_foreground()
    for density, (icon_size, foreground_size) in ANDROID_ICON_SIZES.items():
        output_directory = ANDROID_RESOURCES / f"mipmap-{density}"
        output_directory.mkdir(parents=True, exist_ok=True)
        legacy_icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
        legacy_icon.save(output_directory / "ic_launcher.png")
        legacy_icon.save(output_directory / "ic_launcher_round.png")
        foreground.resize(
            (foreground_size, foreground_size), Image.Resampling.LANCZOS
        ).save(output_directory / "ic_launcher_foreground.png")


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    build_icon().save(OUTPUT, format="ICO", sizes=ICON_SIZES)
    save_android_icons()
    print(f"Created {OUTPUT}")
    print(f"Updated Android launcher icons under {ANDROID_RESOURCES}")


if __name__ == "__main__":
    main()
