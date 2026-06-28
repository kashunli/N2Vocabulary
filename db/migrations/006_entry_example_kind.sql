-- 006_entry_example_kind.sql — separate content role from display order.

PRAGMA foreign_keys = ON;

ALTER TABLE entry_examples
  ADD COLUMN kind TEXT NOT NULL DEFAULT 'example_sentence';

UPDATE entry_examples
   SET kind = 'main_sentence'
 WHERE position = 0;

UPDATE entry_examples
   SET kind = 'related_term'
 WHERE position > 0
   AND TRIM(COALESCE(category, '')) <> '';
