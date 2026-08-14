-- 010_remove_sentence_stars.sql — retire the sentence-star feature.
--
-- Migrations 005 and 007 remain in the ordered history so an old database can
-- still be recreated faithfully. This migration removes both the legacy and
-- canonical tables, including every stored sentence-star record, before the
-- active repository opens the database.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS item_sentence_stars;
DROP TABLE IF EXISTS sentence_stars;
