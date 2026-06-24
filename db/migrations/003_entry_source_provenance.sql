-- 003_entry_source_provenance.sql -- preserve merged cross-book source data.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entry_source_notes (
  entry_id                  INTEGER NOT NULL REFERENCES entries(entry_id) ON DELETE CASCADE,
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
  PRIMARY KEY (entry_id, source_book_code, source_index)
);

CREATE INDEX IF NOT EXISTS idx_entry_source_notes_source
  ON entry_source_notes(source_book_code, source_index);

CREATE TABLE IF NOT EXISTS entry_example_sources (
  entry_id          INTEGER NOT NULL,
  position          INTEGER NOT NULL,
  source_book_code  TEXT    NOT NULL,
  source_index      INTEGER NOT NULL,
  PRIMARY KEY (entry_id, position, source_book_code, source_index),
  FOREIGN KEY (entry_id, position)
    REFERENCES entry_examples(entry_id, position) ON DELETE CASCADE,
  FOREIGN KEY (entry_id, source_book_code, source_index)
    REFERENCES entry_source_notes(entry_id, source_book_code, source_index)
    ON DELETE CASCADE
);
