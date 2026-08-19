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
DEFAULT_GREEN_ROOT = r"D:\n2Prepare\greenWordBook"
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
            try:
                number_padded = str(int(e["entry_number"])).zfill(4)
            except (TypeError, ValueError):
                number_padded = str(e.get("entry_number") or "").strip()
            entries.append(
                {
                    "entry_number": int(e["entry_number"]),
                    "entry_number_padded": number_padded,
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


def build_matches(
    cut_entries: list[dict],
    db_entries: list[dict],
    records_by_number: dict[str, dict] | None = None,
    db_by_source_index: dict[int, dict] | None = None,
) -> tuple[list[dict], dict]:
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
            # No OCR-backed example text (manifest gap). The word clip can
            # still be attached when the printed entry number resolves to the
            # record's actual JSON position (never assume number == position).
            if records_by_number and db_by_source_index:
                rec = records_by_number.get(c["entry_number_padded"])
                if rec is None:
                    stats["no_example_text"] += 1
                    skipped.append({**c, "reason": "no_example_text_no_record"})
                    continue
                src_index = rec["position"]
                row = db_by_source_index.get(src_index)
                if row is None:
                    stats["no_example_text"] += 1
                    skipped.append({**c, "reason": "no_example_text_no_db_row"})
                    continue
                head_matches = (
                    norm(row["reading"], 1) == norm(c["headword"], 1)
                    or norm(row["kanji"], 1) == norm(c["headword"], 1)
                    or (c["bracket"] and norm(row["kanji"], 1) == norm(c["bracket"], 1))
                )
                if not head_matches:
                    stats["no_example_text"] += 1
                    skipped.append({**c, "reason": "no_example_text_headword_mismatch",
                                    "db_row": (src_index, row["kanji"], row["reading"])})
                    continue
                stats["entry_number_fallback"] += 1
                matches.append(
                    {
                        "cut_entry_number": c["entry_number"],
                        "part": c["part"],
                        "word": c["word"],
                        "sentence": None,
                        "db_entry_id": row["entry_id"],
                        "example_position": 0,
                        "match_kind": "entry_number_fallback",
                    }
                )
                continue
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
        example_text = next(
            ex["text"] for ex in db_by_entry[entry_id]["examples"]
            if ex["position"] == position
        )
        matches.append(
            {
                "cut_entry_number": c["entry_number"],
                "part": c["part"],
                "word": c["word"],
                "sentence": c["sentence"],
                "db_entry_id": entry_id,
                "example_position": position,
                "example_text": example_text,
                "match_kind": "text",
            }
        )
    return matches, {"stats": dict(stats), "skipped": skipped}


def plan_steps(
    root: str,
    matches: list[dict],
    db_entries: list[dict],
    item_examples_texts: dict[int, list[tuple[int, str]]],
) -> tuple[list[dict], list[dict], list[dict]]:
    db_by_entry = {e["entry_id"]: e for e in db_entries}
    word_steps = []
    sentence_steps = []
    skipped_sentences = []
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
            # Shared items can carry the example at any position; resolve by
            # text instead of assuming entry_examples position == item position.
            item_pos = None
            for pos, text in item_examples_texts.get(e["item_id"], []):
                if (text or "").strip() == (m.get("example_text") or ""):
                    item_pos = pos
                    break
            if item_pos is None:
                skipped_sentences.append(
                    {
                        "entry_id": m["db_entry_id"],
                        "reason": "no_item_example_text_match",
                    }
                )
                continue
            sentence_steps.append(
                {
                    "entry_id": m["db_entry_id"],
                    "item_id": e["item_id"],
                    "position": m["example_position"],
                    "item_position": item_pos,
                    "src": src,
                    "dst_rel": dst_rel,
                    "old_clip": old,
                }
            )
    return word_steps, sentence_steps, skipped_sentences


def validate(root: str, word_steps, sentence_steps, db_path: str, overwrite: bool = False) -> list[str]:
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
        if os.path.exists(dst) and not overwrite:
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
                (s["dst_rel"], s["item_id"], s["item_position"]),
            ).rowcount
            if n != 1:
                raise RuntimeError(
                    f"item_examples update failed for item {s['item_id']} "
                    f"item_pos {s['item_position']}"
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
    parser.add_argument("--green-root", default=DEFAULT_GREEN_ROOT)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--report", default="tmp/gwb_cut_audio_import_report.json")
    parser.add_argument("--dry-run", action="store_true", help="preview without changing anything")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="allow re-copying over destinations that already exist (re-run after boundary review)",
    )
    args = parser.parse_args()

    root = os.path.abspath(args.repo_root)
    db_path = os.path.join(root, args.db)
    cuts_root = os.path.abspath(args.cuts_root)
    green_root = os.path.abspath(args.green_root)

    cut_entries = load_cut_entries(cuts_root)
    conn = sqlite3.connect(db_path)
    db_entries = load_db(conn)
    # Current book records by printed entry number -> actual JSON position.
    records_by_number = {}
    book_payload = read_json(os.path.join(green_root, "data", "green_word_book_n2_vocab.json"))
    for pos, rec in enumerate(book_payload["records"], start=1):
        try:
            number_padded = str(int(rec["entry_number"])).zfill(4)
        except (TypeError, KeyError, ValueError):
            number_padded = str(rec.get("entry_number") or "").strip()
        if number_padded and number_padded not in records_by_number:
            records_by_number[number_padded] = {**rec, "position": pos}
    db_by_source_index = {
        e["source_index"]: e for e in db_entries if e["source_index"] is not None
    }
    item_examples_texts = {}
    for item_id, position, text in conn.execute(
        "SELECT item_id, position, text FROM item_examples"
    ).fetchall():
        item_examples_texts.setdefault(item_id, []).append((position, text or ""))
    conn.close()
    matches, meta = build_matches(cut_entries, db_entries, records_by_number, db_by_source_index)
    word_steps, sentence_steps, skipped_sentences = plan_steps(
        cuts_root, matches, db_entries, item_examples_texts
    )

    print(f"Cut entries: {len(cut_entries)} | matched: {meta['stats']['matched']}")
    print(f"Planned word files: {len(word_steps)} | sentence files: {len(sentence_steps)}")
    print("Skip stats:", {k: v for k, v in meta["stats"].items() if k != "matched"})
    if skipped_sentences:
        print(f"Sentences skipped (no item_examples text match): {len(skipped_sentences)}")
        for s in skipped_sentences[:10]:
            print("  ", s)

    errors = validate(root, word_steps, sentence_steps, db_path, args.overwrite)
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
        "skipped_sentences": skipped_sentences,
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
