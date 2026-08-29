use anyhow::{Context, Result, bail};
use std::env;
use std::path::PathBuf;
use url::Url;

/// Runtime configuration after environment variables have been resolved.
///
/// Cloning this struct is cheap enough for the tiny HTTP server because it only
/// clones paths and strings. Each request thread gets its own copy, which avoids
/// lifetime juggling around borrowed configuration.
#[derive(Clone, Debug)]
pub struct AppConfig {
    pub db_path: PathBuf,
    pub static_dir: PathBuf,
    pub review_db_path: PathBuf,
    pub users_db_path: PathBuf,
    pub review_evidence_path: PathBuf,
    pub review_seed_path: PathBuf,
    pub clips_dir: PathBuf,
    pub host: String,
    pub port: u16,
    pub mode: RuntimeMode,
    /// Exact browser origin allowed to submit same-origin mutations.
    pub origin: String,
    pub book_code: String,
}

/// Runtime profiles deliberately separate the trusted desktop workflow from a
/// reverse-proxy HTTPS deployment. Public mode becomes usable only after its
/// mail, CAPTCHA, and rate-limit settings are introduced in later changes.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RuntimeMode {
    Local,
    Public,
}

impl RuntimeMode {
    fn from_env() -> Result<Self> {
        match env::var("N2_WORD_SERVICE_MODE")
            .unwrap_or_else(|_| "local".to_string())
            .trim()
            .to_ascii_lowercase()
            .as_str()
        {
            "local" => Ok(Self::Local),
            "public" => Ok(Self::Public),
            value => bail!("N2_WORD_SERVICE_MODE must be either local or public, got {value:?}"),
        }
    }
}

impl AppConfig {
    /// Build configuration from environment variables, using repo-local
    /// defaults that work when this crate is run from `wordService`.
    pub fn from_env() -> Result<Self> {
        // CARGO_MANIFEST_DIR is fixed at compile time and points at
        // wordService. Using it keeps defaults stable no matter which directory
        // the user runs cargo from.
        let word_service_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let project_root = word_service_dir
            .parent()
            .context("wordService should live inside the N2Vocabulary root")?;

        let default_db = word_service_dir.join("data").join("n2vocab.sqlite");
        let default_static = word_service_dir.join("static");
        let default_clips = project_root.join("clips");

        let host = env::var("N2_WORD_SERVICE_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
        let port = env::var("N2_WORD_SERVICE_PORT")
            .unwrap_or_else(|_| "8767".to_string())
            .parse()
            .context("N2_WORD_SERVICE_PORT must be an integer from 0 to 65535")?;
        let mode = RuntimeMode::from_env()?;
        let origin = canonical_origin(
            env::var("N2_WORD_SERVICE_ORIGIN").unwrap_or_else(|_| format!("http://{host}:{port}")),
            mode,
        )?;

        Ok(Self {
            users_db_path: env_path(
                "N2_WORD_SERVICE_USERS_DB",
                word_service_dir.join("data").join("users.sqlite"),
            ),
            review_db_path: env_path(
                "N2_WORD_SERVICE_REVIEW_DB",
                word_service_dir.join("data").join("audio_reviews.sqlite"),
            ),
            review_evidence_path: env_path(
                "N2_WORD_SERVICE_REVIEW_EVIDENCE",
                project_root
                    .join("reviews")
                    .join("vocabulary_audio")
                    .join("n2_all_both_candidates.json"),
            ),
            review_seed_path: env_path(
                "N2_WORD_SERVICE_REVIEW_SEED",
                project_root
                    .join("reviews")
                    .join("vocabulary_audio")
                    .join("n2_all_both.json"),
            ),
            db_path: env_path("N2_WORD_SERVICE_DB", default_db),
            static_dir: env_path("N2_WORD_SERVICE_STATIC", default_static),
            clips_dir: env_path("N2_WORD_SERVICE_CLIPS", default_clips),
            host,
            port,
            mode,
            origin,
            book_code: env::var("N2_WORD_SERVICE_BOOK").unwrap_or_else(|_| "N2".to_string()),
        })
    }
}

fn canonical_origin(raw: String, mode: RuntimeMode) -> Result<String> {
    let url = Url::parse(raw.trim()).context("N2_WORD_SERVICE_ORIGIN must be an absolute URL")?;
    if !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
        || (url.path() != "" && url.path() != "/")
    {
        bail!("N2_WORD_SERVICE_ORIGIN must contain only a scheme, host, and optional port");
    }
    let origin = url.origin().ascii_serialization();
    if origin == "null" {
        bail!("N2_WORD_SERVICE_ORIGIN must use an HTTP or HTTPS origin");
    }
    if mode == RuntimeMode::Public && url.scheme() != "https" {
        bail!("public mode requires an https N2_WORD_SERVICE_ORIGIN");
    }
    Ok(origin)
}

/// Read an environment variable as a path while preserving non-UTF-8 Windows
/// paths. `env::var_os` is a small but useful Rust habit for filesystem paths.
fn env_path(name: &str, fallback: PathBuf) -> PathBuf {
    env::var_os(name).map(PathBuf::from).unwrap_or(fallback)
}

#[cfg(test)]
mod tests {
    use super::{RuntimeMode, canonical_origin};

    #[test]
    fn canonical_origin_rejects_paths_and_requires_https_in_public_mode() {
        assert_eq!(
            canonical_origin("http://127.0.0.1:8767/".to_string(), RuntimeMode::Local).unwrap(),
            "http://127.0.0.1:8767"
        );
        assert!(
            canonical_origin("https://example.test/app".to_string(), RuntimeMode::Public).is_err()
        );
        assert!(canonical_origin("http://example.test".to_string(), RuntimeMode::Public).is_err());
        assert!(
            canonical_origin("https://user@example.test".to_string(), RuntimeMode::Public).is_err()
        );
    }
}
