use anyhow::{Context, Result};
use std::env;
use std::path::PathBuf;

#[derive(Clone, Debug)]
pub struct AppConfig {
    pub db_path: PathBuf,
    pub static_dir: PathBuf,
    pub clips_dir: PathBuf,
    pub host: String,
    pub port: u16,
    pub book_code: String,
}

impl AppConfig {
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
        })
    }
}

fn env_path(name: &str, fallback: PathBuf) -> PathBuf {
    env::var_os(name).map(PathBuf::from).unwrap_or(fallback)
}
