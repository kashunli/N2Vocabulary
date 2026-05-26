use anyhow::{Context, Result};
use std::env;
use std::path::PathBuf;

// These defaults are part of the local workflow contract. They point generated
// sentence audio into the served `clips/` tree so the browser can play the file
// immediately after the backend updates SQLite.
const DEFAULT_TTS_DIR: &str = "clips/generated_sentences/edge_tts";
const DEFAULT_TTS_VOICE: &str = "ja-JP-NanamiNeural";
const DEFAULT_TTS_RATE: &str = "-10%";
const DEFAULT_TTS_PITCH: &str = "+0Hz";

/// Runtime configuration after environment variables have been resolved.
///
/// Cloning this struct is cheap enough for the tiny HTTP server because it only
/// clones paths and strings. Each request thread gets its own copy, which avoids
/// lifetime juggling around borrowed configuration.
#[derive(Clone, Debug)]
pub struct AppConfig {
    pub db_path: PathBuf,
    pub static_dir: PathBuf,
    pub clips_dir: PathBuf,
    pub host: String,
    pub port: u16,
    pub book_code: String,
    pub tts: TtsConfig,
}

/// Microsoft Edge TTS options used by the single backend worker.
#[derive(Clone, Debug)]
pub struct TtsConfig {
    pub voice: String,
    pub rate: String,
    pub pitch: String,
    pub generated_dir: String,
}

impl AppConfig {
    /// Build configuration from environment variables, using repo-local
    /// defaults that work when this crate is run from `wordService/rust`.
    pub fn from_env() -> Result<Self> {
        // CARGO_MANIFEST_DIR is fixed at compile time and points at
        // wordService/rust. Using it keeps defaults stable no matter which
        // directory the user runs cargo from.
        let rust_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let word_service_dir = rust_dir
            .parent()
            .context("rust directory should live inside wordService")?;
        let project_root = word_service_dir
            .parent()
            .context("wordService should live inside the N2Vocabulary root")?;

        let default_db = project_root.join("output").join("n2vocab.sqlite");
        let default_static = word_service_dir.join("static");
        let default_clips = project_root.join("clips");

        Ok(Self {
            db_path: env_path("N2_WORD_SERVICE_DB", default_db),
            static_dir: env_path("N2_WORD_SERVICE_STATIC", default_static),
            clips_dir: env_path("N2_WORD_SERVICE_CLIPS", default_clips),
            host: env::var("N2_WORD_SERVICE_HOST").unwrap_or_else(|_| "127.0.0.1".to_string()),
            port: env::var("N2_WORD_SERVICE_PORT")
                .unwrap_or_else(|_| "8767".to_string())
                .parse()
                .context("N2_WORD_SERVICE_PORT must be an integer from 0 to 65535")?,
            book_code: env::var("N2_WORD_SERVICE_BOOK").unwrap_or_else(|_| "N2".to_string()),
            tts: TtsConfig {
                voice: env::var("N2_WORD_SERVICE_TTS_VOICE")
                    .unwrap_or_else(|_| DEFAULT_TTS_VOICE.to_string()),
                rate: env::var("N2_WORD_SERVICE_TTS_RATE")
                    .unwrap_or_else(|_| DEFAULT_TTS_RATE.to_string()),
                pitch: DEFAULT_TTS_PITCH.to_string(),
                generated_dir: env::var("N2_WORD_SERVICE_TTS_DIR")
                    .unwrap_or_else(|_| DEFAULT_TTS_DIR.to_string()),
            },
        })
    }
}

/// Read an environment variable as a path while preserving non-UTF-8 Windows
/// paths. `env::var_os` is a small but useful Rust habit for filesystem paths.
fn env_path(name: &str, fallback: PathBuf) -> PathBuf {
    env::var_os(name).map(PathBuf::from).unwrap_or(fallback)
}
