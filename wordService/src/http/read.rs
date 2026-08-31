use super::mutations::repository_for_params;
use super::response::{
    parse_local_url, query_map, redirect_to_versioned_audio, send_audio, send_file, send_json,
    send_versioned_json, static_asset_path,
};
use crate::audio_review::AudioReviewStore;
use crate::config::AppConfig;
use crate::repository::WordRepository;
use anyhow::{Context, Result};
use serde_json::json;
use std::path::{Path, PathBuf};
use tiny_http::{Request, StatusCode};
use url::Url;

#[derive(Debug, PartialEq, Eq)]
enum AudioVersionRequest {
    ServeImmutable,
    RedirectToVersioned,
    Missing,
}

#[derive(Debug, PartialEq, Eq)]
enum ContentVersionRequest {
    ServeImmutable,
    ServeUnversioned,
    Missing,
}

fn classify_content_version_request(
    requested_version: Option<&str>,
    current_version: &str,
) -> ContentVersionRequest {
    match requested_version {
        Some(requested) if !current_version.is_empty() && requested == current_version => {
            ContentVersionRequest::ServeImmutable
        }
        Some(_) => ContentVersionRequest::Missing,
        None => ContentVersionRequest::ServeUnversioned,
    }
}

/// Only the exact SHA-256 URL published by the API may receive an immutable
/// cache lifetime. A missing version is a legacy route and is redirected once;
/// a different version must not accidentally serve the current file bytes.
fn classify_audio_version_request(
    requested_version: Option<&str>,
    current_version: &str,
) -> AudioVersionRequest {
    match requested_version {
        Some(requested) if requested == current_version => AudioVersionRequest::ServeImmutable,
        Some(_) => AudioVersionRequest::Missing,
        None => AudioVersionRequest::RedirectToVersioned,
    }
}

fn classify_audio_version_parameters(url: &Url, current_version: &str) -> AudioVersionRequest {
    let requested_versions: Vec<_> = url
        .query_pairs()
        .filter_map(|(key, value)| (key == "v").then_some(value))
        .collect();
    match requested_versions.as_slice() {
        [] => classify_audio_version_request(None, current_version),
        [requested] => classify_audio_version_request(Some(requested), current_version),
        // A cache key with multiple version values is non-canonical. Do not
        // give it immutable semantics even if one value happens to be current.
        _ => AudioVersionRequest::Missing,
    }
}

pub(super) fn handle_read(
    request: Request,
    config: AppConfig,
    repository: WordRepository,
    audio_review: AudioReviewStore,
) -> Result<()> {
    // HEAD requests share the same routes as GET. The method value is still
    // read here to make that behavior visible for Rust learners.
    let method = request.method().clone();
    let parsed = parse_local_url(request.url())?;
    let path = parsed.path().to_string();
    let params = query_map(&parsed);
    let repository = repository_for_params(&repository, &params);

    // Static assets and read-only JSON endpoints are handled first because they
    // are exact paths. Parameterized routes such as `/api/entries/{id}` come
    // later.
    if let Some(page_path) = static_page_path(&config.static_dir, &path) {
        return send_file(request, &page_path, "text/html; charset=utf-8");
    }
    if let Some(asset_path) = static_asset_path(&config.static_dir, &path) {
        return send_file(request, &asset_path, "");
    }

    match path.as_str() {
        "/api/summary" => return send_json(request, StatusCode(200), &repository.get_summary()?),
        "/api/books" => {
            return send_json(
                request,
                StatusCode(200),
                &json!({ "items": repository.list_books()? }),
            );
        }
        "/api/units" => {
            return send_json(
                request,
                StatusCode(200),
                &json!({ "items": repository.list_units()? }),
            );
        }
        "/api/study/legacy-seed" => {
            return send_json(request, StatusCode(200), &repository.legacy_mark_seed()?);
        }
        "/api/audio-review" => {
            return send_json(request, StatusCode(200), &audio_review.list()?);
        }
        "/api/entries" => {
            let version_request = classify_content_version_request(
                params.get("v").map(String::as_str),
                &repository.content_revision(),
            );
            if version_request == ContentVersionRequest::Missing {
                return send_json(
                    request,
                    StatusCode(404),
                    &json!({"error": "content version not found"}),
                );
            }
            let unit = match params.get("unit").filter(|value| !value.is_empty()) {
                Some(value) => Some(value.parse::<i64>().context("unit must be an integer")?),
                None => None,
            };
            let state = params.get("state").map(String::as_str).unwrap_or("all");
            let search = params.get("search").map(String::as_str).unwrap_or("");
            let payload = repository.list_entries(unit, state, search)?;
            return match version_request {
                ContentVersionRequest::ServeImmutable => {
                    send_versioned_json(request, StatusCode(200), &payload)
                }
                ContentVersionRequest::ServeUnversioned => {
                    send_json(request, StatusCode(200), &payload)
                }
                ContentVersionRequest::Missing => unreachable!(),
            };
        }
        _ => {}
    }

    if let Some(id_text) = path.strip_prefix("/api/entries/") {
        let entry_id = match id_text.parse::<i64>() {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "invalid entry id"}),
                );
            }
        };
        return match repository.get_entry(entry_id)? {
            Some(entry) => send_json(request, StatusCode(200), &entry),
            None => send_json(
                request,
                StatusCode(404),
                &json!({"error": "entry not found"}),
            ),
        };
    }

    if let Some(audio_path) = path.strip_prefix("/audio/") {
        let Some(file_path) = repository.resolve_audio_path(audio_path) else {
            return send_json(
                request,
                StatusCode(404),
                &json!({"error": "audio not found"}),
            );
        };
        let Some(version) = repository.audio_version(audio_path) else {
            return send_json(
                request,
                StatusCode(404),
                &json!({"error": "audio not found"}),
            );
        };
        match classify_audio_version_parameters(&parsed, &version) {
            AudioVersionRequest::ServeImmutable => {
                return send_audio(request, &file_path, &version);
            }
            AudioVersionRequest::Missing => {
                return send_json(
                    request,
                    StatusCode(404),
                    &json!({"error": "audio version not found"}),
                );
            }
            AudioVersionRequest::RedirectToVersioned => {
                // Build the redirect from the repository rather than echoing
                // the request path, keeping old URLs canonical and safely
                // normalized before a browser stores the new location.
                let versioned_url = repository
                    .audio_url(Some(audio_path))
                    .context("resolved audio file did not produce an audio URL")?;
                return redirect_to_versioned_audio(request, &versioned_url);
            }
        }
    }

    let _ = method;
    send_json(request, StatusCode(404), &json!({"error": "not found"}))
}

fn static_page_path(static_dir: &Path, request_path: &str) -> Option<PathBuf> {
    match request_path {
        // React is the default wall. Keep the former React URLs as aliases so
        // existing bookmarks continue to open the same study experience.
        "/"
        | "/index.html"
        | "/study-wall-react"
        | "/study-wall-react/"
        | "/study-wall-react.html" => Some(static_dir.join("react-rail").join("index.html")),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{
        AudioVersionRequest, ContentVersionRequest, classify_audio_version_parameters,
        classify_audio_version_request, classify_content_version_request, parse_local_url,
        static_page_path,
    };
    use std::path::Path;

    #[test]
    fn study_wall_routes_assign_the_react_page() {
        let root = Path::new("static");
        let react_page = Some(Path::new("static/react-rail/index.html"));

        assert_eq!(static_page_path(root, "/").as_deref(), react_page);
        assert_eq!(static_page_path(root, "/index.html").as_deref(), react_page);
        assert_eq!(
            static_page_path(root, "/study-wall-react/").as_deref(),
            react_page
        );
        assert!(static_page_path(root, "/classic").is_none());
        assert!(static_page_path(root, "/classic/").is_none());
        assert!(static_page_path(root, "/missing").is_none());
    }

    #[test]
    fn audio_version_request_never_serves_changed_bytes_from_an_old_url() {
        let current = "a".repeat(64);

        assert_eq!(
            classify_audio_version_request(None, &current),
            AudioVersionRequest::RedirectToVersioned
        );
        assert_eq!(
            classify_audio_version_request(Some(&current), &current),
            AudioVersionRequest::ServeImmutable
        );
        assert_eq!(
            classify_audio_version_request(Some(&"b".repeat(64)), &current),
            AudioVersionRequest::Missing
        );
        assert_eq!(
            classify_audio_version_request(Some("short"), &current),
            AudioVersionRequest::Missing
        );
        assert_eq!(
            classify_audio_version_parameters(
                &parse_local_url(&format!("/audio/clips/example.mp3?v={current}")).unwrap(),
                &current,
            ),
            AudioVersionRequest::ServeImmutable
        );
        assert_eq!(
            classify_audio_version_parameters(
                &parse_local_url(&format!("/audio/clips/example.mp3?v={current}&v=forged"))
                    .unwrap(),
                &current,
            ),
            AudioVersionRequest::Missing
        );
    }

    #[test]
    fn content_version_request_only_makes_the_current_revision_immutable() {
        let current = "a".repeat(64);
        assert_eq!(
            classify_content_version_request(Some(&current), &current),
            ContentVersionRequest::ServeImmutable
        );
        assert_eq!(
            classify_content_version_request(Some(&"b".repeat(64)), &current),
            ContentVersionRequest::Missing
        );
        assert_eq!(
            classify_content_version_request(None, &current),
            ContentVersionRequest::ServeUnversioned
        );
        assert_eq!(
            classify_content_version_request(Some(""), ""),
            ContentVersionRequest::Missing
        );
    }
}
