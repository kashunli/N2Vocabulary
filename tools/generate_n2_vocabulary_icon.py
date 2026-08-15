"""Generate the Windows ICO from the N2 Vocabulary favicon design.

The geometry mirrors wordService/static/favicon.svg. Drawing at a large
working resolution before downsampling gives the small Windows icon sizes
clean rounded edges and keeps this generated binary reproducible.
"""

from pathlib import Path

from PIL import Image, ImageDraw


VIEWBOX_SIZE = 64
WORKING_SIZE = 1024
SCALE = WORKING_SIZE // VIEWBOX_SIZE
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "wordService" / "assets" / "n2-vocabulary.ico"


def px(value: float) -> int:
    return round(value * SCALE)


def draw_round_line(draw: ImageDraw.ImageDraw, points, fill, width) -> None:
    """Draw a stroked SVG-style line with round caps."""

    scaled_points = [(px(x), px(y)) for x, y in points]
    scaled_width = px(width)
    draw.line(scaled_points, fill=fill, width=scaled_width)
    radius = scaled_width / 2
    for x, y in (scaled_points[0], scaled_points[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def build_icon() -> Image.Image:
    image = Image.new("RGBA", (WORKING_SIZE, WORKING_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # <rect width="64" height="64" rx="14" fill="#1e3a5f"/>
    draw.rounded_rectangle(
        (0, 0, WORKING_SIZE - 1, WORKING_SIZE - 1),
        radius=px(14),
        fill="#1e3a5f",
    )

    # The three pale vertical study columns from favicon.svg.
    for x in (17, 31, 45):
        draw_round_line(
            draw,
            [(x, 13), (x, 51)],
            fill="#f8f2e8e6",
            width=4,
        )

    # SVG stroke is centered on the circle boundary: draw the white outer
    # stroke first, then the red fill inside it.
    draw.ellipse(
        (px(31 - 9.5), px(32 - 9.5), px(31 + 9.5), px(32 + 9.5)),
        fill="#fffaf2",
    )
    draw.ellipse(
        (px(31 - 8), px(32 - 8), px(31 + 8), px(32 + 8)),
        fill="#c2413b",
    )

    return image


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    build_icon().save(OUTPUT, format="ICO", sizes=ICON_SIZES)
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
