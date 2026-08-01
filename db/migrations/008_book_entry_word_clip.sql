-- Preserve pronunciation audio per book placement while retaining the shared
-- vocabulary-item clip as a compatibility fallback.

ALTER TABLE book_entries ADD COLUMN word_clip TEXT;
ALTER TABLE book_entries ADD COLUMN verb_pattern TEXT;
ALTER TABLE book_entries ADD COLUMN meaning_en TEXT;
ALTER TABLE book_entries ADD COLUMN meaning_zh TEXT;

UPDATE book_entries
   SET word_clip = (
     SELECT e.word_clip FROM entries e WHERE e.entry_id = book_entries.entry_id
   )
 WHERE EXISTS (
   SELECT 1 FROM entries e
    WHERE e.entry_id = book_entries.entry_id
      AND TRIM(COALESCE(e.word_clip, '')) <> ''
 );

UPDATE book_entries
   SET verb_pattern = (SELECT e.verb_pattern FROM entries e WHERE e.entry_id = book_entries.entry_id),
       meaning_en = (SELECT e.meaning_en FROM entries e WHERE e.entry_id = book_entries.entry_id),
       meaning_zh = (SELECT e.meaning_zh FROM entries e WHERE e.entry_id = book_entries.entry_id)
 WHERE EXISTS (SELECT 1 FROM entries e WHERE e.entry_id = book_entries.entry_id);
