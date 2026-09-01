-- 012_audio_ids.sql — replace digest-backed audio identities with database IDs.
--
-- Audio IDs are opaque cache keys.  An unchanged clip keeps its ID; an import
-- or export that replaces the clip assigns a new AUTOINCREMENT ID.  Runtime
-- requests therefore read only this small metadata row and never hash MP3
-- bytes.

CREATE TABLE IF NOT EXISTS audio_assets (
  audio_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  clip_path   TEXT NOT NULL UNIQUE,
  file_size   INTEGER NOT NULL,
  modified_ns INTEGER NOT NULL,
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- Migration 011 stored the same file metadata beside a SHA-256 digest.  Keep
-- the path/stat data and let SQLite allocate compact unique IDs, then remove
-- the obsolete digest table so it cannot accidentally become a runtime
-- dependency again.
INSERT INTO audio_assets(clip_path, file_size, modified_ns, updated_at)
SELECT clip_path, file_size, modified_ns, updated_at
FROM audio_versions
WHERE NOT EXISTS (
  SELECT 1 FROM audio_assets AS existing
  WHERE existing.clip_path = audio_versions.clip_path
);

DROP TABLE audio_versions;
