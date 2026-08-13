//! Library modules for the Rust word service.
//!
//! The binary in `main.rs` stays intentionally tiny: it loads configuration
//! and hands control to `http::run_server`. Keeping most code in library
//! modules makes the repository easier to test because integration tests can
//! import `repository::WordRepository` directly.

pub mod audio_review;
pub mod config;
pub mod http;
pub mod models;
pub mod repository;
pub mod scheduler;
pub mod tts;
pub mod user_store;
