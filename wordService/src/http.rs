use crate::audio_review::AudioReviewStore;
use crate::config::AppConfig;
use crate::repository::WordRepository;
use crate::tts::TtsService;
use anyhow::{Context, Result, anyhow};
use serde_json::json;
use std::thread;
use tiny_http::{Method, Request, Server, StatusCode};

mod mutations;
mod response;

use mutations::{handle_delete, handle_post, handle_put, repository_for_params};
use response::{parse_local_url, query_map, send_file, send_json, send_options, static_asset_path};

/// Start the local HTTP server.
///
/// This service uses `tiny_http`, which is intentionally simple and blocking.
/// Each accepted request gets a short-lived thread so slow file reads or TTS
/// queue waits do not stop the server from accepting the next browser request.
pub fn run_server(config: AppConfig) -> Result<()> {
    let repository = WordRepository::new(
        config.db_path.clone(),
        config.clips_dir.clone(),
        &config.book_code,
    );
    repository.ensure_ready()?;
    let audio_review = AudioReviewStore::load(
        config.review_db_path.clone(),
        &config.review_evidence_path,
        &config.review_seed_path,
    )?;
    let tts_service = TtsService::new(&config.tts)?;

    let address = format!("{}:{}", config.host, config.port);
    let server = Server::http(&address).map_err(|error| anyhow!(error.to_string()))?;
    println!(
        "N2 wordService Rust running at http://{}:{}",
        config.host, config.port
    );
    println!("  db: {}", config.db_path.display());
    println!("  clips: {}", config.clips_dir.display());
    println!("  audio review db: {}", config.review_db_path.display());
    println!(
        "  generated word/sentence audio: {}",
        config.tts.generated_dir
    );

    for request in server.incoming_requests() {
        // The shared state types are cheap handles:
        // - AppConfig clones strings/paths.
        // - WordRepository clones an Arc-backed write lock plus paths.
        // - TtsService clones the queue sender, not the worker.
        let request_config = config.clone();
        let request_repository = repository.clone();
        let request_tts_service = tts_service.clone();
        let request_audio_review = audio_review.clone();
        thread::spawn(move || {
            if let Err(error) = handle_request(
                request,
                request_config,
                request_repository,
                request_tts_service,
                request_audio_review,
            ) {
                eprintln!("request failed: {error:#}");
            }
        });
    }

    Ok(())
}

fn handle_request(
    request: Request,
    config: AppConfig,
    repository: WordRepository,
    tts_service: TtsService,
    audio_review: AudioReviewStore,
) -> Result<()> {
    // Keep method routing near the top so unsupported mutation methods fail
    // before any path-specific logic runs.
    match request.method() {
        Method::Options => return send_options(request),
        Method::Get | Method::Head => {}
        Method::Put => return handle_put(request, repository, audio_review),
        Method::Delete => return handle_delete(request, audio_review),
        Method::Post => return handle_post(request, config, repository, tts_service),
        _ => {
            return send_json(
                request,
                StatusCode(405),
                &json!({"error": "method not allowed"}),
            );
        }
    }

    let method = request.method().clone();
    let parsed = parse_local_url(request.url())?;
    let path = parsed.path().to_string();
    let params = query_map(&parsed);
    let repository = repository_for_params(&repository, &params);

    // Static assets and read-only JSON endpoints are handled first because they
    // are exact paths. Parameterized routes such as `/api/entries/{id}` come
    // later.
    if path == "/" || path == "/index.html" {
        return send_file(
            request,
            &config.static_dir.join("index.html"),
            "text/html; charset=utf-8",
        );
    }
    if path == "/study-wall-react"
        || path == "/study-wall-react/"
        || path == "/study-wall-react.html"
    {
        return send_file(
            request,
            &config.static_dir.join("react-rail").join("index.html"),
            "text/html; charset=utf-8",
        );
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

    // HEAD requests share the same routes as GET. The method value is still
    // read above to make that behavior visible for Rust learners.
    let _ = method;
    send_json(request, StatusCode(404), &json!({"error": "not found"}))
}
