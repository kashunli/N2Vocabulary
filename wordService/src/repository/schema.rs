use super::{
    EXCLUSIVE_MARK_DATA_MIGRATION, WordRepository, collect_rows, now_utc, sqlite_table_exists,
};
use anyhow::{Result, bail};
use rusqlite::{Connection, OptionalExtension, params};

impl WordRepository {
    pub fn ensure_ready(&self) -> Result<()> {
        if !self.db_path.exists() {
            bail!("Database not found: {}", self.db_path.display());
        }
        let mut conn = self.connect()?;
        self.ensure_exclusive_mark_data(&mut conn)?;
        self.ensure_source_provenance_schema(&conn)?;
        self.ensure_example_metadata_schema(&conn)?;
        // `query_row` is the startup probe because these statements return a
        // row; mutation-style `execute` would reject them.
        conn.query_row("SELECT 1 FROM book_entries LIMIT 1", [], |_| Ok(()))?;
        conn.query_row("SELECT 1 FROM vocabulary_items LIMIT 1", [], |_| Ok(()))?;
        Ok(())
    }

    /// Normalize legacy shared marks before they become a guest-import seed.
    fn ensure_exclusive_mark_data(&self, conn: &mut Connection) -> Result<()> {
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS word_service_migrations (
              name TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL
            );
            "#,
        )?;

        let already_applied: Option<String> = conn
            .query_row(
                "SELECT applied_at FROM word_service_migrations WHERE name = ?",
                [EXCLUSIVE_MARK_DATA_MIGRATION],
                |row| row.get(0),
            )
            .optional()?;
        if already_applied.is_some() {
            return Ok(());
        }

        let has_item_marks = sqlite_table_exists(conn, "item_marks")?;
        let has_word_marks = sqlite_table_exists(conn, "word_marks")?;
        let migrated_at = now_utc();
        let transaction = conn.transaction()?;

        if has_item_marks {
            transaction.execute(
                "UPDATE item_marks SET known = 0, updated_at = ? WHERE known = 1 AND flagged = 1",
                [&migrated_at],
            )?;
        }
        if has_word_marks {
            transaction.execute(
                "UPDATE word_marks SET known = 0, updated_at = ? WHERE known = 1 AND flagged = 1",
                [&migrated_at],
            )?;
        }
        transaction.execute(
            "INSERT INTO word_service_migrations(name, applied_at) VALUES(?, ?)",
            params![EXCLUSIVE_MARK_DATA_MIGRATION, migrated_at],
        )?;
        transaction.commit()?;
        Ok(())
    }

    fn ensure_source_provenance_schema(&self, conn: &Connection) -> Result<()> {
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS entry_source_notes (
              entry_id INTEGER NOT NULL REFERENCES entries(entry_id) ON DELETE CASCADE,
              source_book_code TEXT NOT NULL,
              source_entry_uuid TEXT NOT NULL,
              source_index INTEGER NOT NULL,
              source_reading TEXT,
              source_meaning_en TEXT,
              source_meaning_zh TEXT,
              source_explanation_md TEXT,
              source_sentence TEXT,
              source_translation_en TEXT,
              source_translation_zh TEXT,
              source_word_clip TEXT,
              source_sentence_clip TEXT,
              PRIMARY KEY(entry_id, source_book_code, source_index)
            );
            CREATE TABLE IF NOT EXISTS entry_example_sources (
              entry_id INTEGER NOT NULL,
              position INTEGER NOT NULL,
              source_book_code TEXT NOT NULL,
              source_index INTEGER NOT NULL,
              PRIMARY KEY(entry_id, position, source_book_code, source_index),
              FOREIGN KEY(entry_id, position)
                REFERENCES entry_examples(entry_id, position) ON DELETE CASCADE,
              FOREIGN KEY(entry_id, source_book_code, source_index)
                REFERENCES entry_source_notes(entry_id, source_book_code, source_index)
                ON DELETE CASCADE
            );
            "#,
        )?;
        // Older local databases may predate optional canonical source fields.
        let mut statement = conn.prepare("PRAGMA table_info(item_source_notes)")?;
        let rows = statement.query_map([], |row| row.get::<_, String>(1))?;
        let columns = collect_rows(rows)?
            .into_iter()
            .collect::<std::collections::HashSet<_>>();
        for (name, definition) in [
            ("source_title", "TEXT"),
            ("source_page", "INTEGER"),
            ("source_cd_track", "TEXT"),
            ("source_notes_md", "TEXT"),
        ] {
            if !columns.contains(name) {
                conn.execute(
                    &format!("ALTER TABLE item_source_notes ADD COLUMN {name} {definition}"),
                    [],
                )?;
            }
        }
        Ok(())
    }

    fn ensure_example_metadata_schema(&self, conn: &Connection) -> Result<()> {
        let mut statement = conn.prepare("PRAGMA table_info(entry_examples)")?;
        let rows = statement.query_map([], |row| row.get::<_, String>(1))?;
        let columns = collect_rows(rows)?
            .into_iter()
            .collect::<std::collections::HashSet<_>>();
        if !columns.contains("category") {
            conn.execute_batch("ALTER TABLE entry_examples ADD COLUMN category TEXT;")?;
        }
        if !columns.contains("reading") {
            conn.execute_batch("ALTER TABLE entry_examples ADD COLUMN reading TEXT;")?;
        }
        if !columns.contains("kind") {
            conn.execute_batch(
                r#"
                ALTER TABLE entry_examples
                  ADD COLUMN kind TEXT NOT NULL DEFAULT 'example_sentence';
                "#,
            )?;
        }
        conn.execute_batch(
            r#"
            UPDATE entry_examples
               SET kind = 'main_sentence'
             WHERE position = 0
               AND kind = 'example_sentence';

            UPDATE entry_examples
               SET kind = 'related_term'
             WHERE position > 0
               AND kind = 'example_sentence'
               AND TRIM(COALESCE(category, '')) <> '';
            "#,
        )?;
        Ok(())
    }
}
