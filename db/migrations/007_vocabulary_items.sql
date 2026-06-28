-- 007_vocabulary_items.sql - canonical vocabulary items plus book placements.
--
-- This is a compatibility-first migration. The old book-scoped tables remain
-- in place, while new item tables become the schema authority for shared
-- examples, related terms, audio, and study state.

CREATE TABLE IF NOT EXISTS vocabulary_items (
  item_id        INTEGER PRIMARY KEY,
  uuid           TEXT NOT NULL UNIQUE,
  kanji          TEXT NOT NULL,
  reading        TEXT,
  verb_pattern   TEXT,
  meaning_en     TEXT,
  meaning_zh     TEXT,
  explanation_md TEXT,
  word_clip      TEXT,
  created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (kanji, reading)
);

CREATE TABLE IF NOT EXISTS book_entries (
  entry_id       INTEGER PRIMARY KEY,
  item_id        INTEGER NOT NULL REFERENCES vocabulary_items(item_id) ON DELETE CASCADE,
  uuid           TEXT NOT NULL UNIQUE,
  book_code      TEXT NOT NULL REFERENCES books(code) ON DELETE CASCADE,
  unit_number    INTEGER NOT NULL,
  source_index   INTEGER NOT NULL,
  position       INTEGER NOT NULL,
  sentence       TEXT,
  explanation_md TEXT,
  sentence_clip  TEXT,
  created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (book_code, source_index),
  FOREIGN KEY (book_code, unit_number) REFERENCES units(book_code, number)
);

CREATE INDEX IF NOT EXISTS idx_book_entries_book_unit
  ON book_entries(book_code, unit_number, position, source_index);
CREATE INDEX IF NOT EXISTS idx_book_entries_item
  ON book_entries(item_id);

CREATE TABLE IF NOT EXISTS item_examples (
  item_id        INTEGER NOT NULL REFERENCES vocabulary_items(item_id) ON DELETE CASCADE,
  position       INTEGER NOT NULL,
  kind           TEXT NOT NULL DEFAULT 'example_sentence',
  text           TEXT NOT NULL,
  reading        TEXT,
  translation_en TEXT,
  translation_zh TEXT,
  explanation_md TEXT,
  audio_clip     TEXT,
  category       TEXT,
  PRIMARY KEY (item_id, position)
);

CREATE TABLE IF NOT EXISTS item_marks (
  item_id     INTEGER PRIMARY KEY REFERENCES vocabulary_items(item_id) ON DELETE CASCADE,
  known       INTEGER NOT NULL DEFAULT 0 CHECK (known IN (0,1)),
  flagged     INTEGER NOT NULL DEFAULT 0 CHECK (flagged IN (0,1)),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS item_sentence_stars (
  item_id    INTEGER NOT NULL,
  position   INTEGER NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(item_id, position),
  FOREIGN KEY(item_id, position)
    REFERENCES item_examples(item_id, position)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS item_source_notes (
  item_id                  INTEGER NOT NULL REFERENCES vocabulary_items(item_id) ON DELETE CASCADE,
  source_book_code          TEXT    NOT NULL,
  source_entry_uuid         TEXT    NOT NULL,
  source_index              INTEGER NOT NULL,
  source_reading            TEXT,
  source_meaning_en         TEXT,
  source_meaning_zh         TEXT,
  source_explanation_md     TEXT,
  source_sentence           TEXT,
  source_translation_en     TEXT,
  source_translation_zh     TEXT,
  source_word_clip          TEXT,
  source_sentence_clip      TEXT,
  PRIMARY KEY (item_id, source_book_code, source_index)
);

CREATE INDEX IF NOT EXISTS idx_item_source_notes_source
  ON item_source_notes(source_book_code, source_index);

CREATE TABLE IF NOT EXISTS item_example_sources (
  item_id           INTEGER NOT NULL,
  position          INTEGER NOT NULL,
  source_book_code  TEXT    NOT NULL,
  source_index      INTEGER NOT NULL,
  PRIMARY KEY (item_id, position, source_book_code, source_index),
  FOREIGN KEY (item_id, position)
    REFERENCES item_examples(item_id, position) ON DELETE CASCADE,
  FOREIGN KEY (item_id, source_book_code, source_index)
    REFERENCES item_source_notes(item_id, source_book_code, source_index)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS vocabulary_migration_reports (
  kind       TEXT NOT NULL,
  group_key  TEXT NOT NULL,
  detail     TEXT NOT NULL,
  row_count  INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  PRIMARY KEY(kind, group_key)
);

CREATE TEMP TABLE _entry_item_map AS
SELECT
  e.entry_id,
  g.item_id
FROM entries e
JOIN (
  SELECT TRIM(kanji) AS norm_kanji,
         TRIM(COALESCE(reading, '')) AS norm_reading,
         MIN(entry_id) AS item_id
  FROM entries
  GROUP BY TRIM(kanji), TRIM(COALESCE(reading, ''))
) g
  ON g.norm_kanji = TRIM(e.kanji)
 AND g.norm_reading = TRIM(COALESCE(e.reading, ''));

INSERT OR IGNORE INTO vocabulary_items(
  item_id, uuid, kanji, reading, verb_pattern, meaning_en, meaning_zh,
  explanation_md, word_clip, created_at, updated_at
)
SELECT
  g.item_id,
  COALESCE(
    (SELECT e.uuid FROM entries e WHERE e.entry_id = g.item_id),
    'item-' || g.item_id
  ),
  (SELECT e.kanji FROM entries e
    WHERE e.entry_id IN (SELECT entry_id FROM _entry_item_map WHERE item_id = g.item_id)
    ORDER BY CASE e.book_code WHEN 'N2' THEN 0 WHEN 'N3' THEN 1 WHEN 'N2_1500' THEN 2 WHEN 'GWB_N2' THEN 3 ELSE 9 END,
             e.unit_number, e.position, e.source_index
    LIMIT 1),
  NULLIF((SELECT e.reading FROM entries e
    WHERE e.entry_id IN (SELECT entry_id FROM _entry_item_map WHERE item_id = g.item_id)
      AND TRIM(COALESCE(e.reading, '')) <> ''
    ORDER BY CASE e.book_code WHEN 'N2' THEN 0 WHEN 'N3' THEN 1 WHEN 'N2_1500' THEN 2 WHEN 'GWB_N2' THEN 3 ELSE 9 END,
             e.unit_number, e.position, e.source_index
    LIMIT 1), ''),
  (SELECT e.verb_pattern FROM entries e
    WHERE e.entry_id IN (SELECT entry_id FROM _entry_item_map WHERE item_id = g.item_id)
      AND TRIM(COALESCE(e.verb_pattern, '')) <> ''
    ORDER BY CASE e.book_code WHEN 'N2' THEN 0 WHEN 'N3' THEN 1 WHEN 'N2_1500' THEN 2 WHEN 'GWB_N2' THEN 3 ELSE 9 END,
             e.unit_number, e.position, e.source_index
    LIMIT 1),
  (SELECT e.meaning_en FROM entries e
    WHERE e.entry_id IN (SELECT entry_id FROM _entry_item_map WHERE item_id = g.item_id)
      AND TRIM(COALESCE(e.meaning_en, '')) <> ''
    ORDER BY CASE e.book_code WHEN 'N2' THEN 0 WHEN 'N3' THEN 1 WHEN 'N2_1500' THEN 2 WHEN 'GWB_N2' THEN 3 ELSE 9 END,
             e.unit_number, e.position, e.source_index
    LIMIT 1),
  (SELECT e.meaning_zh FROM entries e
    WHERE e.entry_id IN (SELECT entry_id FROM _entry_item_map WHERE item_id = g.item_id)
      AND TRIM(COALESCE(e.meaning_zh, '')) <> ''
    ORDER BY CASE e.book_code WHEN 'N2' THEN 0 WHEN 'N3' THEN 1 WHEN 'N2_1500' THEN 2 WHEN 'GWB_N2' THEN 3 ELSE 9 END,
             e.unit_number, e.position, e.source_index
    LIMIT 1),
  (SELECT e.explanation_md FROM entries e
    WHERE e.entry_id IN (SELECT entry_id FROM _entry_item_map WHERE item_id = g.item_id)
      AND TRIM(COALESCE(e.explanation_md, '')) <> ''
    ORDER BY CASE e.book_code WHEN 'N2' THEN 0 WHEN 'N3' THEN 1 WHEN 'N2_1500' THEN 2 WHEN 'GWB_N2' THEN 3 ELSE 9 END,
             e.unit_number, e.position, e.source_index
    LIMIT 1),
  (SELECT e.word_clip FROM entries e
    WHERE e.entry_id IN (SELECT entry_id FROM _entry_item_map WHERE item_id = g.item_id)
      AND TRIM(COALESCE(e.word_clip, '')) <> ''
    ORDER BY CASE e.book_code WHEN 'N2' THEN 0 WHEN 'N3' THEN 1 WHEN 'N2_1500' THEN 2 WHEN 'GWB_N2' THEN 3 ELSE 9 END,
             e.unit_number, e.position, e.source_index
    LIMIT 1),
  (SELECT MIN(e.created_at) FROM entries e
    WHERE e.entry_id IN (SELECT entry_id FROM _entry_item_map WHERE item_id = g.item_id)),
  (SELECT MAX(e.updated_at) FROM entries e
    WHERE e.entry_id IN (SELECT entry_id FROM _entry_item_map WHERE item_id = g.item_id))
FROM (SELECT DISTINCT item_id FROM _entry_item_map) g;

INSERT OR IGNORE INTO book_entries(
  entry_id, item_id, uuid, book_code, unit_number, source_index, position,
  sentence, explanation_md, sentence_clip, created_at, updated_at
)
SELECT
  e.entry_id, m.item_id, e.uuid, e.book_code, e.unit_number, e.source_index,
  e.position, e.sentence, e.explanation_md, e.sentence_clip, e.created_at, e.updated_at
FROM entries e
JOIN _entry_item_map m ON m.entry_id = e.entry_id;

CREATE TEMP TABLE _example_candidates AS
SELECT
  m.item_id,
  ex.entry_id AS old_entry_id,
  ex.position AS old_position,
  COALESCE(ex.kind, 'example_sentence') AS kind,
  ex.text,
  ex.reading,
  ex.translation_en,
  ex.translation_zh,
  ex.explanation_md,
  ex.audio_clip,
  ex.category,
  ROW_NUMBER() OVER (
    PARTITION BY m.item_id,
                 COALESCE(ex.kind, 'example_sentence'),
                 TRIM(COALESCE(ex.text, '')),
                 TRIM(COALESCE(ex.reading, '')),
                 TRIM(COALESCE(ex.translation_zh, '')),
                 TRIM(COALESCE(ex.category, ''))
    ORDER BY CASE e.book_code WHEN 'N2' THEN 0 WHEN 'N3' THEN 1 WHEN 'N2_1500' THEN 2 WHEN 'GWB_N2' THEN 3 ELSE 9 END,
             e.unit_number, e.position, e.source_index, ex.position
  ) AS dup_rank,
  ROW_NUMBER() OVER (
    PARTITION BY m.item_id
    ORDER BY CASE WHEN COALESCE(ex.kind, 'example_sentence') = 'main_sentence' THEN 0 ELSE 1 END,
             CASE e.book_code WHEN 'N2' THEN 0 WHEN 'N3' THEN 1 WHEN 'N2_1500' THEN 2 WHEN 'GWB_N2' THEN 3 ELSE 9 END,
             e.unit_number, e.position, e.source_index, ex.position
  ) - 1 AS candidate_position
FROM entry_examples ex
JOIN _entry_item_map m ON m.entry_id = ex.entry_id
JOIN entries e ON e.entry_id = ex.entry_id
WHERE TRIM(COALESCE(ex.text, '')) <> '';

CREATE TEMP TABLE _item_example_map AS
SELECT
  item_id,
  old_entry_id,
  old_position,
  ROW_NUMBER() OVER (
    PARTITION BY item_id
    ORDER BY candidate_position
  ) - 1 AS new_position
FROM _example_candidates
WHERE dup_rank = 1;

INSERT OR IGNORE INTO item_examples(
  item_id, position, kind, text, reading, translation_en, translation_zh,
  explanation_md, audio_clip, category
)
SELECT
  c.item_id, map.new_position, c.kind, c.text, c.reading, c.translation_en,
  c.translation_zh, c.explanation_md, c.audio_clip, c.category
FROM _example_candidates c
JOIN _item_example_map map
  ON map.item_id = c.item_id
 AND map.old_entry_id = c.old_entry_id
 AND map.old_position = c.old_position
WHERE c.dup_rank = 1;

INSERT OR IGNORE INTO item_marks(item_id, known, flagged, updated_at)
SELECT
  m.item_id,
  MAX(w.known),
  MAX(w.flagged),
  MAX(w.updated_at)
FROM word_marks w
JOIN _entry_item_map m ON m.entry_id = w.entry_id
GROUP BY m.item_id;

INSERT OR IGNORE INTO item_sentence_stars(item_id, position, updated_at)
SELECT
  map.item_id,
  map.new_position,
  MAX(s.updated_at)
FROM sentence_stars s
JOIN _item_example_map map
  ON map.old_entry_id = s.entry_id
 AND map.old_position = s.position
GROUP BY map.item_id, map.new_position;

INSERT OR IGNORE INTO item_source_notes(
  item_id, source_book_code, source_entry_uuid, source_index, source_reading,
  source_meaning_en, source_meaning_zh, source_explanation_md, source_sentence,
  source_translation_en, source_translation_zh, source_word_clip, source_sentence_clip
)
SELECT
  m.item_id, n.source_book_code, n.source_entry_uuid, n.source_index,
  n.source_reading, n.source_meaning_en, n.source_meaning_zh,
  n.source_explanation_md, n.source_sentence, n.source_translation_en,
  n.source_translation_zh, n.source_word_clip, n.source_sentence_clip
FROM entry_source_notes n
JOIN _entry_item_map m ON m.entry_id = n.entry_id;

INSERT OR IGNORE INTO item_source_notes(
  item_id, source_book_code, source_entry_uuid, source_index, source_reading,
  source_meaning_en, source_meaning_zh, source_explanation_md, source_sentence,
  source_translation_en, source_translation_zh, source_word_clip, source_sentence_clip
)
SELECT
  m.item_id, e.book_code, e.uuid, e.source_index, e.reading, e.meaning_en,
  e.meaning_zh, e.explanation_md, e.sentence, NULL, NULL, e.word_clip,
  e.sentence_clip
FROM entries e
JOIN _entry_item_map m ON m.entry_id = e.entry_id;

INSERT OR IGNORE INTO item_example_sources(
  item_id, position, source_book_code, source_index
)
SELECT
  map.item_id, map.new_position, p.source_book_code, p.source_index
FROM entry_example_sources p
JOIN _item_example_map map
  ON map.old_entry_id = p.entry_id
 AND map.old_position = p.position;

INSERT OR IGNORE INTO item_example_sources(
  item_id, position, source_book_code, source_index
)
SELECT
  map.item_id, map.new_position, e.book_code, e.source_index
FROM _item_example_map map
JOIN entries e ON e.entry_id = map.old_entry_id;

INSERT OR REPLACE INTO vocabulary_migration_reports(kind, group_key, detail, row_count)
SELECT
  'exact_merge',
  TRIM(kanji) || '|' || TRIM(COALESCE(reading, '')),
  GROUP_CONCAT(book_code || ':' || source_index, ', '),
  COUNT(*)
FROM entries
GROUP BY TRIM(kanji), TRIM(COALESCE(reading, ''))
HAVING COUNT(*) > 1;

INSERT OR REPLACE INTO vocabulary_migration_reports(kind, group_key, detail, row_count)
SELECT
  'same_kanji_diff_reading',
  TRIM(kanji),
  GROUP_CONCAT(COALESCE(reading, '') || '@' || book_code || ':' || source_index, ', '),
  COUNT(*)
FROM entries
WHERE TRIM(kanji) <> ''
GROUP BY TRIM(kanji)
HAVING COUNT(DISTINCT TRIM(COALESCE(reading, ''))) > 1;

INSERT OR REPLACE INTO vocabulary_migration_reports(kind, group_key, detail, row_count)
SELECT
  'same_reading_diff_kanji',
  TRIM(COALESCE(reading, '')),
  GROUP_CONCAT(kanji || '@' || book_code || ':' || source_index, ', '),
  COUNT(*)
FROM entries
WHERE TRIM(COALESCE(reading, '')) <> ''
GROUP BY TRIM(COALESCE(reading, ''))
HAVING COUNT(DISTINCT TRIM(kanji)) > 1;

INSERT OR REPLACE INTO vocabulary_migration_reports(kind, group_key, detail, row_count)
SELECT
  'conflicting_meaning_zh',
  CAST(m.item_id AS TEXT),
  GROUP_CONCAT(e.book_code || ':' || e.source_index || '=' || COALESCE(e.meaning_zh, ''), ' | '),
  COUNT(DISTINCT TRIM(COALESCE(e.meaning_zh, '')))
FROM entries e
JOIN _entry_item_map m ON m.entry_id = e.entry_id
WHERE TRIM(COALESCE(e.meaning_zh, '')) <> ''
GROUP BY m.item_id
HAVING COUNT(DISTINCT TRIM(COALESCE(e.meaning_zh, ''))) > 1;

DROP TABLE _entry_item_map;
DROP TABLE _example_candidates;
DROP TABLE _item_example_map;
