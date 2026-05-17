-- 001_initial_schema.sql — books, units, entries, examples, marks
-- Applied by db/migrate.py.  Idempotent within a transaction.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS books (
  code   TEXT PRIMARY KEY,                -- 'N2', 'N3', ...
  title  TEXT NOT NULL,
  notes  TEXT
);

CREATE TABLE IF NOT EXISTS units (
  book_code  TEXT    NOT NULL REFERENCES books(code) ON DELETE CASCADE,
  number     INTEGER NOT NULL,
  header     TEXT    NOT NULL,             -- e.g. "Unit 01 名詞 A"
  title      TEXT    NOT NULL,             -- e.g. "名詞 A"  (stripped)
  PRIMARY KEY (book_code, number)
);

CREATE TABLE IF NOT EXISTS entries (
  entry_id       INTEGER PRIMARY KEY,      -- surrogate; N2 keeps legacy 1..1160
  uuid           TEXT    NOT NULL UNIQUE,  -- xxxxxxxx-xxxx-... assigned on import
  book_code      TEXT    NOT NULL,
  unit_number    INTEGER NOT NULL,
  source_index   INTEGER NOT NULL,         -- the 1..N from THAT book
  position       INTEGER NOT NULL,         -- order within unit
  kanji          TEXT    NOT NULL,
  reading        TEXT,
  headword_text  TEXT    NOT NULL,
  verb_pattern   TEXT,
  meaning_en     TEXT,
  meaning_zh     TEXT,
  sentence       TEXT,
  explanation_md TEXT,
  word_clip      TEXT,
  sentence_clip  TEXT,
  created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (book_code, source_index),
  FOREIGN KEY (book_code, unit_number) REFERENCES units(book_code, number)
);
CREATE INDEX IF NOT EXISTS idx_entries_unit ON entries(book_code, unit_number, position);

CREATE TABLE IF NOT EXISTS entry_examples (
  entry_id       INTEGER NOT NULL REFERENCES entries(entry_id) ON DELETE CASCADE,
  position       INTEGER NOT NULL,          -- 0 = main sentence; 1+ = extra examples
  text           TEXT    NOT NULL,
  translation_en TEXT,
  translation_zh TEXT,
  explanation_md TEXT,                      -- explanation for this example, if generated
  audio_clip     TEXT,                      -- project-root-relative clip path, if available
  PRIMARY KEY (entry_id, position)
);

CREATE TABLE IF NOT EXISTS word_marks (
  entry_id    INTEGER PRIMARY KEY REFERENCES entries(entry_id) ON DELETE CASCADE,
  known       INTEGER NOT NULL DEFAULT 0 CHECK (known   IN (0,1)),
  flagged     INTEGER NOT NULL DEFAULT 0 CHECK (flagged IN (0,1)),
  updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- Touch updated_at automatically on entries UPDATE.
CREATE TRIGGER IF NOT EXISTS trg_entries_updated
AFTER UPDATE ON entries
FOR EACH ROW
BEGIN
  UPDATE entries
     SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
   WHERE entry_id = NEW.entry_id;
END;
