-- 005_sentence_stars.sql — persistent sentence-level study state.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sentence_stars (
  entry_id   INTEGER NOT NULL,
  position   INTEGER NOT NULL,
  updated_at TEXT    NOT NULL,
  PRIMARY KEY (entry_id, position),
  FOREIGN KEY (entry_id, position)
    REFERENCES entry_examples(entry_id, position)
    ON DELETE CASCADE
);
