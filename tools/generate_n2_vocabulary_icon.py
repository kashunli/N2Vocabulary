"""Generate N2 Vocabulary icon formats from the approved tanuki master art.

Every shipped representation is resampled from one user-approved PNG rather
than redrawn. This preserves the selected tanuki's face, book mask, whiskers,
bookmark, soft shadows, and cream tile across web, Windows, and Android.
"""

from pathlib import Path

from PIL import Image


WORKING_SIZE = 1024
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "wordService" / "assets" / "n2-vocabulary.ico"
MASTER_ART = ROOT / "wordService" / "assets" / "n2-vocabulary-tanuki-master.png"
WEB_FAVICON = ROOT / "wordService" / "static" / "favicon.png"
ANDROID_RESOURCES = ROOT / "wordService" / "mobile" / "android" / "app" / "src" / "main" / "res"
ANDROID_ICON_SIZES = {
    "mdpi": (48, 108),
    "hdpi": (72, 162),
    "xhdpi": (96, 216),
    "xxhdpi": (144, 324),
    "xxxhdpi": (192, 432),
}


def build_icon() -> Image.Image:
    """Return a high-resolution copy of the exact user-approved artwork."""

    with Image.open(MASTER_ART) as source:
        return source.convert("RGBA").resize(
            (WORKING_SIZE, WORKING_SIZE), Image.Resampling.LANCZOS
        )


def build_adaptive_foreground() -> Image.Image:
    """Make the adaptive layer directly from the master, preserving its tile."""

    return build_icon().resize((1080, 1080), Image.Resampling.LANCZOS)


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
    icon = build_icon()
    icon.save(OUTPUT, format="ICO", sizes=ICON_SIZES)
    WEB_FAVICON.parent.mkdir(parents=True, exist_ok=True)
    icon.resize((512, 512), Image.Resampling.LANCZOS).save(WEB_FAVICON)
    save_android_icons()
    print(f"Created {OUTPUT}")
    print(f"Created {WEB_FAVICON}")
    print(f"Updated Android launcher icons under {ANDROID_RESOURCES}")


if __name__ == "__main__":
    main()
