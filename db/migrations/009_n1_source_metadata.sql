-- Store Mimikara N1 provenance as source metadata instead of explanation text.
-- A shared vocabulary item can occur in several books, so this belongs on the
-- item/source-occurrence row rather than on item_examples or a word-level
-- explanation field.

ALTER TABLE item_source_notes ADD COLUMN source_title TEXT;
ALTER TABLE item_source_notes ADD COLUMN source_page INTEGER;
ALTER TABLE item_source_notes ADD COLUMN source_cd_track TEXT;
ALTER TABLE item_source_notes ADD COLUMN source_notes_md TEXT;

CREATE INDEX IF NOT EXISTS idx_item_source_notes_book_page
  ON item_source_notes(source_book_code, source_page);

-- The importer historically wrote a line like
--   **Source:** N1語彙トレーニング, page 53, CD 1-17
-- into source_explanation_md and duplicated it into the compatibility
-- explanation columns. Extract the structured values before clearing that
-- legacy source text. The remaining lines are source-specific usage/notes,
-- not sentence explanations.
UPDATE item_source_notes
   SET source_title = 'N1語彙トレーニング',
       source_page = CAST(
         substr(
           source_explanation_md,
           instr(source_explanation_md, ', page ') + length(', page '),
           instr(source_explanation_md, ', CD ') - (
             instr(source_explanation_md, ', page ') + length(', page ')
           )
         ) AS INTEGER
       ),
       source_cd_track = trim(
         substr(
           source_explanation_md,
           instr(source_explanation_md, ', CD ') + length(', CD '),
           CASE
             WHEN instr(
               substr(
                 source_explanation_md,
                 instr(source_explanation_md, ', CD ') + length(', CD ')
               ),
               char(10)
             ) > 0
             THEN instr(
               substr(
                 source_explanation_md,
                 instr(source_explanation_md, ', CD ') + length(', CD ')
               ),
               char(10)
             ) - 1
             ELSE length(source_explanation_md)
           END
         )
       ),
       source_notes_md = CASE
         WHEN instr(source_explanation_md, char(10)) > 0
         THEN ltrim(substr(source_explanation_md, instr(source_explanation_md, char(10)) + 1))
         ELSE ''
       END,
       source_explanation_md = NULL
 WHERE source_book_code = 'N1'
   AND source_explanation_md LIKE '**Source:** N1語彙トレーニング, page %, CD %';

-- An N1 placement has no sentence explanation. An empty compatibility value is
-- intentional: COALESCE in older readers must not fall through to a shared
-- vocabulary item's explanation from another book.
UPDATE entries
   SET explanation_md = ''
 WHERE book_code = 'N1';

UPDATE book_entries
   SET explanation_md = ''
 WHERE book_code = 'N1';
