use crate::config::AppConfig;
use crate::repository::WordRepository;
use crate::tts::TtsService;
use anyhow::{Context, Result, anyhow};
use serde::Serialize;
use serde_json::json;
use std::collections::HashMap;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::thread;
use tiny_http::{Header, Method, Request, Response, Server, StatusCode};
use url::Url;

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
    let tts_service = TtsService::new(&config.tts)?;

    let address = format!("{}:{}", config.host, config.port);
    let server = Server::http(&address).map_err(|error| anyhow!(error.to_string()))?;
    println!(
        "N2 wordService Rust running at http://{}:{}",
        config.host, config.port
    );
    println!("  db: {}", config.db_path.display());
    println!("  clips: {}", config.clips_dir.display());
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
        thread::spawn(move || {
            if let Err(error) = handle_request(
                request,
                request_config,
                request_repository,
                request_tts_service,
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
) -> Result<()> {
    // Keep method routing near the top so unsupported mutation methods fail
    // before any path-specific logic runs.
    match request.method() {
        Method::Options => return send_options(request),
        Method::Get | Method::Head => {}
        Method::Put => return handle_put(request, repository),
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

fn handle_put(mut request: Request, repository: WordRepository) -> Result<()> {
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

fn send_options(request: Request) -> Result<()> {
    let response = add_headers(Response::empty(StatusCode(204)), cors_headers());
    request.respond(response)?;
    Ok(())
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

fn static_asset_path(static_dir: &Path, request_path: &str) -> Option<PathBuf> {
    match request_path {
        "/styles.css" | "/app.js" => Some(static_dir.join(request_path.trim_start_matches('/'))),
        _ => {
            let module_name = request_path.strip_prefix("/js/")?;
            // ES module imports only need direct files in static/js. Keeping the
            // route flat avoids accidentally exposing arbitrary static subtrees.
            if module_name.is_empty()
                || module_name.contains('/')
                || module_name.contains('\\')
                || module_name.contains("..")
                || !module_name.ends_with(".js")
            {
                return None;
            }
            Some(static_dir.join("js").join(module_name))
        }
    }
}
fn send_json<T: Serialize>(request: Request, status: StatusCode, payload: &T) -> Result<()> {
    let data = serde_json::to_vec(payload)?;
    let mut headers = cors_headers();
    headers.push(header("Cache-Control", "no-store"));
    headers.push(header("Content-Type", "application/json; charset=utf-8"));

    // HEAD should return the same status/headers as GET without a response
    // body. This helper centralizes that rule for every JSON endpoint.
    if request.method() == &Method::Head {
        request.respond(add_headers(Response::empty(status), headers))?;
    } else {
        request.respond(add_headers(
            Response::from_data(data).with_status_code(status),
            headers,
        ))?;
    }
    Ok(())
}

fn send_file(request: Request, path: &Path, content_type: &str) -> Result<()> {
    if !path.exists() || !path.is_file() {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    }
    let ctype = if content_type.is_empty() {
        // Let mime_guess handle static assets where the type is obvious from
        // the extension. Audio routes pass an explicit content type above.
        mime_guess::from_path(path)
            .first_or_octet_stream()
            .essence_str()
            .to_string()
    } else {
        content_type.to_string()
    };
    let mut headers = vec![
        header("Cache-Control", "no-store"),
        header("Content-Type", &ctype),
    ];
    headers.extend(cors_headers());

    if request.method() == &Method::Head {
        request.respond(add_headers(Response::empty(StatusCode(200)), headers))?;
    } else {
        request.respond(add_headers(
            Response::from_data(fs::read(path)?).with_status_code(StatusCode(200)),
            headers,
        ))?;
    }
    Ok(())
}

fn add_headers<R: Read>(mut response: Response<R>, headers: Vec<Header>) -> Response<R> {
    for header in headers {
        response.add_header(header);
    }
    response
}

fn parse_local_url(raw: &str) -> Result<Url> {
    // tiny_http exposes only the path/query part for normal requests. Prefixing
    // a dummy host lets the `url` crate parse query strings with standard URL
    // rules instead of hand-splitting on `?` and `&`.
    Url::parse(&format!("http://localhost{raw}")).context("parse request URL")
}

fn query_map(url: &Url) -> HashMap<String, String> {
    url.query_pairs()
        .map(|(key, value)| (key.into_owned(), value.into_owned()))
        .collect()
}

fn cors_headers() -> Vec<Header> {
    vec![
        header("Access-Control-Allow-Origin", "*"),
        header("Access-Control-Allow-Methods", "GET, PUT, POST, OPTIONS"),
        header("Access-Control-Allow-Headers", "Content-Type"),
    ]
}

fn header(name: &str, value: &str) -> Header {
    Header::from_bytes(name.as_bytes(), value.as_bytes()).expect("static header should be valid")
}
#[cfg(test)]
mod tests {
    use super::static_asset_path;
    use std::path::Path;

    #[test]
    fn static_asset_path_allows_known_static_files_and_js_modules() {
        let root = Path::new("static");
        assert_eq!(
            static_asset_path(root, "/styles.css").as_deref(),
            Some(Path::new("static/styles.css"))
        );
        assert_eq!(
            static_asset_path(root, "/js/main.js").as_deref(),
            Some(Path::new("static/js/main.js"))
        );
    }

    #[test]
    fn static_asset_path_rejects_nested_or_non_js_module_paths() {
        let root = Path::new("static");
        assert!(static_asset_path(root, "/js/../app.js").is_none());
        assert!(static_asset_path(root, "/js/nested/main.js").is_none());
        assert!(static_asset_path(root, "/js/main.css").is_none());
        assert!(static_asset_path(root, "/api/summary").is_none());
    }
}
