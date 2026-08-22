use crate::audio_review::AudioReviewStore;
use crate::config::AppConfig;
use crate::repository::WordRepository;
use crate::tts::TtsService;
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
use response::{send_json, send_options};

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
    let user_store = UserStore::new(config.users_db_path.clone());
    user_store.ensure_ready()?;
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
    println!("  users db: {}", config.users_db_path.display());
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
        let request_user_store = user_store.clone();
        thread::spawn(move || {
            if let Err(error) = handle_request(
                request,
                request_config,
                request_repository,
                request_tts_service,
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
    tts_service: TtsService,
    audio_review: AudioReviewStore,
    user_store: UserStore,
) -> Result<()> {
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
            Method::Options => send_options(request),
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
        Method::Options => return send_options(request),
        Method::Get | Method::Head => {}
        Method::Put => return handle_put(request, audio_review),
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

    handle_read(request, config, repository, audio_review)
}
