use super::{EXCLUSIVE_MARK_MIGRATION, SPACED_REVIEW_MIGRATION, UserStore, now_utc};
use anyhow::{Result, bail};
use rusqlite::{Connection, OptionalExtension, params};

fn migrate_exclusive_mark_schema(conn: &Connection) -> Result<()> {
    let columns = conn
        .prepare("PRAGMA table_info(study_cards)")?
        .query_map([], |row| row.get::<_, String>(1))?
        .collect::<std::result::Result<Vec<_>, _>>()?;
    let has_status = columns.iter().any(|name| name == "status");
    let has_mark_updated_at = columns.iter().any(|name| name == "mark_updated_at");
    if has_status && has_mark_updated_at {
        conn.execute(
            "INSERT OR IGNORE INTO study_schema_migrations(name,applied_at) VALUES(?,?)",
            params![EXCLUSIVE_MARK_MIGRATION, now_utc()],
        )?;
        return Ok(());
    }

    let has_legacy_marks =
        columns.iter().any(|name| name == "known") && columns.iter().any(|name| name == "flagged");
    if !has_legacy_marks {
        bail!("study_cards has neither the new status columns nor legacy mark columns");
    }

    // SQLite cannot add a CHECK constraint to an existing table in place. A
    // table rebuild makes the exclusive-state invariant part of the schema and
    // intentionally drops the retired good_step column at the same boundary.
    conn.execute_batch(
        r#"
        BEGIN IMMEDIATE;
        CREATE TABLE study_cards_exclusive (
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          item_uuid TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'unmarked'
            CHECK(status IN ('unmarked','known','flagged')),
          mark_updated_at TEXT,
          enrolled_at TEXT,
          due_at TEXT,
          review_level INTEGER NOT NULL DEFAULT 0 CHECK(review_level >= 0),
          last_reviewed_at TEXT,
          last_played_at TEXT,
          preferred_book_code TEXT,
          preferred_source_index INTEGER,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(user_id, item_uuid)
        );
        INSERT INTO study_cards_exclusive(
          user_id, item_uuid, status, mark_updated_at, enrolled_at, due_at,
          review_level, last_reviewed_at, last_played_at, preferred_book_code,
          preferred_source_index, updated_at
        )
        SELECT
          user_id,
          item_uuid,
          CASE
            WHEN flagged = 1 THEN 'flagged'
            WHEN known = 1 THEN 'known'
            ELSE 'unmarked'
          END,
          updated_at,
          enrolled_at,
          due_at,
          review_level,
          last_reviewed_at,
          last_played_at,
          preferred_book_code,
          preferred_source_index,
          updated_at
        FROM study_cards;
        DROP TABLE study_cards;
        ALTER TABLE study_cards_exclusive RENAME TO study_cards;
        CREATE INDEX IF NOT EXISTS study_cards_due ON study_cards(user_id, due_at);
        COMMIT;
        "#,
    )?;
    conn.execute(
        "INSERT OR IGNORE INTO study_schema_migrations(name,applied_at) VALUES(?,?)",
        params![EXCLUSIVE_MARK_MIGRATION, now_utc()],
    )?;
    Ok(())
}

impl UserStore {
    pub fn ensure_ready(&self) -> Result<()> {
        if let Some(parent) = self.db_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let conn = self.connect()?;
        conn.execute_batch(
            r#"
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
              token_hash TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              csrf_token TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              last_used_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS study_cards (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              item_uuid TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'unmarked'
                CHECK(status IN ('unmarked','known','flagged')),
              mark_updated_at TEXT,
              enrolled_at TEXT,
              due_at TEXT,
              review_level INTEGER NOT NULL DEFAULT 0 CHECK(review_level >= 0),
              last_reviewed_at TEXT,
              last_played_at TEXT,
              preferred_book_code TEXT,
              preferred_source_index INTEGER,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(user_id, item_uuid)
            );
            CREATE TABLE IF NOT EXISTS guest_imports (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              import_id TEXT NOT NULL,
              snapshot_checksum TEXT NOT NULL,
              imported_at TEXT NOT NULL,
              PRIMARY KEY(user_id, import_id)
            );
            CREATE TABLE IF NOT EXISTS study_schema_migrations (
              name TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS study_cards_due ON study_cards(user_id, due_at);
            CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
            "#,
        )?;
        let has_review_level = conn
            .prepare("PRAGMA table_info(study_cards)")?
            .query_map([], |row| row.get::<_, String>(1))?
            .collect::<std::result::Result<Vec<_>, _>>()?
            .into_iter()
            .any(|name| name == "review_level");
        if !has_review_level {
            conn.execute(
                "ALTER TABLE study_cards ADD COLUMN review_level INTEGER NOT NULL DEFAULT 0 CHECK(review_level >= 0)",
                [],
            )?;
        }
        migrate_exclusive_mark_schema(&conn)?;
        let migration_applied: Option<String> = conn
            .query_row(
                "SELECT applied_at FROM study_schema_migrations WHERE name=?",
                [SPACED_REVIEW_MIGRATION],
                |row| row.get(0),
            )
            .optional()?;
        if migration_applied.is_none() {
            // The prior scheduler had no compatible level semantics. Preserve
            // tags and normal-playback provenance, but reset every schedule.
            conn.execute(
                r#"UPDATE study_cards SET enrolled_at=NULL,due_at=NULL,review_level=0,
                   last_reviewed_at=NULL"#,
                [],
            )?;
            conn.execute(
                "INSERT INTO study_schema_migrations(name,applied_at) VALUES(?,?)",
                params![SPACED_REVIEW_MIGRATION, now_utc()],
            )?;
        }
        Ok(())
    }
}
