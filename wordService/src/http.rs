use crate::audio_review::AudioReviewStore;
use crate::config::AppConfig;
use crate::repository::WordRepository;
use crate::user_store::UserStore;
use anyhow::{Result, anyhow};
use serde_json::json;
use std::thread;
use tiny_http::{Method, Request, Server, StatusCode};

mod account;
mod mutations;
mod read;
mod response;

use mutations::{handle_delete, handle_post, handle_put};
use read::handle_read;
use response::send_json;

/// Start the local HTTP server.
///
/// This service uses `tiny_http`, which is intentionally simple and blocking.
/// Each accepted request gets a short-lived thread so slow file reads do not
/// stop the server from accepting the next browser request.
pub fn run_server(config: AppConfig) -> Result<()> {
    let repository = WordRepository::new(
        config.db_path.clone(),
        config.clips_dir.clone(),
        &config.book_code,
    );
    repository.ensure_ready()?;
    let user_store = UserStore::new(config.users_db_path.clone());
    user_store.ensure_ready()?;
    let audio_review = AudioReviewStore::load(
        config.review_db_path.clone(),
        &config.review_evidence_path,
        &config.review_seed_path,
    )?;

    let address = format!("{}:{}", config.host, config.port);
    let server = Server::http(&address).map_err(|error| anyhow!(error.to_string()))?;
    println!(
        "N2 wordService Rust running at http://{}:{}",
        config.host, config.port
    );
    println!(
        "  mode: {:?}; browser origin: {}",
        config.mode, config.origin
    );
    println!("  db: {}", config.db_path.display());
    println!("  clips: {}", config.clips_dir.display());
    println!("  audio review db: {}", config.review_db_path.display());
    println!("  users db: {}", config.users_db_path.display());

    for request in server.incoming_requests() {
        // The shared state types are cheap handles:
        // - AppConfig clones strings/paths.
        // - WordRepository clones an Arc-backed write lock plus paths.
        let request_config = config.clone();
        let request_repository = repository.clone();
        let request_audio_review = audio_review.clone();
        let request_user_store = user_store.clone();
        thread::spawn(move || {
            if let Err(error) = handle_request(
                request,
                request_config,
                request_repository,
                request_audio_review,
                request_user_store,
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
    audio_review: AudioReviewStore,
    user_store: UserStore,
) -> Result<()> {
    if matches!(
        request.method(),
        Method::Post | Method::Put | Method::Delete
    ) && !origin_matches(
        request
            .headers()
            .iter()
            .find(|header| header.field.equiv("Origin"))
            .map(|header| header.value.as_str()),
        &config.origin,
    ) {
        return send_json(
            request,
            StatusCode(403),
            &json!({"error": "invalid request origin"}),
        );
    }
    let request_path = request
        .url()
        .split('?')
        .next()
        .unwrap_or("")
        .trim_end_matches('/');
    if account::is_account_path(request_path) {
        return match request.method() {
            Method::Get | Method::Head => account::handle_get(request, user_store),
            Method::Post => account::handle_post(request, user_store, repository),
            Method::Put => account::handle_put(request, user_store, repository),
            Method::Options => send_json(
                request,
                StatusCode(405),
                &json!({"error": "method not allowed"}),
            ),
            _ => send_json(
                request,
                StatusCode(405),
                &json!({"error": "method not allowed"}),
            ),
        };
    }
    // Keep method routing near the top so unsupported mutation methods fail
    // before any path-specific logic runs.
    match request.method() {
        Method::Options => {
            return send_json(
                request,
                StatusCode(405),
                &json!({"error": "method not allowed"}),
            );
        }
        Method::Get | Method::Head => {}
        Method::Put => return handle_put(request, audio_review),
        Method::Delete => return handle_delete(request, audio_review),
        Method::Post => return handle_post(request, repository),
        _ => {
            return send_json(
                request,
                StatusCode(405),
                &json!({"error": "method not allowed"}),
            );
        }
    }

    handle_read(request, config, repository, audio_review)
}

/// A same-origin browser sends Origin for unsafe fetches. Requiring an exact
/// configured value prevents another website from triggering local or public
/// mutations with a victim's cookies; CSRF tokens still protect sessions too.
fn origin_matches(request_origin: Option<&str>, expected_origin: &str) -> bool {
    request_origin.is_some_and(|origin| origin == expected_origin)
}

#[cfg(test)]
mod tests {
    use super::origin_matches;

    #[test]
    fn unsafe_requests_require_the_exact_configured_origin() {
        assert!(origin_matches(
            Some("http://127.0.0.1:8767"),
            "http://127.0.0.1:8767"
        ));
        assert!(!origin_matches(
            Some("http://localhost:8767"),
            "http://127.0.0.1:8767"
        ));
        assert!(!origin_matches(None, "http://127.0.0.1:8767"));
    }
}
