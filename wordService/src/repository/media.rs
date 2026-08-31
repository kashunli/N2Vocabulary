use super::WordRepository;
use crate::repository::paths::normalize_clip_path;
use anyhow::{Result, anyhow};
use rusqlite::OptionalExtension;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::UNIX_EPOCH;

impl WordRepository {
    /// Return a normalized audio path without computing its content hash.
    ///
    /// List responses can contain hundreds or thousands of clips.  The browser
    /// only needs to know that a clip exists while building that list; the
    /// audio route will redirect this URL to the immutable, hash-versioned URL
    /// when playback actually starts.
    pub fn audio_path_url(&self, clip_path: Option<&str>) -> Option<String> {
        let normalized = normalize_clip_path(clip_path?, true)?;
        let resolved = self.resolve_audio_path(&normalized)?;
        let metadata = resolved.metadata().ok()?;
        metadata.is_file().then(|| format!("/audio/{normalized}"))
    }

    /// Return the immutable URL whose digest was recorded when the clip was
    /// last published. Runtime requests never hash audio bytes.
    pub fn audio_url(&self, clip_path: Option<&str>) -> Option<String> {
        let normalized = normalize_clip_path(clip_path?, true)?;
        let resolved = self.resolve_audio_path(&normalized)?;
        if !resolved.metadata().ok()?.is_file() {
            return None;
        }
        let version = self.audio_version_for_clip(&normalized, &resolved)?;
        Some(format!("/audio/{normalized}?v={version}"))
    }

    /// Resolve a request path and return the persisted clip version. This is
    /// used by the audio route and intentionally performs no SHA-256 work.
    pub fn audio_version(&self, request_path: &str) -> Option<String> {
        let normalized = normalize_clip_path(request_path, false)?;
        let resolved = self.resolve_audio_path(&normalized)?;
        if !resolved.metadata().ok()?.is_file() {
            return None;
        }
        self.audio_version_for_clip(&normalized, &resolved)
    }

    /// Record a clip after an importer or generator has written it.
    ///
    /// File size and modification time are persisted alongside the digest.
    /// Callers invoke this after writing a clip, so an explicit update always
    /// recalculates the digest even if a filesystem timestamp was preserved.
    /// The bulk sync command avoids calling this for unchanged files.
    pub fn record_audio_version(&self, clip_path: &str) -> Result<Option<String>> {
        let normalized = normalize_clip_path(clip_path, true)
            .ok_or_else(|| anyhow!("invalid audio clip path: {clip_path}"))?;
        let resolved = self
            .resolve_audio_path(&normalized)
            .ok_or_else(|| anyhow!("invalid audio clip path: {clip_path}"))?;
        let conn = self.connect()?;
        let Some(metadata) = resolved.metadata().ok().filter(|value| value.is_file()) else {
            conn.execute(
                "DELETE FROM audio_versions WHERE clip_path = ?",
                [&normalized],
            )?;
            return Ok(None);
        };
        let size = i64::try_from(metadata.len())?;
        let modified_ns = modified_ns(&metadata)?;
        let sha256 = format!("{:x}", Sha256::digest(fs::read(&resolved)?));
        conn.execute(
            r#"
            INSERT INTO audio_versions(clip_path, sha256, file_size, modified_ns)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(clip_path) DO UPDATE SET
              sha256 = excluded.sha256,
              file_size = excluded.file_size,
              modified_ns = excluded.modified_ns,
              updated_at = CURRENT_TIMESTAMP
            "#,
            (&normalized, &sha256, &size, &modified_ns),
        )?;
        Ok(Some(sha256))
    }

    fn audio_version_for_clip(&self, normalized: &str, path: &Path) -> Option<String> {
        let metadata = path.metadata().ok()?;
        let size = i64::try_from(metadata.len()).ok()?;
        let modified_ns = modified_ns(&metadata).ok()?;
        let conn = self.connect().ok()?;
        let (sha256, stored_size, stored_modified_ns): (String, i64, i64) = conn
            .query_row(
                "SELECT sha256, file_size, modified_ns FROM audio_versions WHERE clip_path = ?",
                [normalized],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .optional()
            .ok()??;
        (stored_size == size && stored_modified_ns == modified_ns).then_some(sha256)
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
