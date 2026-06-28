"""Add the image-reviewed mimetic/adverb batch to the N2_1500 book.

The app has books and units, but no separate tag table. This workflow uses a
dedicated N2_1500 unit as the visible tag so the whole image batch can be
selected together. Existing N2_1500 rows are moved into that unit; missing rows
are appended with source indexes after the current N2_1500 maximum.
"""

from __future__ import annotations

import argparse
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path


DB_PATH = Path("data/n2vocab.sqlite")
BOOK_CODE = "N2_1500"
TAG_UNIT_NUMBER = 10
TAG_HEADER = "Tag 01 拟声拟态词"
TAG_TITLE = "拟声拟态词"


@dataclass(frozen=True)
class Candidate:
    row: int
    reading: str
    word: str
    meaning_en: str
    meaning_zh: str


CANDIDATES = [
    Candidate(1, "こつこつ", "こつこつ", "steadily; persistently; tapping sound", "不懈努力，孜孜不倦；轻敲声"),
    Candidate(2, "くるくる", "くるくる", "spinning; coiling; briskly; constantly changing", "滴溜溜地转；勤快；一层层、一圈圈地缠绕"),
    Candidate(3, "あたふた", "あたふた", "in a panic; flustered", "慌忙，慌张失措"),
    Candidate(4, "すべすべ", "すべすべ", "smooth; silky", "光滑，滑溜；柔软光洁"),
    Candidate(5, "ざらざら", "ざらざら", "rough; gritty; rustling or rattling", "粗糙，不光滑；沙沙声，刷啦刷啦声"),
    Candidate(6, "そわそわ", "そわそわ", "restless; fidgety", "不镇静，坐立不安，心神不定"),
    Candidate(7, "ひしひし", "ひしひし", "keenly; deeply; pressingly", "深切地，强烈地；紧迫地"),
    Candidate(8, "ねばねば", "ねばねば", "sticky; gooey", "黏黏糊糊，发黏"),
    Candidate(9, "さらさら", "さらさら", "smoothly; fluently; rustling; dry and fresh", "沙沙；流利地，顺畅地；干燥清爽"),
    Candidate(10, "ぶらぶら", "ぶらぶら", "idly; strolling; dangling; swaying", "摇晃；闲逛；无所事事"),
    Candidate(11, "ぶかぶか", "ぶかぶか", "baggy; loose-fitting", "肥大，不合身"),
    Candidate(12, "うろうろ", "うろうろ", "wandering; pacing around; being flustered", "徘徊，转来转去；心神不安"),
    Candidate(13, "せかせか", "せかせか", "hurriedly; restlessly", "急急忙忙，慌慌张张"),
    Candidate(14, "のろのろ", "のろのろ", "slowly; sluggishly", "慢吞吞，迟缓"),
    Candidate(15, "まちまち", "まちまち", "varied; diverse; different", "各不相同，形形色色"),
    Candidate(16, "おどおど", "おどおど", "timidly; nervously", "提心吊胆，怯生生，慌张不安"),
    Candidate(17, "まるまる", "丸々", "completely; entirely; plump and round", "全部；整整，完全；圆滚滚"),
    Candidate(18, "めきめき", "めきめき", "rapidly; remarkably", "显著，迅速"),
    Candidate(19, "ぐずぐず", "愚図愚図", "dawdling; grumbling; hesitating", "磨蹭，拖延；嘟囔，唠叨"),
    Candidate(20, "てきぱき", "てきぱき", "briskly; efficiently", "麻利，利落，敏捷"),
    Candidate(21, "すいすい", "すいすい", "smoothly; swiftly; easily", "轻快顺利地；流利地"),
    Candidate(22, "くよくよ", "くよくよ", "worrying; brooding", "担心，想不开，闷闷不乐"),
    Candidate(23, "めそめそ", "めそめそ", "sobbing; whimpering", "低声抽泣，爱哭"),
    Candidate(24, "びくびく", "びくびく", "trembling with fear; nervously", "害怕，发抖；提心吊胆"),
    Candidate(25, "どきどき", "どきどき", "pounding; throbbing; nervous", "心七上八下，忐忑不安"),
    Candidate(26, "じめじめ", "じめじめ", "damp; gloomy", "潮湿；阴郁，忧郁"),
    Candidate(27, "すくすく", "すくすく", "growing quickly and healthily", "茁壮成长"),
    Candidate(28, "ごろごろ", "ごろごろ", "rumbling; rolling; lying around; everywhere", "咕噜咕噜滚动；到处都是；闲着；轰隆声"),
    Candidate(29, "はらはら", "はらはら", "fluttering down; nervous; anxious", "静静落下；担心，忧虑；头发散乱"),
    Candidate(30, "だらだら", "だらだら", "dragging on; dripping; lazily", "滴滴答答地；冗长；磨蹭"),
    Candidate(31, "うずうず", "うずうず", "itching to do something; restless", "心里发痒，坐立不安"),
    Candidate(32, "ぎくしゃく", "ぎくしゃく", "awkward; jerky; strained", "不圆滑，不灵活，生硬"),
    Candidate(33, "ぺこぺこ", "ぺこぺこ", "hungry; bowing and scraping", "肚子饿；点头哈腰，谄媚"),
    Candidate(34, "にこにこ", "にこにこ", "smiling", "笑嘻嘻，微微笑"),
    Candidate(35, "ありあり", "ありあり", "vividly; clearly", "活现，清楚，明明白白"),
    Candidate(36, "へとへと", "へとへと", "exhausted; worn out", "非常疲惫，筋疲力尽"),
    Candidate(37, "ゆっくり", "ゆっくり", "slowly; leisurely; comfortably", "慢慢，不着急；舒适，充分"),
    Candidate(38, "そっくり", "そっくり", "exactly alike; entirely", "完全，全部；一模一样"),
    Candidate(39, "ぴったり", "ぴったり", "exactly; snugly; perfectly", "紧密；恰好；完全一致"),
    Candidate(40, "びっくり", "びっくり", "surprised; startled", "吓一跳，受惊"),
    Candidate(41, "さっぱり", "さっぱり", "refreshing; frank; completely not", "整洁；爽快；清淡；完全不"),
    Candidate(42, "めっきり", "めっきり", "markedly; suddenly", "显著，急剧"),
    Candidate(43, "がっしり", "がっしり", "solidly built; sturdy", "粗壮，健壮；结实"),
    Candidate(44, "まるきり", "丸切り", "completely; utterly, usually negative", "完全不，简直"),
    Candidate(45, "がっかり", "がっかり", "disappointed; dejected", "失望，灰心丧气；筋疲力竭"),
    Candidate(46, "すっかり", "すっかり", "completely; entirely", "全部，完全"),
    Candidate(47, "しっかり", "確り", "firmly; reliably; properly", "稳固；认真；可靠；扎实"),
    Candidate(48, "ぐっすり", "ぐっすり", "sound asleep", "酣睡，熟睡；完全地"),
    Candidate(49, "げっそり", "げっそり", "haggard; dispirited", "急剧消瘦；失望，无精打采"),
    Candidate(50, "たっぷり", "たっぷり", "plenty; fully", "充分，足够，多"),
    Candidate(51, "びっしょり", "びっしょり", "soaked; drenched", "湿透"),
    Candidate(52, "じっくり", "じっくり", "carefully; thoroughly; patiently", "慢慢地；仔细地；踏踏实实"),
    Candidate(53, "すんなり", "すんなり", "smoothly; easily; slenderly", "顺利，容易；苗条，柔软"),
    Candidate(54, "ぐったり", "ぐったり", "exhausted; limp", "精疲力尽，十分疲乏"),
    Candidate(55, "こっそり", "こっそり", "secretly; stealthily", "悄悄地，偷偷地"),
    Candidate(56, "すっきり", "すっきり", "refreshed; neat; clear; relieved", "清爽；畅快；整洁；痛快"),
    Candidate(57, "くっきり", "くっきり", "distinctly; clearly", "鲜明，清楚"),
    Candidate(58, "あっさり", "あっさり", "plainly; lightly; easily; frankly", "清淡；坦率；简单；轻易"),
    Candidate(59, "はっきり", "はっきり", "clearly; plainly; definitely", "清楚，明确；爽快"),
    Candidate(60, "うんざり", "うんざり", "fed up; disgusted", "厌烦，索然无味"),
    Candidate(61, "ぱっちり", "ぱっちり", "wide-eyed; bright-eyed", "眼睛又大又亮"),
    Candidate(62, "ばっちり", "バッチリ", "perfectly; successfully; just right", "完美地，充分地，顺利地；正好"),
    Candidate(63, "きっかり", "きっかり", "exactly; precisely; on time", "正好，整；准时"),
    Candidate(64, "てっきり", "てっきり", "surely; with no doubt; mistakenly assuming", "一定，以为无疑"),
    Candidate(65, "きっぱり", "きっぱり", "decisively; flatly; clearly", "断然，明确"),
    Candidate(66, "ぎっしり", "ぎっしり", "tightly packed; crammed", "满满的，挤得满满的"),
    Candidate(67, "うっかり", "うっかり", "carelessly; inadvertently; absentmindedly", "不注意，不留神；无意中；茫然"),
    Candidate(68, "からから", "からから", "bone-dry; rattling; empty; laughing loudly", "哗啦，哈哈；干透，空空"),
    Candidate(69, "がらがら", "がらがら", "rattling; rumbling; empty; uncrowded; hoarse", "轰隆；哗啦；粗鲁；人少，空荡荡"),
]


def make_uuid(candidate: Candidate) -> str:
    name = f"wordService:{BOOK_CODE}:mimetic-batch:{candidate.row}:{candidate.reading}:{candidate.word}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def find_existing_n2_1500(cur: sqlite3.Cursor, candidate: Candidate) -> sqlite3.Row | None:
    return cur.execute(
        """
        SELECT entry_id, source_index, unit_number, position, kanji, reading
        FROM entries
        WHERE book_code = ?
          AND (kanji IN (?, ?) OR reading IN (?, ?))
        ORDER BY source_index
        LIMIT 1
        """,
        (BOOK_CODE, candidate.reading, candidate.word, candidate.reading, candidate.word),
    ).fetchone()


def run(apply: bool) -> None:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    try:
        cur.execute("PRAGMA foreign_keys = ON")
        max_source_index = cur.execute(
            "SELECT COALESCE(MAX(source_index), 0) FROM entries WHERE book_code = ?",
            (BOOK_CODE,),
        ).fetchone()[0]
        next_source_index = max_source_index + 1

        moves: list[tuple[Candidate, sqlite3.Row]] = []
        inserts: list[tuple[Candidate, int]] = []
        seen_existing: set[int] = set()

        for candidate in CANDIDATES:
            existing = find_existing_n2_1500(cur, candidate)
            if existing is not None:
                if existing["entry_id"] in seen_existing:
                    raise RuntimeError(f"duplicate candidate maps to entry_id {existing['entry_id']}")
                seen_existing.add(existing["entry_id"])
                moves.append((candidate, existing))
                continue
            inserts.append((candidate, next_source_index))
            next_source_index += 1

        print(f"candidates={len(CANDIDATES)}")
        print(f"existing_moved_into_tag={len(moves)}")
        print(f"missing_inserted={len(inserts)}")
        print(f"target_unit={TAG_UNIT_NUMBER} {TAG_TITLE}")
        if not apply:
            for candidate, existing in moves:
                print(
                    "MOVE",
                    candidate.row,
                    existing["source_index"],
                    existing["kanji"],
                    existing["reading"],
                    f"unit {existing['unit_number']} -> {TAG_UNIT_NUMBER}",
                )
            for candidate, source_index in inserts[:10]:
                print("INSERT", candidate.row, source_index, candidate.word, candidate.reading)
            if len(inserts) > 10:
                print(f"... {len(inserts) - 10} more inserts")
            print("dry_run=True")
            return

        cur.execute(
            """
            INSERT INTO units(book_code, number, header, title)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(book_code, number) DO UPDATE SET
              header = excluded.header,
              title = excluded.title
            """,
            (BOOK_CODE, TAG_UNIT_NUMBER, TAG_HEADER, TAG_TITLE),
        )

        for candidate, existing in moves:
            cur.execute(
                """
                UPDATE entries
                SET unit_number = ?,
                    position = ?,
                    meaning_en = ?,
                    meaning_zh = ?,
                    explanation_md = '',
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE entry_id = ?
                """,
                (
                    TAG_UNIT_NUMBER,
                    candidate.row,
                    candidate.meaning_en,
                    candidate.meaning_zh,
                    existing["entry_id"],
                ),
            )

        for candidate, source_index in inserts:
            cur.execute(
                """
                INSERT INTO entries(
                  uuid, book_code, unit_number, source_index, position,
                  kanji, reading, verb_pattern, meaning_en, meaning_zh,
                  sentence, explanation_md, word_clip, sentence_clip
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, '', '', NULL, NULL)
                """,
                (
                    make_uuid(candidate),
                    BOOK_CODE,
                    TAG_UNIT_NUMBER,
                    source_index,
                    candidate.row,
                    candidate.word,
                    candidate.reading,
                    candidate.meaning_en,
                    candidate.meaning_zh,
                ),
            )

        cur.execute(
            """
            UPDATE entry_examples
            SET explanation_md = ''
            WHERE entry_id IN (
              SELECT entry_id
              FROM entries
              WHERE book_code = ? AND unit_number = ?
            )
            """,
            (BOOK_CODE, TAG_UNIT_NUMBER),
        )

        tag_count = cur.execute(
            "SELECT COUNT(*) FROM entries WHERE book_code = ? AND unit_number = ?",
            (BOOK_CODE, TAG_UNIT_NUMBER),
        ).fetchone()[0]
        if tag_count != len(CANDIDATES):
            raise RuntimeError(f"tag unit has {tag_count} rows, expected {len(CANDIDATES)}")

        explanation_count = cur.execute(
            """
            SELECT COUNT(*)
            FROM entries
            WHERE book_code = ? AND unit_number = ?
              AND trim(coalesce(explanation_md, '')) <> ''
            """,
            (BOOK_CODE, TAG_UNIT_NUMBER),
        ).fetchone()[0]
        if explanation_count:
            raise RuntimeError(f"tag unit still has {explanation_count} entry explanations")

        example_explanation_count = cur.execute(
            """
            SELECT COUNT(*)
            FROM entry_examples ex
            JOIN entries e ON e.entry_id = ex.entry_id
            WHERE e.book_code = ? AND e.unit_number = ?
              AND trim(coalesce(ex.explanation_md, '')) <> ''
            """,
            (BOOK_CODE, TAG_UNIT_NUMBER),
        ).fetchone()[0]
        if example_explanation_count:
            raise RuntimeError(
                f"tag unit still has {example_explanation_count} example explanations"
            )

        english_count = cur.execute(
            """
            SELECT COUNT(*)
            FROM entries
            WHERE book_code = ? AND unit_number = ?
              AND trim(coalesce(meaning_en, '')) <> ''
            """,
            (BOOK_CODE, TAG_UNIT_NUMBER),
        ).fetchone()[0]
        if english_count != len(CANDIDATES):
            raise RuntimeError(f"tag unit has {english_count} English meanings")

        integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_errors = cur.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok":
            raise RuntimeError(f"integrity_check failed: {integrity}")
        if foreign_key_errors:
            raise RuntimeError(f"foreign_key_check failed: {foreign_key_errors[:3]}")

        con.commit()
        print("apply=True")
        print(f"tag_count={tag_count}")
        print(f"entry_explanations={explanation_count}")
        print(f"example_explanations={example_explanation_count}")
        print(f"english_meanings={english_count}")
        print(f"new_source_index_range={inserts[0][1] if inserts else 'none'}-{inserts[-1][1] if inserts else 'none'}")
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes to the SQLite database")
    args = parser.parse_args()
    run(apply=args.apply)


if __name__ == "__main__":
    main()
