use super::{WordRepository, now_utc};
use anyhow::{Context, Result, bail};
use rusqlite::{Connection, OptionalExtension, params};
use std::fs;
use std::path::Path;
use std::thread;
use std::time::Duration;
use tempfile::TempDir;

impl WordRepository {
    /// Update compatibility marks stored with content for guest import.
    pub fn set_mark(&self, entry_id: i64, known: bool, flagged: bool) -> Result<()> {
        // A temporary DB copy avoids fragile direct writes when stale WAL
        // sidecars exist. The shared lock protects the whole replacement.
        let known = known && !flagged;
        let _guard = self
            .write_lock
            .lock()
            .expect("mark write lock should not be poisoned");
        let temp_dir = TempDir::with_prefix("n2_word_mark_")?;
        let temp_db = temp_dir.path().join(
            self.db_path
                .file_name()
                .context("database path should have a filename")?,
        );
        fs::copy(&self.db_path, &temp_db)?;

        {
            let conn = Connection::open(&temp_db)?;
            conn.execute_batch("PRAGMA foreign_keys = ON; PRAGMA journal_mode = DELETE;")?;
            let item_id: Option<i64> = conn
                .query_row(
                    "SELECT item_id FROM book_entries WHERE book_code = ? AND entry_id = ?",
                    params![&self.book_code, entry_id],
                    |row| row.get(0),
                )
                .optional()?;
            let Some(item_id) = item_id else {
                bail!("unknown entry_id");
            };

            if !known && !flagged {
                conn.execute("DELETE FROM item_marks WHERE item_id = ?", [item_id])?;
            } else {
                conn.execute(
                    r#"
                    INSERT INTO item_marks(item_id, known, flagged, updated_at)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(item_id) DO UPDATE SET
                      known = excluded.known,
                      flagged = excluded.flagged,
                      updated_at = excluded.updated_at
                    "#,
                    params![item_id, bool_to_int(known), bool_to_int(flagged), now_utc()],
                )?;
            }
        }

        copy_database_back_with_retry(&temp_db, &self.db_path)
    }
}

fn copy_database_back_with_retry(temp_db: &Path, db_path: &Path) -> Result<()> {
    let mut last_error = None;
    for _ in 0..10 {
        match fs::copy(temp_db, db_path) {
            Ok(_) => return Ok(()),
            Err(error) => {
                last_error = Some(error);
                thread::sleep(Duration::from_millis(150));
            }
        }
    }
    Err(last_error
        .context("database copy should have been attempted")?
        .into())
}

fn bool_to_int(value: bool) -> i64 {
    if value { 1 } else { 0 }
}
