use crate::audio_review::{AudioReviewStore, AudioReviewUpdate};
use crate::config::AppConfig;
use crate::repository::WordRepository;
use crate::tts::TtsService;
use anyhow::{Context, Result, anyhow};
use serde_json::json;
use std::collections::HashMap;
use std::thread;
use tiny_http::{Method, Request, Server, StatusCode};

mod response;

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

fn handle_post(
    request: Request,
    config: AppConfig,
    repository: WordRepository,
    tts_service: TtsService,
) -> Result<()> {
    let parsed = parse_local_url(request.url())?;
    let path = parsed.path().trim_end_matches('/').to_string();
    let params = query_map(&parsed);
    let repository = repository_for_params(&repository, &params);
    if let Some(rest) = path.strip_prefix("/api/units/") {
        let parts = rest.split('/').collect::<Vec<_>>();
        if parts.len() == 2 && parts[1] == "flagged-audio" {
            let unit_number = match parts[0].parse::<i64>() {
                Ok(value) => value,
                Err(_) => {
                    return send_json(
                        request,
                        StatusCode(400),
                        &json!({"error": "unit must be an integer"}),
                    );
                }
            };
            return match repository.export_unit_flagged_audio(unit_number) {
                Ok(payload) => send_json(request, StatusCode(200), &payload),
                Err(error)
                    if error.to_string().contains("no flagged words")
                        || error.to_string().contains("missing audio clips")
                        || error.to_string().contains("unit must be") =>
                {
                    send_json(
                        request,
                        StatusCode(400),
                        &json!({"error": error.to_string()}),
                    )
                }
                Err(error) => send_json(
                    request,
                    StatusCode(500),
                    &json!({"error": error.to_string()}),
                ),
            };
        }
    }

    let Some(rest) = path.strip_prefix("/api/entries/") else {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    };
    // Expected shapes:
    // /api/entries/{entry_id}/audio
    // /api/entries/{entry_id}/examples/{position}/audio
    // Splitting after the fixed prefix keeps parsing straightforward and makes
    // invalid routes return 404 instead of accidentally matching a partial path.
    let parts = rest.split('/').collect::<Vec<_>>();
    if parts.len() == 2 && parts[1] == "audio" {
        let entry_id = match parts[0].parse::<i64>() {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "invalid entry id"}),
                );
            }
        };
        return match repository.ensure_word_audio(entry_id, &config.tts.generated_dir, |word| {
            tts_service.synthesize_sentence(word)
        }) {
            Ok(payload) => send_json(request, StatusCode(200), &payload),
            Err(error)
                if error.to_string().contains("unknown entry")
                    || error.to_string().contains("empty word") =>
            {
                send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": error.to_string()}),
                )
            }
            Err(error) => send_json(
                request,
                StatusCode(500),
                &json!({"error": error.to_string()}),
            ),
        };
    }
    if parts.len() != 4 || parts[1] != "examples" || parts[3] != "audio" {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    }
    let entry_id = match parts[0].parse::<i64>() {
        Ok(value) => value,
        Err(_) => {
            return send_json(
                request,
                StatusCode(400),
                &json!({"error": "invalid entry id"}),
            );
        }
    };
    let position = match parts[2].parse::<i64>() {
        Ok(value) => value,
        Err(_) => {
            return send_json(
                request,
                StatusCode(400),
                &json!({"error": "invalid sentence index"}),
            );
        }
    };

    let result = repository.ensure_example_audio(
        entry_id,
        position,
        &config.tts.generated_dir,
        |sentence| tts_service.synthesize_sentence(sentence),
    );
    // The repository returns domain errors as anyhow messages. Mapping the
    // known ones here keeps HTTP status choices in the HTTP layer.
    match result {
        Ok(payload) => send_json(request, StatusCode(200), &payload),
        Err(error) if error.to_string().contains("unknown example") => send_json(
            request,
            StatusCode(404),
            &json!({"error": "unknown example"}),
        ),
        Err(error) if error.to_string().contains("empty sentence") => send_json(
            request,
            StatusCode(400),
            &json!({"error": "empty sentence"}),
        ),
        Err(error) => send_json(
            request,
            StatusCode(500),
            &json!({"error": error.to_string()}),
        ),
    }
}

fn handle_put(
    mut request: Request,
    repository: WordRepository,
    audio_review: AudioReviewStore,
) -> Result<()> {
    let parsed = parse_local_url(request.url())?;
    let path = parsed.path().trim_end_matches('/').to_string();
    let params = query_map(&parsed);
    let repository = repository_for_params(&repository, &params);
    let mut body = String::new();
    request.as_reader().read_to_string(&mut body)?;
    // An empty PUT body means "clear both flags". That matches the frontend's
    // simple mark contract and avoids requiring `{}` for a no-state mark.
    let body: serde_json::Value =
        match serde_json::from_str(if body.trim().is_empty() { "{}" } else { &body }) {
            Ok(value) => value,
            Err(_) => {
                return send_json(request, StatusCode(400), &json!({"error": "invalid JSON"}));
            }
        };

    if let Some(id_text) = path.strip_prefix("/api/audio-review/") {
        let source_index = match id_text.parse::<i64>() {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "source index must be integer"}),
                );
            }
        };
        let update = match serde_json::from_value::<AudioReviewUpdate>(body.clone()) {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "invalid audio review payload"}),
                );
            }
        };
        return match audio_review.set_decision(source_index, update) {
            Ok(decision) => send_json(request, StatusCode(200), &decision),
            Err(error) if error.to_string().contains("unknown audio review item") => send_json(
                request,
                StatusCode(404),
                &json!({"error": "unknown audio review item"}),
            ),
            Err(error)
                if error.to_string().contains("invalid audio review decision")
                    || error.to_string().contains("cannot be empty")
                    || error.to_string().contains("equivalent to the original") =>
            {
                send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": error.to_string()}),
                )
            }
            Err(error) => Err(error),
        };
    }

    if let Some(id_text) = path.strip_prefix("/api/marks/") {
        let entry_id = match id_text.parse::<i64>() {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "entry id must be integer"}),
                );
            }
        };

        let known = body
            .get("known")
            .and_then(|value| value.as_bool())
            .unwrap_or(false);
        let flagged = body
            .get("flagged")
            .and_then(|value| value.as_bool())
            .unwrap_or(false);

        return match repository.set_mark(entry_id, known, flagged) {
            Ok(()) => send_json(request, StatusCode(200), &json!({"ok": true})),
            Err(error) if error.to_string().contains("unknown entry_id") => send_json(
                request,
                StatusCode(404),
                &json!({"error": "unknown entry_id"}),
            ),
            Err(error) => Err(error),
        };
    }

    if let Some(rest) = path.strip_prefix("/api/entries/") {
        let parts = rest.split('/').collect::<Vec<_>>();
        if parts.len() == 4 && parts[1] == "examples" && parts[3] == "star" {
            let entry_id = match parts[0].parse::<i64>() {
                Ok(value) => value,
                Err(_) => {
                    return send_json(
                        request,
                        StatusCode(400),
                        &json!({"error": "entry id must be integer"}),
                    );
                }
            };
            let position = match parts[2].parse::<i64>() {
                Ok(value) => value,
                Err(_) => {
                    return send_json(
                        request,
                        StatusCode(400),
                        &json!({"error": "sentence index must be integer"}),
                    );
                }
            };
            let starred = body
                .get("starred")
                .and_then(|value| value.as_bool())
                .unwrap_or(false);
            return match repository.set_sentence_star(entry_id, position, starred) {
                Ok(()) => send_json(
                    request,
                    StatusCode(200),
                    &json!({"ok": true, "starred": starred}),
                ),
                Err(error) if error.to_string().contains("unknown example") => send_json(
                    request,
                    StatusCode(404),
                    &json!({"error": "unknown example"}),
                ),
                Err(error) => Err(error),
            };
        }
    }

    send_json(request, StatusCode(404), &json!({"error": "not found"}))
}

fn handle_delete(request: Request, audio_review: AudioReviewStore) -> Result<()> {
    let parsed = parse_local_url(request.url())?;
    let path = parsed.path().trim_end_matches('/').to_string();
    let Some(id_text) = path.strip_prefix("/api/audio-review/") else {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    };
    let source_index = match id_text.parse::<i64>() {
        Ok(value) => value,
        Err(_) => {
            return send_json(
                request,
                StatusCode(400),
                &json!({"error": "source index must be integer"}),
            );
        }
    };
    match audio_review.clear_decision(source_index) {
        Ok(cleared) => send_json(
            request,
            StatusCode(200),
            &json!({"ok": true, "cleared": cleared}),
        ),
        Err(error) if error.to_string().contains("unknown audio review item") => send_json(
            request,
            StatusCode(404),
            &json!({"error": "unknown audio review item"}),
        ),
        Err(error) => Err(error),
    }
}

fn repository_for_params(
    repository: &WordRepository,
    params: &HashMap<String, String>,
) -> WordRepository {
    match params.get("book").filter(|value| !value.trim().is_empty()) {
        Some(book_code) => repository.for_book(book_code),
        None => repository.clone(),
    }
}
