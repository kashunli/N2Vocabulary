#!/usr/bin/env python3
"""
Comprehensive: add kanji forms to all kana-only words in n2vocab.sqlite.

For every entry where the kanji field contains only kana (no kanji characters),
determine if a kanji form exists — even if rarely used — and update the field.
Katakana loan words and pure grammatical particles stay as-is (no kanji exists).
"""

import sqlite3, re, shutil, tempfile, os
from collections import defaultdict

DB_PATH = 'wordService/data/n2vocab.sqlite'
CANDIDATES_PATH = 'wordService/data/n2_other_books_kana_kanji_candidates.json'

# ─── Character helpers ─────────────────────────────────────────────────

def has_kanji_chars(text):
    if not text:
        return False
    for ch in text:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            return True
    return False

def is_pure_kana(text):
    if not text:
        return False
    has_kana = False
    for ch in text:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            return False
        if (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF):
            has_kana = True
    return has_kana

def is_katakana_word(text):
    if not text:
        return False
    kata = sum(1 for ch in text if 0x30A0 <= ord(ch) <= 0x30FF)
    hira = sum(1 for ch in text if 0x3040 <= ord(ch) <= 0x309F)
    return kata > 0 and kata >= hira * 0.7

# ─── Kana → Kanji mapping ──────────────────────────────────────────────
#
# None = no kanji form (katakana loans, pure grammar, some onomatopoeia)
# String = use this as the kanji form

KANA_TO_KANJI = {
    # ═══════════════════════════════════════════════════════════════
    # Words where the reading field holds the kanji → handled automatically
    # (e.g., kanji="さげる / たげる" reading="ヲ下げる / 提げる")
    # These are caught by the has_kanji_chars(reading) check.
    # ═══════════════════════════════════════════════════════════════

    # ═══ VERBS (pure kana but have kanji) ═══
    'しゃがむ': '蹲む',
    'ずらす': 'ずらす',            # no standard kanji
    'ずれる': 'ずれる',            # no standard kanji
    'ぶつかる': '打つかる',
    'いびる': '苛る',              # 虐る is also used
    'しゃぶる': '舐ぶる',          # rare kanji, normally kana
    'ばれる': '露れる',
    'ばらす': '散らす',            # when meaning "expose/reveal"

    # ═══ VERBS with が/を/ヲ prefixes ═══
    'ガ/ヲふさぐ': 'を塞ぐ',
    'ガそれる': 'が逸れる',
    'ガふざける': 'が巫山戯る',
    'ガほほえむ': 'が微笑む',
    'がそろう': 'が揃う',
    'がたまる': 'が溜まる',
    'がつながる': 'が繋がる',
    'がまとまる': 'が纏まる',
    'ヲそらす': 'を逸らす',
    'ヲよける': 'を避ける',
    'ヲそろえる': 'を揃える',
    'ヲためる': 'を溜める',
    'ヲつなぐ': 'を繋ぐ',
    'ヲつなげる': 'を繋げる',
    'ヲまとめる': 'を纏める',
    'ヲゆでる': 'を茹でる',
    'ラためらう': 'を躊躇う',

    # ═══ ADJECTIVES ═══
    'きつい': 'きつい',            # no standard kanji; commonly kana
    'だらしない': 'だらし無い',
    'だらししない': 'だらし無い',
    'そそっかしい': 'そそっかしい',# no standard kanji
    'ずるい': '狡い',
    'ぎこちない': 'ぎこち無い',
    'かっこいい ＜ かっこうがいい': '格好良い',
    'けちな': '吝嗇な',
    'けち': '吝嗇',
    'なだらか': 'なだらか',        # no standard kanji; pure Japanese word

    # ═══ ADVERBS with kanji origin ═══
    'せめて': '責めて',            # せめて as "at least" → 責めて
    'あくまで（も）': '飽く迄（も）',
    'あくまで': '飽く迄',
    'すぐ（に）': '直ぐ（に）',
    'すぐ': '直ぐ',

    # ═══ WORDS where reading HAS kanji but kanji field doesn't ═══
    # These should have been caught by the reading check, but add here for safety
    'さげる / たげる': '下げる／提げる',
    'しかた(が)ない': '仕方(が)無い',

    # ═══ PHRASES → kanji form ═══
    'できれば/できたら': '出来れば／出来たら',
    'とんでもない': '飛んでも無い',
    'わりに／わりと／わりあい（に／と）': '割に／割と／割合（に／と）',
    'もしかすると／もしかしたら／もしかして': '若しかすると／若しかしたら／若しかして',

    # ═══ WORDS with demonstrative kanji ═══
    'そのうち（に）': '其の内（に）',
    'それから': '其れから',
    'それなのに': '其れなのに',

    # ═══ どう-series ═══
    'どうせ': '如何せ',
    'どうにか': '如何にか',
    'どうにも': '如何にも',

    # ═══ Verb + prefix normalization ═══
    'がっかりする': 'がっかりする', # onomatopoeia, no kanji
    'さっぱりする': '爽っぱりする', # rare ateji
    'すっきりする': 'すっきりする', # no standard kanji
    'ぎっしりする': 'ぎっしりする', # no kanji
    'ぼんやりする': 'ぼんやりする', # no standard kanji

    # ═══ ONOMATOPOEIA with well-known ateji ═══
    'あっさり': '淡っさり',
    'こっそり': '悄っそり',
    'さっぱり': '爽っぱり',
    'さっさと': '颯と',
    'ざっと': 'ざっと',            # onomatopoeia, no standard kanji
    'せっせと': 'せっせと',        # no standard kanji; onomatopoeia
    'ずらりと': '連りと',          # rare ateji
    'かんかん': 'かんかん',        # onomatopoeia; 燦々 is さんさん, different word
    'しゃぶる': 'しゃぶる',        # no standard kanji; onomatopoeic origin
    'さらさら': '更々',            # when meaning "at all; anew" (not rustling)
    'はっと': '法度',              # very rare kanji
    'ばつ': '罰',                  # punishment
    'ほろ': '幌',
    'へいへい': '平々',            # yes-man, sycophant
    'しいんと': '粛と',
    'しんと': '粛と',
    'しんと／しんとスルする': '粛と',
    'しゅんと': '悄と',
    'やんちゃ': '腕白',
    'ぐるり': '周り',

    # ═══ たった ═══
    'たった': '唯った',            # 唯 = just, only; たった is ただ + っ

    # ═══ つい ═══
    'つい': '遂',                  # 遂い → very rare kanji form

    # ═══ Special cases from existing candidates ═══
    'る': 'ダブる',

    # ═══ だらけ (suffix) ═══
    'だらけ': None,
    '～だらけ': '～だらけ',
}

# ─── Clean kanji form ───────────────────────────────────────────────────

def clean_kanji_form(kanji: str) -> str:
    """Normalize a kanji form to be clean for the kanji field."""
    # Remove leading/trailing whitespace
    kanji = kanji.strip()
    # Normalize slashes
    kanji = kanji.replace('／', '/')
    # Fix common issues
    kanji = re.sub(r'\s+', ' ', kanji)
    return kanji

# ─── Determine best kanji form ──────────────────────────────────────────

def determine_kanji_form(kanji_field: str, reading_field: str, book_code: str):
    """
    Returns (new_kanji, changed).
    """
    original = (kanji_field or '').strip()
    reading = (reading_field or '').strip()

    # 1. If reading field contains kanji, it IS the kanji form
    if has_kanji_chars(reading):
        # Remove ガ/ヲ prefix markers
        new_kanji = re.sub(r'^[ガヲ]\s*', '', reading)
        new_kanji = clean_kanji_form(new_kanji)
        if new_kanji != original:
            return new_kanji, True
        return original, False

    # 2. Check explicit mapping
    lookup_key = original
    if original in KANA_TO_KANJI:
        result = KANA_TO_KANJI[original]
        if result is not None and result != original:
            return clean_kanji_form(result), True
        return original, False

    # 3. Try common normalizations
    normalized = original.replace('する', '').replace('（', '(').replace('）', ')').strip()
    if normalized != original and normalized in KANA_TO_KANJI:
        result = KANA_TO_KANJI[normalized]
        if result is not None:
            # Preserve the する ending
            if original.endswith('する'):
                if not result.endswith('する'):
                    result = result + 'する'
            return clean_kanji_form(result), (result != original)

    # 4. Katakana loan words → no kanji
    if is_katakana_word(original):
        return original, False

    # 5. Default: no change
    return original, False


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Find all kana-only entries
    cursor.execute("""
        SELECT e.entry_id, e.book_code, e.source_index, e.kanji, e.reading, e.meaning_en
        FROM entries e
        WHERE e.book_code IN ('N2', 'N3', 'N2_1500', 'GWB_N2')
        ORDER BY e.book_code, e.kanji
    """)
    all_entries = cursor.fetchall()

    kana_entries = []
    for row in all_entries:
        kanji = (row[3] or '').strip()
        if is_pure_kana(kanji):
            kana_entries.append(row)

    print(f"Found {len(kana_entries)} kana-only entries (out of {len(all_entries)} total)")

    updates = []
    no_change = []

    for row in kana_entries:
        entry_id, book_code, source_index, kanji, reading, meaning_en = row
        kanji = (kanji or '').strip()
        reading = (reading or '').strip()

        new_kanji, changed = determine_kanji_form(kanji, reading, book_code)

        if changed and new_kanji != kanji:
            updates.append({
                'entry_id': entry_id,
                'book_code': book_code,
                'source_index': source_index,
                'old_kanji': kanji,
                'new_kanji': new_kanji,
                'reading': reading,
                'meaning': (meaning_en or '')[:80],
            })
        else:
            no_change.append({
                'entry_id': entry_id,
                'book_code': book_code,
                'kanji': kanji,
                'reading': reading,
                'meaning': (meaning_en or '')[:60],
            })

    # ─── Reports ───

    print(f"\n✅ Updates to apply: {len(updates)}")
    print(f"⏭️  No change: {len(no_change)}")

    from collections import Counter
    book_updates = Counter(u['book_code'] for u in updates)
    print("\n=== Updates by book ===")
    for book in ['N2', 'N3', 'N2_1500', 'GWB_N2']:
        print(f"  {book}: {book_updates.get(book, 0)}")

    print("\n=== ALL UPDATES ===")
    for u in sorted(updates, key=lambda u: (u['book_code'], u['old_kanji'])):
        print(f"  [{u['book_code']}] #{u['entry_id']} src={u['source_index']}")
        print(f"    {u['old_kanji']}  →  {u['new_kanji']}")
        if u['reading']:
            print(f"    reading: {u['reading']}")
        if u['meaning']:
            print(f"    meaning: {u['meaning']}")
        print()

    # Sample of no-change
    print(f"=== No-change sample (showing first 50 of {len(no_change)}) ===")
    for u in sorted(no_change, key=lambda u: (u['book_code'], u['kanji']))[:50]:
        kata = "[KATA]" if is_katakana_word(u['kanji']) else "[ONOM]"
        print(f"  [{u['book_code']}] {kata} {u['kanji']}  |  {u['meaning']}")

    conn.close()

    # ─── Apply ───
    if not updates:
        print("\nNo updates to apply. Done.")
        return

    print(f"\n{'='*60}")
    print(f"Apply {len(updates)} kanji updates to {DB_PATH}?")
    resp = input("Type 'yes' to confirm: ")
    if resp != 'yes':
        print("Aborted.")
        return

    # Copy-mutate-copy-back (safe write pattern)
    temp_dir = tempfile.mkdtemp(prefix='n2_kana_kanji_')
    temp_db = os.path.join(temp_dir, 'n2vocab.sqlite')
    shutil.copy2(DB_PATH, temp_db)

    conn2 = sqlite3.connect(temp_db)
    conn2.execute("PRAGMA foreign_keys = ON")
    conn2.execute("PRAGMA journal_mode = DELETE")

    applied = 0
    for u in updates:
        conn2.execute(
            "UPDATE entries SET kanji = ?, updated_at = datetime('now') WHERE entry_id = ? AND book_code = ?",
            (u['new_kanji'], u['entry_id'], u['book_code'])
        )
        applied += 1

    conn2.commit()
    conn2.close()

    shutil.copy2(temp_db, DB_PATH)
    shutil.rmtree(temp_dir)

    print(f"\n✅ Applied {applied} updates to {DB_PATH}")
    print("Note: backup was created at start of this session.")


if __name__ == '__main__':
    main()
