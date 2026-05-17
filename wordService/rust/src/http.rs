use crate::config::AppConfig;
use crate::repository::WordRepository;
use anyhow::{Context, Result, anyhow};
use serde::Serialize;
use serde_json::json;
use std::collections::HashMap;
use std::fs;
use std::io::Read;
use std::path::Path;
use std::thread;
use tiny_http::{Header, Method, Request, Response, Server, StatusCode};
use url::Url;

pub fn run_server(config: AppConfig) -> Result<()> {
    let repository = WordRepository::new(
        config.db_path.clone(),
        config.clips_dir.clone(),
        &config.book_code,
    );
    repository.ensure_ready()?;

    let address = format!("{}:{}", config.host, config.port);
    let server = Server::http(&address).map_err(|error| anyhow!(error.to_string()))?;
    println!(
        "N2 wordService Rust running at http://{}:{}",
        config.host, config.port
    );
    println!("  db: {}", config.db_path.display());
    println!("  clips: {}", config.clips_dir.display());

    for request in server.incoming_requests() {
        let request_config = config.clone();
        let request_repository = repository.clone();
        thread::spawn(move || {
            if let Err(error) = handle_request(request, request_config, request_repository) {
                eprintln!("request failed: {error:#}");
            }
        });
    }

    Ok(())
}

fn handle_request(request: Request, config: AppConfig, repository: WordRepository) -> Result<()> {
    match request.method() {
        Method::Options => return send_options(request),
        Method::Get | Method::Head => {}
        Method::Put => return handle_put(request, repository),
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

    match path.as_str() {
        "/" | "/index.html" => {
            return send_file(
                request,
                &config.static_dir.join("index.html"),
                "text/html; charset=utf-8",
            );
        }
        "/styles.css" | "/app.js" => {
            return send_file(
                request,
                &config.static_dir.join(path.trim_start_matches('/')),
                "",
            );
        }
        "/api/summary" => return send_json(request, StatusCode(200), &repository.get_summary()?),
        "/api/units" => {
            return send_json(
                request,
                StatusCode(200),
                &json!({ "items": repository.list_units()? }),
            );
        }
        "/api/marks" => return send_json(request, StatusCode(200), &repository.get_marks()?),
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

fn handle_put(mut request: Request, repository: WordRepository) -> Result<()> {
    let parsed = parse_local_url(request.url())?;
    let path = parsed.path().trim_end_matches('/').to_string();
    let Some(id_text) = path.strip_prefix("/api/marks/") else {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    };
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

    let mut body = String::new();
    request.as_reader().read_to_string(&mut body)?;
    let body: serde_json::Value =
        match serde_json::from_str(if body.trim().is_empty() { "{}" } else { &body }) {
            Ok(value) => value,
            Err(_) => {
                return send_json(request, StatusCode(400), &json!({"error": "invalid JSON"}));
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

    match repository.set_mark(entry_id, known, flagged) {
        Ok(()) => send_json(request, StatusCode(200), &json!({"ok": true})),
        Err(error) if error.to_string().contains("unknown entry_id") => send_json(
            request,
            StatusCode(404),
            &json!({"error": "unknown entry_id"}),
        ),
        Err(error) => Err(error),
    }
}

fn send_options(request: Request) -> Result<()> {
    let response = add_headers(Response::empty(StatusCode(204)), cors_headers());
    request.respond(response)?;
    Ok(())
}

fn send_json<T: Serialize>(request: Request, status: StatusCode, payload: &T) -> Result<()> {
    let data = serde_json::to_vec(payload)?;
    let mut headers = cors_headers();
    headers.push(header("Cache-Control", "no-store"));
    headers.push(header("Content-Type", "application/json; charset=utf-8"));

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
        header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS"),
        header("Access-Control-Allow-Headers", "Content-Type"),
    ]
}

fn header(name: &str, value: &str) -> Header {
    Header::from_bytes(name.as_bytes(), value.as_bytes()).expect("static header should be valid")
}
