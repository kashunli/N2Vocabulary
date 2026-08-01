use anyhow::{Context, Result, bail};

pub(super) fn normalize_clip_path(value: &str, allow_legacy_output_prefix: bool) -> Option<String> {
    let mut normalized = value.replace('\\', "/").trim_start_matches('/').to_string();
    if allow_legacy_output_prefix && let Some(stripped) = normalized.strip_prefix("output/clips/") {
        normalized = format!("clips/{stripped}");
    }
    if !normalized.starts_with("clips/") {
        return None;
    }

    // Reject path traversal and Windows drive tricks before joining with the
    // real clips parent. This is a simple lexical guard; no filesystem access is
    // needed to decide whether a requested clip path is allowed.
    for part in normalized.split('/') {
        if part.is_empty() || part == "." || part == ".." || part.contains(':') {
            return None;
        }
    }
    Some(normalized)
}

pub(super) fn normalize_generated_audio_dir(value: &str) -> Result<String> {
    // Accept a friendly short value like `generated_sentences/edge_tts`, but
    // normalize it to the same `clips/...` shape that the rest of the service
    // stores and serves.
    let mut normalized = value.replace('\\', "/").trim_matches('/').to_string();
    if normalized.is_empty() {
        bail!("generated audio directory cannot be empty");
    }
    if let Some(stripped) = normalized.strip_prefix("output/clips/") {
        normalized = format!("clips/{stripped}");
    } else if !normalized.starts_with("clips/") {
        normalized = format!("clips/{normalized}");
    }
    normalize_clip_path(&normalized, false)
        .filter(|path| !path.ends_with(".mp3"))
        .context("generated audio directory must stay inside clips")
}

pub(super) fn generated_sentence_clip_path(
    generated_dir: &str,
    entry_id: i64,
    position: i64,
) -> Result<String> {
    // The deterministic filename makes regeneration idempotent and easy to
    // audit by entry ID and sentence position.
    let dir = normalize_generated_audio_dir(generated_dir)?;
    Ok(format!("{dir}/word{entry_id}_sentence{position}.mp3"))
}

pub(super) fn generated_word_clip_path(generated_dir: &str, entry_id: i64) -> Result<String> {
    let dir = normalize_generated_audio_dir(generated_dir)?;
    Ok(format!("{dir}/word{entry_id}.mp3"))
}
