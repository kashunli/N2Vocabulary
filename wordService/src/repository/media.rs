use super::{CachedAudioVersion, WordRepository};
use crate::repository::paths::normalize_clip_path;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};

impl WordRepository {
    pub fn audio_url(&self, clip_path: Option<&str>) -> Option<String> {
        // Missing or invalid stored paths become absent audio rather than
        // making an otherwise valid vocabulary response fail.
        let normalized = normalize_clip_path(clip_path?, true)?;
        let resolved = self.resolve_audio_path(&normalized)?;
        let version = self.audio_version_for_path(&resolved)?;
        Some(format!("/audio/{normalized}?v={version}"))
    }

    /// Resolve and hash a request path using the file server's strict rules.
    pub fn audio_version(&self, request_path: &str) -> Option<String> {
        self.resolve_audio_path(request_path)
            .and_then(|path| self.audio_version_for_path(&path))
    }

    fn audio_version_for_path(&self, path: &Path) -> Option<String> {
        let metadata = path.metadata().ok()?;
        if !metadata.is_file() {
            return None;
        }
        let size = metadata.len();
        let modified = metadata.modified().ok()?;
        if let Some(cached) = self
            .audio_versions
            .lock()
            .expect("audio version cache lock should not be poisoned")
            .get(path)
            .filter(|cached| cached.size == size && cached.modified == modified)
        {
            return Some(cached.sha256.clone());
        }
        let sha256 = format!("{:x}", Sha256::digest(fs::read(path).ok()?));
        self.audio_versions
            .lock()
            .expect("audio version cache lock should not be poisoned")
            .insert(
                path.to_path_buf(),
                CachedAudioVersion {
                    size,
                    modified,
                    sha256: sha256.clone(),
                },
            );
        Some(sha256)
    }

    pub fn resolve_audio_path(&self, request_path: &str) -> Option<PathBuf> {
        let normalized = normalize_clip_path(request_path, false)?;
        // Stored paths begin with `clips/`; clips_dir names that directory, so
        // joining from its parent preserves the stored relative path.
        let clips_parent = self.clips_dir.parent().unwrap_or_else(|| Path::new("."));
        Some(clips_parent.join(normalized))
    }
}
