#!/usr/bin/env python3
"""Combine vocabulary_db.json and vocabulary_combined.json into a single file.

Handles three issues:
1. Normal combine: explanation from db + examples from combined
2. Overwritten entries: wrong-numbered entries in raw JSON overwrote correct ones
   - Restore correct entries from raw JSON
   - Move misnumbered entries + their DB data to correct indices
3. Positional null entries: assign indices based on position
"""

import json
import glob
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "output", "vocabulary_db.json")
COMBINED_PATH = os.path.join(BASE_DIR, "output", "vocabulary_combined.json")
JSON_DIR = os.path.join(BASE_DIR, "json")
OUTPUT_PATH = os.path.join(BASE_DIR, "output", "vocabulary_combined_final.json")
RESTORED_PATH = os.path.join(BASE_DIR, "output", "vocabulary_missing_restored.json")

# Mapping: wrong_number -> (correct_index, kanji_hint, source_page)
# These entries were parsed with the wrong number and overwrote the real entries
MISNUMBERED = {
    # (wrong_num, correct_index, kanji, source_page_for_wrong_entry)
    584: (610, "監督", 126),   # page_126 parsed 監督 as #584, should be #610
    589: (639, "解放", 133),   # page_133 parsed 解放 as #589, should be #639
    656: (663, "開発", 138),   # page_138 parsed 開発 as #656, should be #663
    657: (664, "開店", 138),   # page_138 parsed 開店 as #657, should be #664
    658: (665, "開業", 138),   # page_138 parsed 開業 as #658, should be #665
    659: (666, "開催", 138),   # page_138 parsed 開催 as #659, should be #666
    660: (667, "開放", 138),   # page_138 parsed 開放 as #660, should be #667
    966: (962, "管理", 207),   # page_207 parsed 管理 as #966, should be #962
    975: (971, "関連", 208),   # page_208 parsed 関連 as #975, should be #971
}

# Correct entries that were overwritten — where to find them in raw JSON
CORRECT_AT_WRONG = {
    584: (123, "栽培"),
    589: (124, "所有"),
    656: (137, "増大"),
    657: (137, "増量"),
    658: (137, "増税"),
    659: (137, "増員"),
    660: (137, "減点"),
    966: (208, "分野"),
    975: (209, "付属"),
}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def index_by(entries, key="index"):
    return {e[key]: e for e in entries}


def find_unit_for_index(db_entries, target_idx):
    sorted_entries = sorted(db_entries, key=lambda e: e["index"])
    for i, e in enumerate(sorted_entries):
        if e["index"] == target_idx:
            return e["unit"]
        if e["index"] > target_idx:
            if i > 0:
                return sorted_entries[i - 1]["unit"]
            break
    for e in reversed(sorted_entries):
        if e["index"] < target_idx:
            return e["unit"]
    return {"number": 1, "header": "Unit 01"}


def extract_reading_from_raw_text(raw_text, target_index):
    pattern = rf"^{target_index}\s+([あ-ん]+)\s+"
    m = re.search(pattern, raw_text, re.MULTILINE)
    return m.group(1) if m else None


def get_raw_entry(page_num, number_or_kanji=None, number=None, kanji=None):
    """Get a raw entry from a page by number or kanji match."""
    page_file = os.path.join(JSON_DIR, f"page_{page_num:03d}.json")
    if not os.path.exists(page_file):
        return None, None
    page = load_json(page_file)
    if "entries" not in page:
        return None, None
    for e in page["entries"]:
        if number is not None and e.get("number") == number:
            return e, page
        if kanji is not None and kanji in e.get("kanji", ""):
            return e, page
    return None, page


def raw_entry_to_combined(idx, raw_entry, unit_info, correct_reading=None):
    reading = correct_reading or raw_entry.get("reading", "")
    return {
        "index": idx,
        "unit": unit_info,
        "reading": reading,
        "kanji": raw_entry.get("kanji", ""),
        "headword_text": raw_entry.get("kanji", ""),
        "verb_pattern": raw_entry.get("verb_pattern"),
        "meaning_en": raw_entry.get("meaning_en", ""),
        "meaning_zh": raw_entry.get("meaning_zh", ""),
        "sentence": raw_entry["examples"][0] if raw_entry.get("examples") else "",
        "examples": raw_entry.get("examples", []),
        "word_clip": f"output/clips/unit{unit_info['number']:02d}/word{idx}.mp3",
        "sentence_clip": f"output/clips/unit{unit_info['number']:02d}/sentence{idx}.mp3",
        "explanation": None,
    }


def main():
    db_entries = load_json(DB_PATH)
    combined_entries = load_json(COMBINED_PATH)

    db_by_idx = index_by(db_entries)
    combined_by_idx = index_by(combined_entries)

    # Load all pages for raw entry access
    all_pages = {}
    for f in sorted(glob.glob(os.path.join(JSON_DIR, "page_*.json"))):
        page = load_json(f)
        all_pages[page["page"]] = page

    wrong_indices = set(MISNUMBERED.keys())
    all_indices = sorted(set(list(db_by_idx.keys()) + list(combined_by_idx.keys())))
    max_idx = max(all_indices)
    full_range = set(range(1, max_idx + 1))

    # --- STEP 1: Normal combine, excluding wrong-numbered indices ---
    merged = {}
    both_sources = 0
    db_only = 0
    combined_only = 0

    for idx in all_indices:
        if idx in wrong_indices:
            continue  # Skip — will be restored from raw JSON

        in_db = idx in db_by_idx
        in_combined = idx in combined_by_idx

        if in_db and in_combined:
            both_sources += 1
            entry = dict(db_by_idx[idx])
            entry["examples"] = combined_by_idx[idx].get("examples", [])
        elif in_db:
            db_only += 1
            entry = dict(db_by_idx[idx])
        else:
            combined_only += 1
            entry = dict(combined_by_idx[idx])

        merged[idx] = entry

    # --- STEP 2: Restore correct entries at overwritten indices ---
    restored_correct = []
    for wrong_idx, (correct_page, correct_kanji) in CORRECT_AT_WRONG.items():
        raw_entry, page = get_raw_entry(correct_page, number=wrong_idx)
        if raw_entry:
            unit = find_unit_for_index(db_entries, wrong_idx)
            entry = raw_entry_to_combined(wrong_idx, raw_entry, unit)
            merged[wrong_idx] = entry
            restored_correct.append(entry)
            print(f"  Restored correct entry #{wrong_idx}: {entry['kanji']} ({entry['reading']})")
        else:
            print(f"  WARNING: Could not find correct entry #{wrong_idx} ({correct_kanji}) on page {correct_page}")

    # --- STEP 3: Move misnumbered entries + their DB data to correct indices ---
    restored_misnumbered = []
    for wrong_idx, (correct_idx, kanji, source_page) in MISNUMBERED.items():
        raw_entry, page = get_raw_entry(source_page, kanji=kanji)
        if not raw_entry:
            print(f"  WARNING: Could not find misnumbered entry {wrong_idx}->{correct_idx} ({kanji}) on page {source_page}")
            continue

        correct_reading = extract_reading_from_raw_text(page.get("raw_text", ""), correct_idx)
        unit = find_unit_for_index(db_entries, correct_idx)
        entry = raw_entry_to_combined(correct_idx, raw_entry, unit, correct_reading)

        # Transfer explanation and clip paths from the wrong index in the DB
        if wrong_idx in db_by_idx:
            wrong_db = db_by_idx[wrong_idx]
            entry["explanation"] = wrong_db.get("explanation")
            entry["word_clip"] = wrong_db.get("word_clip", entry["word_clip"])
            entry["sentence_clip"] = wrong_db.get("sentence_clip", entry["sentence_clip"])

        # Transfer examples from the wrong index in the combined file
        if wrong_idx in combined_by_idx:
            entry["examples"] = combined_by_idx[wrong_idx].get("examples", entry["examples"])

        merged[correct_idx] = entry
        restored_misnumbered.append(entry)
        print(f"  Moved misnumbered entry: {entry['kanji']} ({entry['reading']}) #{wrong_idx} -> #{correct_idx}")

    # --- STEP 4: Positional null entries ---
    restored_positional = []

    # Page 38: null entry after 170 -> index 171
    page38 = all_pages.get(38)
    if page38:
        for i, e in enumerate(page38["entries"]):
            if e.get("number") is None and i > 0 and page38["entries"][i - 1].get("number") == 170:
                unit = find_unit_for_index(db_entries, 171)
                entry = raw_entry_to_combined(171, e, unit)
                merged[171] = entry
                restored_positional.append(entry)
                break

    # Page 162: null entry between 760 and 762 -> index 761
    page162 = all_pages.get(162)
    if page162:
        for i, e in enumerate(page162["entries"]):
            if e.get("number") is None:
                prev = page162["entries"][i - 1].get("number") if i > 0 else None
                nxt = page162["entries"][i + 1].get("number") if i + 1 < len(page162["entries"]) else None
                if prev == 760 and nxt == 762:
                    unit = find_unit_for_index(db_entries, 761)
                    entry = raw_entry_to_combined(761, e, unit)
                    merged[761] = entry
                    restored_positional.append(entry)
                    break

    # Page 139: 6 null entries -> indices 670-675
    page139 = all_pages.get(139)
    if page139:
        null_count = 0
        for i, e in enumerate(page139["entries"]):
            if e.get("number") is None:
                idx = 670 + null_count
                correct_reading = extract_reading_from_raw_text(page139.get("raw_text", ""), idx)
                unit = find_unit_for_index(db_entries, idx)
                entry = raw_entry_to_combined(idx, e, unit, correct_reading)
                merged[idx] = entry
                restored_positional.append(entry)
                null_count += 1

    # Sort and deduplicate (merged is a dict so last write wins — no dups)
    final_list = [merged[k] for k in sorted(merged.keys())]

    # Compute truly missing
    final_indices = set(merged.keys())
    truly_missing = sorted(full_range - final_indices)

    # --- Write output ---
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(final_list, f, ensure_ascii=False, indent=2)

    all_restored = restored_correct + restored_misnumbered + restored_positional
    with open(RESTORED_PATH, "w", encoding="utf-8") as f:
        json.dump(all_restored, f, ensure_ascii=False, indent=2)

    # --- Report ---
    print()
    print("=" * 60)
    print("VOCABULARY COMBINATION REPORT")
    print("=" * 60)
    print(f"Total entries in vocabulary_db.json:       {len(db_entries)}")
    print(f"Total entries in vocabulary_combined.json:  {len(combined_entries)}")
    print(f"Total entries in combined_final.json:       {len(final_list)}")
    print()
    print("Normal merge (existing correct entries):")
    print(f"  Both sources (explanation from db + examples from combined): {both_sources}")
    print(f"  Only in vocabulary_db.json:                                  {db_only}")
    print(f"  Only in vocabulary_combined.json:                            {combined_only}")
    print()
    print(f"Restored correct entries (overwritten by misnumbered): {len(restored_correct)}")
    for r in restored_correct:
        print(f"  #{r['index']}: {r['kanji']} ({r['reading']})")
    print()
    print(f"Moved misnumbered entries to correct indices: {len(restored_misnumbered)}")
    for r in restored_misnumbered:
        orig_wrong = None
        for w, (c, k, p) in MISNUMBERED.items():
            if c == r["index"]:
                orig_wrong = w
                break
        print(f"  {r['kanji']} ({r['reading']}): #{orig_wrong} -> #{r['index']}")
    print()
    print(f"Positional null entries restored: {len(restored_positional)}")
    for r in restored_positional:
        print(f"  #{r['index']}: {r['kanji']} ({r['reading']})")
    print()
    if truly_missing:
        print(f"Indices STILL missing from all sources ({len(truly_missing)}):")
        print(f"  {truly_missing}")
    else:
        print("All indices 1-{} accounted for!".format(max_idx))
    print()
    print("=" * 60)
    print(f"Output: {OUTPUT_PATH}")
    print(f"Restored entries: {RESTORED_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
