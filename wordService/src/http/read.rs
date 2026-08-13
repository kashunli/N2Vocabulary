use super::mutations::repository_for_params;
use super::response::{parse_local_url, query_map, send_file, send_json, static_asset_path};
use crate::audio_review::AudioReviewStore;
use crate::config::AppConfig;
use crate::repository::WordRepository;
use anyhow::{Context, Result};
use serde_json::json;
use std::path::{Path, PathBuf};
use tiny_http::{Request, StatusCode};

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
        "/api/marks" => return send_json(request, StatusCode(200), &repository.get_marks()?),
        "/api/study/legacy-seed" => {
            return send_json(request, StatusCode(200), &repository.legacy_mark_seed()?);
        }
        "/api/audio-review" => {
            return send_json(request, StatusCode(200), &audio_review.list()?);
        }
        "/api/starred-sentences" => {
            let unit = match params.get("unit").filter(|value| !value.is_empty()) {
                Some(value) => Some(value.parse::<i64>().context("unit must be an integer")?),
                None => None,
            };
            return send_json(
                request,
                StatusCode(200),
                &repository.list_starred_sentences(unit)?,
            );
        }
        "/api/entries" => {
            let unit = match params.get("unit").filter(|value| !value.is_empty()) {
                Some(value) => Some(value.parse::<i64>().context("unit must be an integer")?),
                None => None,
            };
            let state = params.get("state").map(String::as_str).unwrap_or("all");
            let search = params.get("search").map(String::as_str).unwrap_or("");
            let payload = repository.list_entries(unit, state, search)?;
            return send_json(request, StatusCode(200), &payload);
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
        return send_file(request, &file_path, "audio/mpeg");
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
        | "/study-wall-react.html"
        | "/review"
        | "/review/" => Some(static_dir.join("react-rail").join("index.html")),
        // The classic wall now has an explicit URL instead of owning `/`.
        "/classic" | "/classic/" => Some(static_dir.join("index.html")),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::static_page_path;
    use std::path::Path;

    #[test]
    fn study_wall_routes_assign_default_and_classic_pages() {
        let root = Path::new("static");
        let react_page = Some(Path::new("static/react-rail/index.html"));
        let classic_page = Some(Path::new("static/index.html"));

        assert_eq!(static_page_path(root, "/").as_deref(), react_page);
        assert_eq!(static_page_path(root, "/index.html").as_deref(), react_page);
        assert_eq!(
            static_page_path(root, "/study-wall-react/").as_deref(),
            react_page
        );
        assert_eq!(static_page_path(root, "/classic").as_deref(), classic_page);
        assert_eq!(static_page_path(root, "/classic/").as_deref(), classic_page);
        assert_eq!(static_page_path(root, "/review").as_deref(), react_page);
        assert!(static_page_path(root, "/missing").is_none());
    }
}
