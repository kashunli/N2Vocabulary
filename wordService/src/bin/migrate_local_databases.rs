use anyhow::{Context, Result, bail};
use n2_word_service_rust::config::AppConfig;
use n2_word_service_rust::repository::WordRepository;
use n2_word_service_rust::user_store::UserStore;

/// Run the idempotent SQLite migrations without starting the HTTP server.
///
/// This intentionally uses the same environment variables and defaults as the
/// service, so a deployment can back up its two databases and run this command
/// as a visible maintenance step before the next server start.
fn main() -> Result<()> {
    let config = AppConfig::from_env()?;
    if !config.db_path.is_file() {
        bail!("content database not found: {}", config.db_path.display());
    }
    if !config.users_db_path.is_file() {
        bail!(
            "users database not found: {}",
            config.users_db_path.display()
        );
    }

    WordRepository::new(&config.db_path, &config.clips_dir, &config.book_code)
        .ensure_ready()
        .with_context(|| format!("migrate content database {}", config.db_path.display()))?;
    UserStore::new(&config.users_db_path)
        .ensure_ready()
        .with_context(|| format!("migrate users database {}", config.users_db_path.display()))?;

    println!("Content database ready: {}", config.db_path.display());
    println!("Users database ready: {}", config.users_db_path.display());
    println!("Exclusive mark migration completed or was already applied.");
    Ok(())
}
