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
