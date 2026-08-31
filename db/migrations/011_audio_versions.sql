-- 011_audio_versions.sql — persisted content identities for published audio.
-- Runtime requests read this table; audio import/update workflows refresh rows
-- only for clips whose size or modification time changed.

CREATE TABLE IF NOT EXISTS audio_versions (
  clip_path   TEXT PRIMARY KEY,
  sha256      TEXT NOT NULL,
  file_size   INTEGER NOT NULL,
  modified_ns INTEGER NOT NULL,
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
