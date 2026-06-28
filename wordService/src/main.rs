use anyhow::Result;
use n2_word_service_rust::config::AppConfig;
use n2_word_service_rust::http::run_server;

fn main() -> Result<()> {
    // Rust programs commonly return Result from main. The ? operator can then
    // bubble errors up with context instead of forcing every call site to print
    // and exit manually.
    let config = AppConfig::from_env()?;
    run_server(config)
}
