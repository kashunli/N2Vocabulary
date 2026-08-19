#!/usr/bin/env python3
"""Import human-read Green Word Book N2 cut audio into WordService.

Reads `greenWordBook/work/cuts/p*/manifest.json` (word + example-sentence cuts)
and attaches each cut to its GWB_N2 DB entry. Matching is by exact normalized
example-sentence text only -- cut entry numbers cannot be trusted because the
DB was imported from an older OCR snapshot and is missing entries.

The old Edge TTS word/sentence audio is replaced in place:
  - words:     clips/gwb_n2/human/words/word{entry_id}.mp3
  - sentences: clips/gwb_n2/human/sentences/word{entry_id}_sentence{pos}.mp3
Both DB pointers (book_entries.word_clip and item_examples/entry_examples
audio_clip) are updated, and the DB is backed up first.

Run with --dry-run first to preview. Unmatched cut entries are reported and
skipped; they have no GWB_N2 DB row yet.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict

BOOK_CODE = "GWB_N2"
DEFAULT_CUTS_ROOT = r"D:\n2Prepare\greenWordBook\work\cuts"
DEFAULT_DB = "wordService/data/n2vocab.sqlite"
WORD_DST_DIR = "clips/gwb_n2/human/words"
SENTENCE_DST_DIR = "clips/gwb_n2/human/sentences"
OLD_SENTENCE_PREFIX = "clips/generated_sentences/edge_tts/"
MIN_MP3_BYTES = 1000


def norm(text: str, level: int = 1) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    if level >= 1:
        t = re.sub(r"\s+", "", t)
    if level >= 2:
        t = re.sub(r"[。．.！？!?、，,・:：;；「」『』（）()【】\[\]\"'～〜\u3000]", "", t)
    return t


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_cut_entries(cuts_root: str) -> list[dict]:
    entries = []
    for mpath in sorted(glob.glob(os.path.join(cuts_root, "p*", "manifest.json"))):
        m = read_json(mpath)
        for e in m["entries"]:
            entries.append(
                {
                    "entry_number": int(e["entry_number"]),
                    "headword": (e.get("headword") or "").strip(),
                    "bracket": ((e.get("book_content") or {}).get("bracket_form") or "").strip(),
                    "example": ((e.get("book_content") or {}).get("example_japanese") or "").strip(),
                    "word": e.get("clip_path"),
                    "sentence": e.get("sentence_clip_path"),
                    "part": os.path.basename(os.path.dirname(mpath)),
                }
            )
    return entries


def load_db(conn) -> tuple[list[dict], dict]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    db_entries = []
    for r in cur.execute(
        "SELECT be.entry_id, be.item_id, be.source_index, be.unit_number, "
        "be.sentence, be.word_clip, v.kanji, v.reading "
        "FROM book_entries be JOIN vocabulary_items v ON v.item_id = be.item_id "
        "WHERE be.book_code=?", (BOOK_CODE,)
    ).fetchall():
        ex_rows = cur.execute(
            "SELECT position, text, audio_clip FROM entry_examples "
            "WHERE entry_id=? ORDER BY position",
            (r["entry_id"],),
        ).fetchall()
        db_entries.append(
            {
                "entry_id": r["entry_id"],
                "item_id": r["item_id"],
                "source_index": r["source_index"],
                "unit_number": r["unit_number"],
                "sentence": (r["sentence"] or "").strip(),
                "word_clip": r["word_clip"],
                "kanji": (r["kanji"] or "").strip(),
                "reading": (r["reading"] or "").strip(),
                "examples": [
                    {"position": x["position"], "text": (x["text"] or "").strip(),
                     "audio_clip": x["audio_clip"]}
                    for x in ex_rows
                ],
            }
        )
    return db_entries


def build_matches(cut_entries: list[dict], db_entries: list[dict]) -> tuple[list[dict], dict]:
    idx = defaultdict(list)  # level1 example text -> [(entry_id, position)]
    idx2 = defaultdict(list)  # level2
    by_reading = defaultdict(list)
    by_kanji = defaultdict(list)
    for e in db_entries:
        for ex in e["examples"]:
            idx[norm(ex["text"], 1)].append((e["entry_id"], ex["position"]))
            idx2[norm(ex["text"], 2)].append((e["entry_id"], ex["position"]))
        if e["reading"]:
            by_reading[norm(e["reading"], 1)].append(e["entry_id"])
        if e["kanji"]:
            by_kanji[norm(e["kanji"], 1)].append(e["entry_id"])
    db_by_entry = {e["entry_id"]: e for e in db_entries}

    matches = []
    stats = Counter()
    skipped = []
    for c in cut_entries:
        example = c["example"]
        if not example:
            stats["no_example_text"] += 1
            skipped.append({**c, "reason": "no_example_text"})
            continue
        cands = idx[norm(example, 1)] or idx2[norm(example, 2)]
        if not cands:
            # Headword fallback against rows whose sentence matches at level 2.
            head_ids = set()
            for hw in (c["headword"], c["bracket"]):
                head_ids.update(by_reading[norm(hw, 1)])
                head_ids.update(by_kanji[norm(hw, 1)])
            for eid in head_ids:
                e = db_by_entry[eid]
                texts = [ex["text"] for ex in e["examples"]] + [e["sentence"]]
                if any(norm(t, 2) == norm(example, 2) for t in texts if t):
                    cands.append((eid, 0))
            if not cands:
                stats["no_db_match"] += 1
                skipped.append({**c, "reason": "no_db_match"})
                continue
            stats["headword_fallback"] += 1
        uniq = sorted(set(cands))
        if len(uniq) > 1:
            head_ids = set()
            for hw in (c["headword"], c["bracket"]):
                head_ids.update(by_reading[norm(hw, 1)])
                head_ids.update(by_kanji[norm(hw, 1)])
            narrowed = [u for u in uniq if u[0] in head_ids]
            if len(narrowed) != 1:
                stats["ambiguous"] += 1
                skipped.append({**c, "reason": "ambiguous", "candidates": uniq})
                continue
            uniq = narrowed
            stats["ambiguous_resolved_by_headword"] += 1
        entry_id, position = uniq[0]
        stats["matched"] += 1
        matches.append(
            {
                "cut_entry_number": c["entry_number"],
                "part": c["part"],
                "word": c["word"],
                "sentence": c["sentence"],
                "db_entry_id": entry_id,
                "example_position": position,
            }
        )
    return matches, {"stats": dict(stats), "skipped": skipped}


def plan_steps(root: str, matches: list[dict], db_entries: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    db_by_entry = {e["entry_id"]: e for e in db_entries}
    word_steps = []
    sentence_steps = []
    for m in matches:
        e = db_by_entry[m["db_entry_id"]]
        if m["word"]:
            src = os.path.join(root, m["part"], m["word"])
            dst_rel = f"{WORD_DST_DIR}/word{m['db_entry_id']}.mp3"
            word_steps.append(
                {
                    "entry_id": m["db_entry_id"],
                    "src": src,
                    "dst_rel": dst_rel,
                    "old_clip": e["word_clip"],
                }
            )
        if m["sentence"]:
            src = os.path.join(root, m["part"], m["sentence"])
            dst_rel = f"{SENTENCE_DST_DIR}/word{m['db_entry_id']}_sentence{m['example_position']}.mp3"
            old = None
            for ex in e["examples"]:
                if ex["position"] == m["example_position"]:
                    old = ex["audio_clip"]
            sentence_steps.append(
                {
                    "entry_id": m["db_entry_id"],
                    "item_id": e["item_id"],
                    "position": m["example_position"],
                    "src": src,
                    "dst_rel": dst_rel,
                    "old_clip": old,
                }
            )
    return word_steps, sentence_steps


def validate(root: str, word_steps, sentence_steps, db_path: str) -> list[str]:
    errors = []
    seen_dst = set()
    for s in word_steps + sentence_steps:
        if not os.path.isfile(s["src"]):
            errors.append(f"missing source: {s['src']}")
            continue
        if os.path.getsize(s["src"]) < MIN_MP3_BYTES:
            errors.append(f"suspiciously small source: {s['src']}")
        if s["dst_rel"] in seen_dst:
            errors.append(f"duplicate destination: {s['dst_rel']}")
        seen_dst.add(s["dst_rel"])
        dst = os.path.join(root, s["dst_rel"])
        if os.path.exists(dst):
            errors.append(f"destination already exists: {s['dst_rel']}")
    if not os.path.isfile(db_path):
        errors.append(f"DB not found: {db_path}")
    return errors


def backup_db(db_path: str) -> str:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{db_path}.backup_before_gwb_cut_audio_import_{ts}"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup)
    src.backup(dst)
    dst.close()
    src.close()
    return backup


def apply(root: str, db_path: str, word_steps, sentence_steps) -> None:
    os.makedirs(os.path.join(root, WORD_DST_DIR), exist_ok=True)
    os.makedirs(os.path.join(root, SENTENCE_DST_DIR), exist_ok=True)

    # Copy files first (all validated), then update DB.
    for s in word_steps + sentence_steps:
        dst = os.path.join(root, s["dst_rel"])
        shutil.copy2(s["src"], dst)
        if os.path.getsize(dst) != os.path.getsize(s["src"]):
            raise RuntimeError(f"copy size mismatch: {s['src']} -> {dst}")

    conn = sqlite3.connect(db_path, timeout=15)
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for s in word_steps:
            n = conn.execute(
                "UPDATE book_entries SET word_clip=? WHERE book_code=? AND entry_id=?",
                (s["dst_rel"], BOOK_CODE, s["entry_id"]),
            ).rowcount
            if n != 1:
                raise RuntimeError(f"word update failed for entry {s['entry_id']}")
        for s in sentence_steps:
            n = conn.execute(
                "UPDATE item_examples SET audio_clip=? WHERE item_id=? AND position=?",
                (s["dst_rel"], s["item_id"], s["position"]),
            ).rowcount
            if n != 1:
                raise RuntimeError(
                    f"item_examples update failed for item {s['item_id']} pos {s['position']}"
                )
            n = conn.execute(
                "UPDATE entry_examples SET audio_clip=? WHERE entry_id=? AND position=?",
                (s["dst_rel"], s["entry_id"], s["position"]),
            ).rowcount
            if n != 1:
                raise RuntimeError(
                    f"entry_examples update failed for entry {s['entry_id']} pos {s['position']}"
                )
            # A shared item can appear in multiple GWB_N2 book_entries with the
            # same example text; keep their per-entry rows consistent too.
            example_text = conn.execute(
                "SELECT text FROM entry_examples WHERE entry_id=? AND position=?",
                (s["entry_id"], s["position"]),
            ).fetchone()[0]
            for sibling in conn.execute(
                "SELECT be.entry_id FROM book_entries be "
                "JOIN entry_examples ex ON ex.entry_id = be.entry_id AND ex.position = ? "
                "WHERE be.item_id = ? AND be.book_code = ? AND be.entry_id != ? "
                "AND TRIM(ex.text) = ?",
                (s["position"], s["item_id"], BOOK_CODE, s["entry_id"], example_text),
            ).fetchall():
                conn.execute(
                    "UPDATE entry_examples SET audio_clip=? WHERE entry_id=? AND position=?",
                    (s["dst_rel"], sibling[0], s["position"]),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def verify(root: str, db_path: str, word_steps, sentence_steps) -> list[str]:
    problems = []
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT count(*) FROM book_entries WHERE book_code=? AND word_clip LIKE ?",
        (BOOK_CODE, WORD_DST_DIR + "/%"),
    )
    new_word_rows = cur.fetchone()[0]
    cur.execute(
        "SELECT count(*) FROM book_entries WHERE book_code=? AND word_clip LIKE ?",
        (BOOK_CODE, "clips/gwb_n2/words/%"),
    )
    old_word_rows = cur.fetchone()[0]
    # Count distinct updated example rows; a shared item can map to several
    # GWB_N2 book_entries, so a JOIN would double-count them.
    cur.execute(
        "SELECT count(*) FROM item_examples ex "
        "WHERE ex.audio_clip LIKE ? AND EXISTS ("
        "  SELECT 1 FROM book_entries be WHERE be.item_id = ex.item_id AND be.book_code = ?"
        ")",
        (SENTENCE_DST_DIR + "/%", BOOK_CODE),
    )
    new_sentence_rows = cur.fetchone()[0]
    cur.execute(
        "SELECT count(*) FROM item_examples ex JOIN book_entries be ON be.item_id=ex.item_id "
        "WHERE be.book_code=? AND ex.audio_clip LIKE ?",
        (BOOK_CODE, OLD_SENTENCE_PREFIX + "%"),
    )
    old_sentence_rows = cur.fetchone()[0]
    conn.close()

    if new_word_rows != len(word_steps):
        problems.append(f"new word rows {new_word_rows} != steps {len(word_steps)}")
    if new_sentence_rows != len(sentence_steps):
        problems.append(f"new sentence rows {new_sentence_rows} != steps {len(sentence_steps)}")

    missing = []
    for s in word_steps + sentence_steps:
        if not os.path.isfile(os.path.join(root, s["dst_rel"])):
            missing.append(s["dst_rel"])
    if missing:
        problems.append(f"{len(missing)} destination files missing")

    print(
        f"Verify: new word rows={new_word_rows}, old-path word rows={old_word_rows}, "
        f"new sentence rows={new_sentence_rows}, remaining GWB edge_tts rows={old_sentence_rows}"
    )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="N2Vocabulary repo root (default: cwd)")
    parser.add_argument("--cuts-root", default=DEFAULT_CUTS_ROOT)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--report", default="tmp/gwb_cut_audio_import_report.json")
    parser.add_argument("--dry-run", action="store_true", help="preview without changing anything")
    args = parser.parse_args()

    root = os.path.abspath(args.repo_root)
    db_path = os.path.join(root, args.db)
    cuts_root = os.path.abspath(args.cuts_root)

    cut_entries = load_cut_entries(cuts_root)
    conn = sqlite3.connect(db_path)
    db_entries = load_db(conn)
    conn.close()
    matches, meta = build_matches(cut_entries, db_entries)
    word_steps, sentence_steps = plan_steps(cuts_root, matches, db_entries)

    print(f"Cut entries: {len(cut_entries)} | matched: {meta['stats']['matched']}")
    print(f"Planned word files: {len(word_steps)} | sentence files: {len(sentence_steps)}")
    print("Skip stats:", {k: v for k, v in meta["stats"].items() if k != "matched"})

    errors = validate(root, word_steps, sentence_steps, db_path)
    if errors:
        print("FATAL validation errors:")
        for e in errors[:20]:
            print("  ", e)
        return 1

    report = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "cuts_root": cuts_root,
        "db": db_path,
        "stats": meta["stats"],
        "skipped": meta["skipped"],
        "word_plan": word_steps,
        "sentence_plan": sentence_steps,
    }
    os.makedirs(os.path.dirname(os.path.join(root, args.report)), exist_ok=True)
    with open(os.path.join(root, args.report), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"Report -> {os.path.join(root, args.report)}")

    if args.dry_run:
        print("Dry run — no changes made.")
        return 0

    backup = backup_db(db_path)
    print(f"DB backup -> {backup}")
    apply(root, db_path, word_steps, sentence_steps)
    print("Copied files and updated DB.")
    problems = verify(root, db_path, word_steps, sentence_steps)
    if problems:
        print("VERIFY FAILED:")
        for p in problems:
            print("  ", p)
        return 2
    print("Import verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
