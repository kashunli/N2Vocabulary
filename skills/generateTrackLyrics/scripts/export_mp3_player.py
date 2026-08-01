#!/usr/bin/env python3
"""Build and validate a flat N1/N2/N3 export for an MP3 player."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

from formats import safe_track_name, source_fingerprint


BOOKS = ("n1", "n2", "n3")
UNIT_FOLDER_RE = re.compile(r"^Unit(?P<unit>\d+(?:\.\d+)?)")
N1_DISC_RE = re.compile(r"Disc(?P<disc>[12])-", re.IGNORECASE)
N2_DISC_RE = re.compile(r"(?:^|\s)(?P<disc>[12])-(?P<track>\d+)(?:\s|$)")
N3_UNIT_RE = re.compile(r"_u(?P<unit>\d+)(?:_|$)", re.IGNORECASE)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def portable_unit(unit: str) -> str:
    """Keep review units visible while avoiding dots in player filenames."""
    return unit.replace(".", "-").lstrip("0") or "0"


def source_unit(book: str, source: Path) -> str:
    if book == "n3":
        match = N3_UNIT_RE.search(source.stem)
        if match:
            return str(int(match.group("unit")))
    match = UNIT_FOLDER_RE.match(source.parent.name)
    if not match:
        raise ValueError(f"Cannot determine unit from source path: {source}")
    return match.group("unit")


def source_disc(book: str, source: Path, unit: str) -> int:
    if book == "n1":
        match = N1_DISC_RE.search(source.stem)
        if not match:
            raise ValueError(f"Cannot determine N1 disc from: {source}")
        return int(match.group("disc"))
    if book == "n2":
        match = N2_DISC_RE.search(source.stem)
        if match:
            return int(match.group("disc"))
        # The retained N2 files switch to "Track N" naming after CD2 starts
        # at Unit7.5. Unit7's first two CD2 tracks retain explicit 2-N names.
        return 2 if float(unit) >= 7.5 else 1
    return 1 if int(unit) <= 6 else 2


def load_track_rows(track_lyrics_root: Path, book: str) -> list[dict]:
    book_dir = track_lyrics_root / book
    manifest = json.loads((book_dir / "manifest.json").read_text(encoding="utf-8"))
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for cue in manifest["cues"]:
        grouped[(cue["track"], cue["source_audio"])].append(cue)

    rows = []
    for (track, source_value), cues in grouped.items():
        source = Path(source_value)
        unit = source_unit(book, source)
        disc = source_disc(book, source, unit)
        lrc = book_dir / "tracks" / f"{safe_track_name(track)}.lrc"
        if not source.is_file() or not lrc.is_file():
            raise FileNotFoundError(f"Missing MP3/LRC input pair: {source} / {lrc}")
        rows.append(
            {
                "book": book.upper(),
                "track": track,
                "source_mp3": source,
                "source_lrc": lrc,
                "unit": unit,
                "disc": disc,
                "first_entry_id": min(int(cue["entry_id"]) for cue in cues),
            }
        )

    rows.sort(key=lambda row: (float(row["unit"]), row["disc"], row["first_entry_id"]))
    sequence_by_group: dict[tuple[str, int], int] = defaultdict(int)
    for row in rows:
        group = (row["unit"], row["disc"])
        sequence_by_group[group] += 1
        row["sequence"] = sequence_by_group[group]
        row["basename"] = (
            f"unit{portable_unit(row['unit'])}-cd{row['disc']}-track{row['sequence']}"
        )
    return rows


def assert_generated_child(path: Path, output_root: Path) -> None:
    """Guard recursive cleanup so it can only touch a generated child path."""
    resolved = path.resolve()
    root = output_root.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError(f"Refusing generated-folder cleanup outside {root}: {resolved}")


def build_export(root: Path, target: Path) -> dict:
    output_root = root / "output"
    track_lyrics_root = output_root / "track_lyrics"
    target = target.resolve()
    staging = target.with_name(f".{target.name}.build")
    assert_generated_child(target, output_root)
    assert_generated_child(staging, output_root)

    if staging.exists():
        shutil.rmtree(staging)
    for book in BOOKS:
        (staging / book.upper()).mkdir(parents=True, exist_ok=True)

    exported = []
    for book in BOOKS:
        for row in load_track_rows(track_lyrics_root, book):
            relative_mp3 = Path(book.upper()) / f"{row['basename']}.mp3"
            relative_lrc = Path(book.upper()) / f"{row['basename']}.lrc"
            shutil.copy2(row["source_mp3"], staging / relative_mp3)
            shutil.copy2(row["source_lrc"], staging / relative_lrc)
            exported.append(
                {
                    "book": row["book"],
                    "unit": row["unit"],
                    "disc": row["disc"],
                    "sequence": row["sequence"],
                    "first_entry_id": row["first_entry_id"],
                    "original_track": row["track"],
                    "source_mp3": str(row["source_mp3"].resolve()),
                    "source_lrc": str(row["source_lrc"].resolve()),
                    "exported_mp3": relative_mp3.as_posix(),
                    "exported_lrc": relative_lrc.as_posix(),
                    "mp3_fingerprint": source_fingerprint(row["source_mp3"]),
                    "lrc_fingerprint": source_fingerprint(row["source_lrc"]),
                }
            )

    if target.exists():
        shutil.rmtree(target)
    staging.rename(target)
    manifest = {
        "schema_version": 1,
        "status": "built",
        "target": str(target),
        "book_counts": {
            book.upper(): sum(row["book"] == book.upper() for row in exported)
            for book in BOOKS
        },
        "tracks": exported,
    }
    manifest_path = target.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return validate_export(target, manifest_path)


def validate_export(target: Path, manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[dict] = []
    expected_directories = {book.upper() for book in BOOKS}
    actual_directories = {path.name for path in target.iterdir() if path.is_dir()}
    if actual_directories != expected_directories:
        errors.append(
            {
                "reason": "subfolder_set_mismatch",
                "expected": sorted(expected_directories),
                "actual": sorted(actual_directories),
            }
        )

    for path in target.rglob("*"):
        if path.is_dir() and path.parent != target:
            errors.append({"reason": "nested_directory", "path": str(path)})
        if path.is_file() and path.suffix.lower() not in {".mp3", ".lrc"}:
            errors.append({"reason": "unexpected_extension", "path": str(path)})

    for row in manifest["tracks"]:
        mp3 = target / row["exported_mp3"]
        lrc = target / row["exported_lrc"]
        if mp3.stem != lrc.stem:
            errors.append({"reason": "basename_mismatch", "mp3": str(mp3), "lrc": str(lrc)})
            continue
        for kind, path, expected in (
            ("mp3", mp3, row["mp3_fingerprint"]),
            ("lrc", lrc, row["lrc_fingerprint"]),
        ):
            if not path.is_file():
                errors.append({"reason": "missing_export", "kind": kind, "path": str(path)})
            elif source_fingerprint(path) != expected:
                errors.append({"reason": "fingerprint_mismatch", "kind": kind, "path": str(path)})

    for book in BOOKS:
        folder = target / book.upper()
        mp3_stems = {path.stem for path in folder.glob("*.mp3")} if folder.is_dir() else set()
        lrc_stems = {path.stem for path in folder.glob("*.lrc")} if folder.is_dir() else set()
        if mp3_stems != lrc_stems:
            errors.append(
                {
                    "reason": "pair_set_mismatch",
                    "book": book.upper(),
                    "mp3_only": sorted(mp3_stems - lrc_stems),
                    "lrc_only": sorted(lrc_stems - mp3_stems),
                }
            )
        expected_count = manifest["book_counts"][book.upper()]
        if len(mp3_stems) != expected_count:
            errors.append(
                {
                    "reason": "track_count_mismatch",
                    "book": book.upper(),
                    "expected": expected_count,
                    "actual": len(mp3_stems),
                }
            )

    report = {
        "status": "accepted" if not errors else "failed",
        "error_count": len(errors),
        "errors": errors,
        "book_counts": manifest["book_counts"],
        "pair_count": len(manifest["tracks"]),
    }
    manifest["status"] = report["status"]
    manifest["validation"] = report
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--target", type=Path, default=None)
    args = parser.parse_args()
    root = repo_root()
    target = (args.target or root / "output" / "mp3_player_vocab_tracks").resolve()
    manifest_path = target.with_suffix(".manifest.json")
    report = (
        validate_export(target, manifest_path)
        if args.validate_only
        else build_export(root, target)
    )
    print(
        f"MP3-player export: {report['status']} "
        f"({report['pair_count']} MP3/LRC pairs, {report['error_count']} errors)"
    )
    raise SystemExit(0 if report["status"] == "accepted" else 1)


if __name__ == "__main__":
    main()
