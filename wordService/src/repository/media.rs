use super::WordRepository;
use crate::repository::paths::normalize_clip_path;
use anyhow::{Result, anyhow};
use rusqlite::OptionalExtension;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

impl WordRepository {
    /// Return a normalized audio path without looking up its cache ID.
    ///
    /// List responses can contain hundreds or thousands of clips. The browser
    /// only needs to know that a clip exists while building that list; the
    /// audio route resolves the persisted ID when playback starts.
    pub fn audio_path_url(&self, clip_path: Option<&str>) -> Option<String> {
        let normalized = normalize_clip_path(clip_path?, true)?;
        let resolved = self.resolve_audio_path(&normalized)?;
        let metadata = resolved.metadata().ok()?;
        metadata.is_file().then(|| format!("/audio/{normalized}"))
    }

    /// Return the immutable URL whose cache ID was recorded when the clip was
    /// last published. Runtime requests never read or hash audio bytes.
    pub fn audio_url(&self, clip_path: Option<&str>) -> Option<String> {
        let normalized = normalize_clip_path(clip_path?, true)?;
        let resolved = self.resolve_audio_path(&normalized)?;
        let audio_id = self.audio_id_for_clip(&normalized, &resolved)?;
        Some(format!("/audio/{normalized}?v={audio_id}"))
    }

    /// Resolve a request path and return the persisted clip ID. This is used
    /// by the audio route and intentionally performs no MP3 hashing.
    pub fn audio_id(&self, request_path: &str) -> Option<String> {
        let normalized = normalize_clip_path(request_path, false)?;
        let resolved = self.resolve_audio_path(&normalized)?;
        self.audio_id_for_clip(&normalized, &resolved)
            .map(|audio_id| audio_id.to_string())
    }

    /// Record a clip after an importer or generator has written it.
    ///
    /// File size and modification time are persisted only to detect an
    /// unregistered filesystem replacement. Every explicit update replaces the
    /// row, which gives the clip a new AUTOINCREMENT ID even when the writer
    /// preserved the old file metadata.
    pub fn record_audio_id(&self, clip_path: &str) -> Result<Option<i64>> {
        let normalized = normalize_clip_path(clip_path, true)
            .ok_or_else(|| anyhow!("invalid audio clip path: {clip_path}"))?;
        let resolved = self
            .resolve_audio_path(&normalized)
            .ok_or_else(|| anyhow!("invalid audio clip path: {clip_path}"))?;
        let mut conn = self.connect()?;
        let Some(metadata) = resolved.metadata().ok().filter(|value| value.is_file()) else {
            conn.execute(
                "DELETE FROM audio_assets WHERE clip_path = ?",
                [&normalized],
            )?;
            return Ok(None);
        };
        let size = i64::try_from(metadata.len())?;
        let modified_ns = modified_ns(&metadata)?;
        let transaction = conn.transaction()?;
        transaction.execute(
            "DELETE FROM audio_assets WHERE clip_path = ?",
            [&normalized],
        )?;
        transaction.execute(
            "INSERT INTO audio_assets(clip_path, file_size, modified_ns) VALUES (?, ?, ?)",
            (&normalized, &size, &modified_ns),
        )?;
        let audio_id = transaction.last_insert_rowid();
        transaction.commit()?;
        Ok(Some(audio_id))
    }

    fn audio_id_for_clip(&self, normalized: &str, path: &Path) -> Option<i64> {
        let metadata = path.metadata().ok()?;
        if !metadata.is_file() {
            return None;
        }
        let size = i64::try_from(metadata.len()).ok()?;
        let modified_ns = modified_ns(&metadata).ok()?;
        let conn = self.connect().ok()?;
        let (audio_id, stored_size, stored_modified_ns): (i64, i64, i64) = conn
            .query_row(
                "SELECT audio_id, file_size, modified_ns FROM audio_assets WHERE clip_path = ?",
                [normalized],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .optional()
            .ok()??;
        (stored_size == size && stored_modified_ns == modified_ns).then_some(audio_id)
    }

    pub fn resolve_audio_path(&self, request_path: &str) -> Option<PathBuf> {
        let normalized = normalize_clip_path(request_path, false)?;
        // Stored paths begin with `clips/`; clips_dir names that directory, so
        // joining from its parent preserves the stored relative path.
        let clips_parent = self.clips_dir.parent().unwrap_or_else(|| Path::new("."));
        Some(clips_parent.join(normalized))
    }
}

fn modified_ns(metadata: &std::fs::Metadata) -> Result<i64> {
    let duration = metadata.modified()?.duration_since(UNIX_EPOCH)?;
    Ok(i64::try_from(duration.as_nanos())?)
}
