-- 002_entry_example_metadata.sql — normalize sentence metadata into examples.
-- The data move is intentionally handled by the dated updates/ script so it
-- can write review artifacts and a backup before touching the canonical DB.

PRAGMA foreign_keys = ON;

ALTER TABLE entry_examples ADD COLUMN translation_en TEXT;
ALTER TABLE entry_examples ADD COLUMN translation_zh TEXT;
ALTER TABLE entry_examples ADD COLUMN explanation_md TEXT;
ALTER TABLE entry_examples ADD COLUMN audio_clip TEXT;
