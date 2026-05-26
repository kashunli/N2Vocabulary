use crate::models::{
    AudioGenerationResponse, EntryExample, EntryListResponse, EntryPayload, MarkState,
    MarksResponse, Summary, UnitRef, UnitSummary,
};
use anyhow::{Context, Result, bail};
use chrono::Utc;
use rusqlite::types::Value;
use rusqlite::{Connection, OptionalExtension, params, params_from_iter};
use std::collections::{BTreeMap, HashMap};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use tempfile::TempDir;

const STATE_VALUES: [&str; 4] = ["all", "known", "flagged", "unmarked"];

/// Data-access layer for the word study service.
///
/// The HTTP layer should not know SQL details, SQLite path rules, or how audio
/// paths are stored. Keeping those decisions here makes the API handlers small
/// and gives tests a clean place to exercise workflow behavior directly.
#[derive(Clone, Debug)]
pub struct WordRepository {
    db_path: PathBuf,
    clips_dir: PathBuf,
    book_code: String,
    write_lock: Arc<Mutex<()>>,
}

/// A raw joined row from the `entries` query.
///
/// This is intentionally not serialized. It mirrors the database shape first,
/// then `serialize_entry` converts it into the browser-facing API shape.
#[derive(Debug)]
struct EntryRow {
    entry_id: i64,
    uuid: String,
    book_code: String,
    source_index: i64,
    unit_number: i64,
    unit_header: String,
    kanji: String,
    reading: Option<String>,
    headword_text: String,
    verb_pattern: Option<String>,
    meaning_en: Option<String>,
    meaning_zh: Option<String>,
    sentence: Option<String>,
    explanation_md: Option<String>,
    word_clip: Option<String>,
    sentence_clip: Option<String>,
    known: Option<i64>,
    flagged: Option<i64>,
    mark_updated_at: Option<String>,
}

impl WordRepository {
    /// Create a repository handle.
    ///
    /// `impl Into<PathBuf>` lets callers pass either `PathBuf` or string-like
    /// path values without forcing every call site to spell out `.into()`.
    pub fn new(
        db_path: impl Into<PathBuf>,
        clips_dir: impl Into<PathBuf>,
        book_code: &str,
    ) -> Self {
        Self {
            db_path: db_path.into(),
            clips_dir: clips_dir.into(),
            book_code: book_code.to_string(),
            write_lock: Arc::new(Mutex::new(())),
        }
    }

    pub fn ensure_ready(&self) -> Result<()> {
        if !self.db_path.exists() {
            bail!("Database not found: {}", self.db_path.display());
        }
        let conn = self.connect()?;
        // rusqlite separates row-returning statements from mutation-style
        // execute calls. query_row is the right startup probe for SELECT.
        conn.query_row("SELECT 1 FROM entries LIMIT 1", [], |_| Ok(()))?;
        conn.query_row("SELECT 1 FROM word_marks LIMIT 1", [], |_| Ok(()))?;
        Ok(())
    }

    fn connect(&self) -> Result<Connection> {
        // Open a fresh SQLite connection per operation. For a local study
        // service this is simple, fast enough, and avoids sharing a Connection
        // across request threads.
        let conn = Connection::open(&self.db_path)
            .with_context(|| format!("open SQLite database {}", self.db_path.display()))?;
        conn.execute_batch("PRAGMA foreign_keys = ON;")?;
        Ok(conn)
    }

    pub fn get_marks(&self) -> Result<MarksResponse> {
        let conn = self.connect()?;
        let mut statement =
            conn.prepare("SELECT entry_id, known, flagged, updated_at FROM word_marks")?;
        let rows = statement.query_map([], |row| {
            let entry_id: i64 = row.get(0)?;
            Ok((
                entry_id.to_string(),
                MarkState {
                    known: int_to_bool(row.get(1)?),
                    flagged: int_to_bool(row.get(2)?),
                    updated_at: row.get(3)?,
                },
            ))
        })?;

        // BTreeMap keeps JSON output stable by sorting entry IDs. That is nice
        // for debugging and for future agents comparing responses.
        let mut marks = BTreeMap::new();
        for row in rows {
            let (entry_id, mark) = row?;
            marks.insert(entry_id, mark);
        }

        let latest: Option<String> =
            conn.query_row("SELECT MAX(updated_at) FROM word_marks", [], |row| {
                row.get(0)
            })?;

        Ok(MarksResponse {
            version: 2,
            updated_at: latest.unwrap_or_else(now_utc),
            marks,
        })
    }

    pub fn get_summary(&self) -> Result<Summary> {
        let conn = self.connect()?;
        let (entries, units, known, flagged): (i64, i64, i64, i64) = conn.query_row(
            r#"
            SELECT
              COUNT(*) AS entries,
              COUNT(DISTINCT unit_number) AS units,
              SUM(CASE WHEN COALESCE(m.known, 0) = 1 THEN 1 ELSE 0 END) AS known,
              SUM(CASE WHEN COALESCE(m.flagged, 0) = 1 THEN 1 ELSE 0 END) AS flagged
            FROM entries e
            LEFT JOIN word_marks m ON m.entry_id = e.entry_id
            WHERE e.book_code = ?
            "#,
            [&self.book_code],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
        )?;

        // "Unmarked" means neither known nor flagged, not just "missing row".
        // That distinction matters because clearing a mark deletes its row.
        let marked_any = self.count_marked_any(&conn)?;
        Ok(Summary {
            entries,
            units,
            known,
            flagged,
            unmarked: (entries - marked_any).max(0),
        })
    }

    fn count_marked_any(&self, conn: &Connection) -> Result<i64> {
        let count = conn.query_row(
            r#"
            SELECT COUNT(*)
            FROM entries e
            JOIN word_marks m ON m.entry_id = e.entry_id
            WHERE e.book_code = ? AND (m.known = 1 OR m.flagged = 1)
            "#,
            [&self.book_code],
            |row| row.get(0),
        )?;
        Ok(count)
    }

    pub fn list_units(&self) -> Result<Vec<UnitSummary>> {
        let conn = self.connect()?;
        let mut statement = conn.prepare(
            r#"
            SELECT
              u.number,
              u.header,
              u.title,
              COUNT(e.entry_id) AS entry_count,
              SUM(CASE WHEN COALESCE(m.known, 0) = 1 THEN 1 ELSE 0 END) AS known,
              SUM(CASE WHEN COALESCE(m.flagged, 0) = 1 THEN 1 ELSE 0 END) AS flagged,
              SUM(CASE WHEN m.entry_id IS NULL THEN 1 ELSE 0 END) AS unmarked
            FROM units u
            JOIN entries e
              ON e.book_code = u.book_code AND e.unit_number = u.number
            LEFT JOIN word_marks m ON m.entry_id = e.entry_id
            WHERE u.book_code = ?
            GROUP BY u.number, u.header, u.title
            ORDER BY u.number
            "#,
        )?;

        let rows = statement.query_map([&self.book_code], |row| {
            let header: String = row.get(1)?;
            let title: String = row.get(2)?;
            Ok(UnitSummary {
                number: row.get(0)?,
                title: short_title(&header).unwrap_or(title),
                header,
                entry_count: row.get(3)?,
                known: row.get(4)?,
                flagged: row.get(5)?,
                unmarked: row.get(6)?,
            })
        })?;

        collect_rows(rows)
    }

    pub fn list_entries(
        &self,
        unit: Option<i64>,
        state: &str,
        search: &str,
    ) -> Result<EntryListResponse> {
        if !STATE_VALUES.contains(&state) {
            bail!("state must be one of: {}", STATE_VALUES.join(", "));
        }

        // Dynamic SQL is kept narrow: only fixed snippets are appended, and all
        // user values still go through SQLite parameters.
        let mut clauses = vec!["e.book_code = ?".to_string()];
        let mut query_params = vec![Value::Text(self.book_code.clone())];

        if let Some(unit_number) = unit {
            clauses.push("e.unit_number = ?".to_string());
            query_params.push(Value::Integer(unit_number));
        }
        match state {
            "known" => clauses.push("COALESCE(m.known, 0) = 1".to_string()),
            "flagged" => clauses.push("COALESCE(m.flagged, 0) = 1".to_string()),
            "unmarked" => clauses.push("m.entry_id IS NULL".to_string()),
            _ => {}
        }
        let trimmed_search = search.trim();
        if !trimmed_search.is_empty() {
            clauses.push(
                r#"
                (
                  COALESCE(e.kanji, '') LIKE ?
                  OR COALESCE(e.reading, '') LIKE ?
                  OR COALESCE(e.headword_text, '') LIKE ?
                  OR COALESCE(e.meaning_en, '') LIKE ?
                  OR COALESCE(e.meaning_zh, '') LIKE ?
                  OR COALESCE(ex.text, '') LIKE ?
                  OR COALESCE(ex.translation_en, '') LIKE ?
                  OR COALESCE(ex.translation_zh, '') LIKE ?
                )
                "#
                .to_string(),
            );
            // The same search text is bound to each LIKE placeholder. Binding
            // instead of interpolating prevents user input from becoming SQL.
            for _ in 0..8 {
                query_params.push(Value::Text(format!("%{trimmed_search}%")));
            }
        }

        let conn = self.connect()?;
        let sql = format!(
            r#"
            SELECT DISTINCT
              e.entry_id, e.uuid, e.book_code, e.source_index, e.unit_number,
              u.header AS unit_header, e.kanji, e.reading, e.headword_text,
              e.verb_pattern, e.meaning_en, e.meaning_zh, e.sentence,
              e.explanation_md, e.word_clip, e.sentence_clip,
              m.known, m.flagged, m.updated_at AS mark_updated_at
            FROM entries e
            JOIN units u
              ON u.book_code = e.book_code AND u.number = e.unit_number
            LEFT JOIN word_marks m ON m.entry_id = e.entry_id
            LEFT JOIN entry_examples ex ON ex.entry_id = e.entry_id
            WHERE {}
            ORDER BY e.unit_number, e.position, e.source_index
            "#,
            clauses.join(" AND ")
        );

        let rows = self.query_entry_rows(&conn, &sql, query_params)?;
        let entry_ids = rows.iter().map(|row| row.entry_id).collect::<Vec<_>>();
        // Load examples in one follow-up query instead of one query per entry.
        // This keeps list rendering fast while still leaving the SQL readable.
        let examples = self.load_examples(&conn, &entry_ids)?;
        let items = rows
            .iter()
            .map(|row| self.serialize_entry(row, examples.get(&row.entry_id), false))
            .collect::<Vec<_>>();

        Ok(EntryListResponse {
            total: items.len(),
            items,
        })
    }

    pub fn get_entry(&self, entry_id: i64) -> Result<Option<EntryPayload>> {
        let conn = self.connect()?;
        let sql = r#"
            SELECT
              e.entry_id, e.uuid, e.book_code, e.source_index, e.unit_number,
              u.header AS unit_header, e.kanji, e.reading, e.headword_text,
              e.verb_pattern, e.meaning_en, e.meaning_zh, e.sentence,
              e.explanation_md, e.word_clip, e.sentence_clip,
              m.known, m.flagged, m.updated_at AS mark_updated_at
            FROM entries e
            JOIN units u
              ON u.book_code = e.book_code AND u.number = e.unit_number
            LEFT JOIN word_marks m ON m.entry_id = e.entry_id
            WHERE e.book_code = ? AND e.entry_id = ?
            "#;
        let rows = self.query_entry_rows(
            &conn,
            sql,
            vec![
                Value::Text(self.book_code.clone()),
                Value::Integer(entry_id),
            ],
        )?;
        let Some(row) = rows.first() else {
            return Ok(None);
        };

        let examples = self.load_examples(&conn, &[entry_id])?;
        Ok(Some(self.serialize_entry(
            row,
            examples.get(&entry_id),
            true,
        )))
    }

    fn query_entry_rows(
        &self,
        conn: &Connection,
        sql: &str,
        query_params: Vec<Value>,
    ) -> Result<Vec<EntryRow>> {
        let mut statement = conn.prepare(sql)?;
        let rows = statement.query_map(params_from_iter(query_params.iter()), |row| {
            Ok(EntryRow {
                entry_id: row.get(0)?,
                uuid: row.get(1)?,
                book_code: row.get(2)?,
                source_index: row.get(3)?,
                unit_number: row.get(4)?,
                unit_header: row.get(5)?,
                kanji: row.get(6)?,
                reading: row.get(7)?,
                headword_text: row.get(8)?,
                verb_pattern: row.get(9)?,
                meaning_en: row.get(10)?,
                meaning_zh: row.get(11)?,
                sentence: row.get(12)?,
                explanation_md: row.get(13)?,
                word_clip: row.get(14)?,
                sentence_clip: row.get(15)?,
                known: row.get(16)?,
                flagged: row.get(17)?,
                mark_updated_at: row.get(18)?,
            })
        })?;

        collect_rows(rows)
    }

    fn load_examples(
        &self,
        conn: &Connection,
        entry_ids: &[i64],
    ) -> Result<HashMap<i64, Vec<EntryExample>>> {
        if entry_ids.is_empty() {
            return Ok(HashMap::new());
        }
        // SQLite does not accept a Vec directly as one `IN (?)` parameter, so
        // we build exactly one placeholder per already-known numeric entry ID.
        let placeholders = vec!["?"; entry_ids.len()].join(",");
        let sql = format!(
            r#"
            SELECT entry_id, position, text, translation_en, translation_zh,
                   explanation_md, audio_clip
            FROM entry_examples
            WHERE entry_id IN ({placeholders})
            ORDER BY entry_id, position
            "#
        );
        let mut statement = conn.prepare(&sql)?;
        let rows = statement.query_map(params_from_iter(entry_ids.iter()), |row| {
            let entry_id: i64 = row.get(0)?;
            let audio_clip: Option<String> = row.get(6)?;
            Ok((
                entry_id,
                EntryExample {
                    position: row.get(1)?,
                    text: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
                    translation_en: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                    translation_zh: row.get::<_, Option<String>>(4)?.unwrap_or_default(),
                    explanation_md: row.get::<_, Option<String>>(5)?.unwrap_or_default(),
                    audio_url: self.audio_url(audio_clip.as_deref()),
                },
            ))
        })?;

        let mut by_entry: HashMap<i64, Vec<EntryExample>> = HashMap::new();
        for row in rows {
            let (entry_id, example) = row?;
            by_entry.entry(entry_id).or_default().push(example);
        }
        Ok(by_entry)
    }

    fn serialize_entry(
        &self,
        row: &EntryRow,
        examples: Option<&Vec<EntryExample>>,
        detail: bool,
    ) -> EntryPayload {
        // Work with slices here so the rest of the function can treat "no
        // examples" and "empty examples Vec" the same way without cloning.
        let examples_slice = examples.map(Vec::as_slice).unwrap_or(&[]);
        let main_example = examples_slice.iter().find(|example| example.position == 0);

        // The current schema stores the main sentence in entry_examples at
        // position 0. The legacy entries.sentence column stays as a fallback so
        // the service can survive mid-migration databases.
        let sentence = main_example
            .map(|example| example.text.clone())
            .or_else(|| row.sentence.clone())
            .unwrap_or_default();
        let sentence_audio_url = main_example
            .and_then(|example| example.audio_url.clone())
            .or_else(|| self.audio_url(row.sentence_clip.as_deref()));

        EntryPayload {
            entry_id: row.entry_id,
            source_index: row.source_index,
            uuid: row.uuid.clone(),
            book_code: row.book_code.clone(),
            unit: UnitRef {
                number: row.unit_number,
                header: row.unit_header.clone(),
                title: short_title(&row.unit_header).unwrap_or_default(),
            },
            kanji: if row.headword_text.is_empty() {
                row.kanji.clone()
            } else {
                row.headword_text.clone()
            },
            reading: row.reading.clone().unwrap_or_default(),
            verb_pattern: row.verb_pattern.clone().unwrap_or_default(),
            meaning_en: row.meaning_en.clone().unwrap_or_default(),
            meaning_zh: row.meaning_zh.clone().unwrap_or_default(),
            sentence,
            sentence_translation_en: main_example
                .map(|example| example.translation_en.clone())
                .unwrap_or_default(),
            sentence_translation_zh: main_example
                .map(|example| example.translation_zh.clone())
                .unwrap_or_default(),
            word_audio_url: self.audio_url(row.word_clip.as_deref()),
            sentence_audio_url,
            mark: MarkState {
                known: row.known.map(int_to_bool).unwrap_or(false),
                flagged: row.flagged.map(int_to_bool).unwrap_or(false),
                updated_at: row.mark_updated_at.clone(),
            },
            examples: detail.then(|| examples_slice.to_vec()),
            explanation_md: detail.then(|| {
                main_example
                    .map(|example| example.explanation_md.clone())
                    .filter(|value| !value.is_empty())
                    .or_else(|| row.explanation_md.clone())
                    .unwrap_or_default()
            }),
        }
    }

    pub fn audio_url(&self, clip_path: Option<&str>) -> Option<String> {
        // Returning Option is deliberate: bad or missing DB paths simply become
        // absent audio URLs instead of crashing the whole entry response.
        let normalized = normalize_clip_path(clip_path?, true)?;
        let resolved = self.resolve_audio_path(&normalized)?;
        if !resolved.is_file() {
            return None;
        }
        Some(format!("/audio/{normalized}"))
    }

    pub fn resolve_audio_path(&self, request_path: &str) -> Option<PathBuf> {
        let normalized = normalize_clip_path(request_path, false)?;
        // Stored paths start with `clips/...`; the configured clips_dir points
        // at the `clips` folder itself, so joining from its parent preserves the
        // stored relative path exactly.
        let clips_parent = self.clips_dir.parent().unwrap_or_else(|| Path::new("."));
        Some(clips_parent.join(normalized))
    }

    pub fn set_mark(&self, entry_id: i64, known: bool, flagged: bool) -> Result<()> {
        // Mark writes go through a temporary DB copy because stale WAL sidecars
        // on this Windows workspace have made direct writes fragile. The mutex
        // makes that copy-mutate-copy-back sequence one-at-a-time.
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
            let exists: Option<i64> = conn
                .query_row(
                    "SELECT 1 FROM entries WHERE book_code = ? AND entry_id = ?",
                    params![&self.book_code, entry_id],
                    |row| row.get(0),
                )
                .optional()?;
            if exists.is_none() {
                bail!("unknown entry_id");
            }

            if !known && !flagged {
                conn.execute("DELETE FROM word_marks WHERE entry_id = ?", [entry_id])?;
            } else {
                conn.execute(
                    r#"
                    INSERT INTO word_marks(entry_id, known, flagged, updated_at)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(entry_id) DO UPDATE SET
                      known = excluded.known,
                      flagged = excluded.flagged,
                      updated_at = excluded.updated_at
                    "#,
                    params![
                        entry_id,
                        bool_to_int(known),
                        bool_to_int(flagged),
                        now_utc()
                    ],
                )?;
            }
        }

        fs::copy(&temp_db, &self.db_path)?;
        Ok(())
    }

    pub fn ensure_example_audio<F>(
        &self,
        entry_id: i64,
        position: i64,
        generated_dir: &str,
        synthesize: F,
    ) -> Result<AudioGenerationResponse>
    where
        F: FnOnce(&str) -> Result<Vec<u8>>,
    {
        let _guard = self
            .write_lock
            .lock()
            .expect("audio write lock should not be poisoned");

        let conn = self.connect()?;
        let row: Option<(String, Option<String>)> = conn
            .query_row(
                r#"
                SELECT ex.text, ex.audio_clip
                FROM entry_examples ex
                JOIN entries e ON e.entry_id = ex.entry_id
                WHERE e.book_code = ? AND ex.entry_id = ? AND ex.position = ?
                "#,
                params![&self.book_code, entry_id, position],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;
        drop(conn);

        let Some((text, current_clip)) = row else {
            bail!("unknown example");
        };
        let sentence = clean_sentence_text_for_tts(&text);
        if sentence.is_empty() {
            bail!("empty sentence");
        }

        if let Some(current) = current_clip.as_deref()
            && let Some(existing_path) = self.resolve_audio_path(current)
            && existing_path.exists()
            && let Some(audio_url) = self.audio_url(Some(current))
        {
            // Reuse is important for cost and speed. If SQLite points at a real
            // file, the endpoint returns it without calling TTS again.
            return Ok(AudioGenerationResponse {
                ok: true,
                audio_url,
                generated: false,
            });
        }

        let generated_rel_path = generated_sentence_clip_path(generated_dir, entry_id, position)?;
        let final_path = self
            .resolve_audio_path(&generated_rel_path)
            .context("generated audio path should resolve inside clips")?;
        // Production passes the real Edge TTS synthesizer; tests pass a tiny
        // fake closure. That keeps path and DB behavior testable without
        // depending on the network.
        let audio_bytes = synthesize(&sentence)?;
        if audio_bytes.is_empty() {
            bail!("TTS returned no audio bytes");
        }
        write_file_atomically(&final_path, &audio_bytes)?;
        self.update_example_audio_clip(entry_id, position, &generated_rel_path, generated_dir)?;
        let generated_url = self
            .audio_url(Some(&generated_rel_path))
            .context("generated audio path should be servable")?;

        Ok(AudioGenerationResponse {
            ok: true,
            audio_url: generated_url,
            generated: true,
        })
    }

    fn update_example_audio_clip(
        &self,
        entry_id: i64,
        position: i64,
        clip_path: &str,
        generated_dir: &str,
    ) -> Result<()> {
        let temp_dir = TempDir::with_prefix("n2_word_audio_")?;
        let temp_db = temp_dir.path().join(
            self.db_path
                .file_name()
                .context("database path should have a filename")?,
        );
        fs::copy(&self.db_path, &temp_db)?;

        {
            // Match set_mark's copy-mutate-copy-back pattern so audio metadata
            // writes have the same Windows-safe behavior as mark writes.
            let conn = Connection::open(&temp_db)?;
            conn.execute_batch(
                r#"
                PRAGMA foreign_keys = ON;
                PRAGMA journal_mode = DELETE;
                CREATE TABLE IF NOT EXISTS word_service_settings (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                "#,
            )?;
            let changed = conn.execute(
                r#"
                UPDATE entry_examples
                SET audio_clip = ?
                WHERE entry_id = ? AND position = ?
                "#,
                params![clip_path, entry_id, position],
            )?;
            if changed != 1 {
                bail!("unknown example");
            }
            conn.execute(
                r#"
                INSERT INTO word_service_settings(key, value, updated_at)
                VALUES('generated_sentence_audio_dir', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  value = excluded.value,
                  updated_at = excluded.updated_at
                "#,
                params![normalize_generated_audio_dir(generated_dir)?, now_utc()],
            )?;
        }

        fs::copy(&temp_db, &self.db_path)?;
        Ok(())
    }
}

fn collect_rows<T>(
    rows: rusqlite::MappedRows<'_, impl FnMut(&rusqlite::Row<'_>) -> rusqlite::Result<T>>,
) -> Result<Vec<T>> {
    // rusqlite iterators yield Result<T> for each row. This helper converts
    // "many row results" into the more common Result<Vec<T>> shape.
    let mut values = Vec::new();
    for row in rows {
        values.push(row?);
    }
    Ok(values)
}

fn normalize_clip_path(value: &str, allow_legacy_output_prefix: bool) -> Option<String> {
    let mut normalized = value.replace('\\', "/").trim_start_matches('/').to_string();
    if allow_legacy_output_prefix && let Some(stripped) = normalized.strip_prefix("output/clips/") {
        normalized = format!("clips/{stripped}");
    }
    if !normalized.starts_with("clips/") {
        return None;
    }

    // Reject path traversal and Windows drive tricks before joining with the
    // real clips parent. This is a simple lexical guard; no filesystem access is
    // needed to decide whether a requested clip path is allowed.
    for part in normalized.split('/') {
        if part.is_empty() || part == "." || part == ".." || part.contains(':') {
            return None;
        }
    }
    Some(normalized)
}

fn normalize_generated_audio_dir(value: &str) -> Result<String> {
    // Accept a friendly short value like `generated_sentences/edge_tts`, but
    // normalize it to the same `clips/...` shape that the rest of the service
    // stores and serves.
    let mut normalized = value.replace('\\', "/").trim_matches('/').to_string();
    if normalized.is_empty() {
        bail!("generated audio directory cannot be empty");
    }
    if let Some(stripped) = normalized.strip_prefix("output/clips/") {
        normalized = format!("clips/{stripped}");
    } else if !normalized.starts_with("clips/") {
        normalized = format!("clips/{normalized}");
    }
    normalize_clip_path(&normalized, false)
        .filter(|path| !path.ends_with(".mp3"))
        .context("generated audio directory must stay inside clips")
}

fn generated_sentence_clip_path(
    generated_dir: &str,
    entry_id: i64,
    position: i64,
) -> Result<String> {
    // The deterministic filename makes regeneration idempotent and easy to
    // audit by entry ID and sentence position.
    let dir = normalize_generated_audio_dir(generated_dir)?;
    Ok(format!("{dir}/word{entry_id}_sentence{position}.mp3"))
}

/// Normalize OCR/study notation into a sentence Edge TTS can read naturally.
///
/// The database often keeps textbook shorthand such as `｛な／の｝`, leading
/// sense indexes like `②`, and furigana in parentheses. Those are useful for a
/// human reader, but the TTS request should contain one plain pronounceable
/// sentence. The rule is intentionally conservative and local: when the book
/// offers alternatives, choose the first option instead of trying to invent a
/// new sentence.
pub fn clean_sentence_text_for_tts(raw: &str) -> String {
    let mut text = raw
        .replace('｛', "{")
        .replace('｝', "}")
        .replace('（', "(")
        .replace('）', ")")
        .replace('\u{3000}', " ");

    text = strip_leading_noise(&text);
    text = replace_choice_groups(&text, '{', '}', true);
    text = strip_leading_noise(&text);
    text = strip_leading_example_marker(&text);
    text = replace_choice_groups(&text, '(', ')', false);
    text = collapse_slash_ellipsis_lists(&text);
    text = text
        .replace("……", "")
        .replace('…', "")
        .replace("...", "")
        .replace('※', "")
        .replace("。 ・", "。")
        .replace("」 ・", "」");
    text = text.chars().filter(|ch| !is_circled_number(*ch)).collect();
    text = collapse_sentence_spaces(&text);

    // Some rows become empty after removing pure index markers. Keeping this as
    // a final pass lets the normal empty-sentence guard report them cleanly.
    strip_leading_noise(&text)
}

fn replace_choice_groups(text: &str, open: char, close: char, keep_plain_group: bool) -> String {
    let mut output = String::new();
    let mut rest = text;

    while let Some(open_at) = rest.find(open) {
        output.push_str(&rest[..open_at]);
        let after_open = &rest[open_at + open.len_utf8()..];
        let Some(close_at) = find_matching_close(after_open, open, close) else {
            output.push(open);
            rest = after_open;
            continue;
        };

        let group = &after_open[..close_at];
        let replacement = if group_has_choice(group) {
            first_choice(group)
        } else if keep_plain_group {
            clean_choice_fragment(group)
        } else {
            String::new()
        };
        if !replacement.is_empty() && output.ends_with(char::is_whitespace) {
            output.pop();
        }
        output.push_str(&replacement);
        rest = &after_open[close_at + close.len_utf8()..];
        if !replacement.is_empty() {
            rest = rest.trim_start();
        }
    }

    output.push_str(rest);
    output
}

fn find_matching_close(text: &str, open: char, close: char) -> Option<usize> {
    let mut depth = 0usize;
    for (index, ch) in text.char_indices() {
        if ch == open {
            depth += 1;
        } else if ch == close {
            if depth == 0 {
                return Some(index);
            }
            depth -= 1;
        }
    }
    None
}

fn group_has_choice(value: &str) -> bool {
    value.contains('/') || value.contains('／') || value.contains('…')
}

fn first_choice(value: &str) -> String {
    let first = value
        .split(|ch| ch == '/' || ch == '／')
        .next()
        .unwrap_or(value);
    clean_choice_fragment(first)
}

fn clean_choice_fragment(value: &str) -> String {
    value
        .replace("……", "")
        .replace('…', "")
        .replace("...", "")
        .trim()
        .to_string()
}

fn collapse_slash_ellipsis_lists(text: &str) -> String {
    let mut output = text.to_string();
    for ellipsis in ["……", "…", "..."] {
        while let Some(ellipsis_at) = output.find(ellipsis) {
            let before = &output[..ellipsis_at];
            let Some(slash_at) = before.rfind(|ch| ch == '/' || ch == '／') else {
                break;
            };
            let list_start = find_choice_list_start(before, slash_at);
            let remove_start = before[list_start..]
                .find(|ch| ch == '/' || ch == '／')
                .map(|offset| list_start + offset)
                .unwrap_or(slash_at);
            output.replace_range(remove_start..ellipsis_at + ellipsis.len(), "");
        }
    }
    output
}

fn find_choice_list_start(text: &str, slash_at: usize) -> usize {
    text[..slash_at]
        .char_indices()
        .rev()
        .find(|(_, ch)| {
            matches!(
                ch,
                '。' | '、' | '「' | '」' | ' ' | '\t' | '\n' | '・' | '(' | ')' | '[' | ']'
            )
        })
        .map(|(index, ch)| index + ch.len_utf8())
        .unwrap_or(0)
}

fn strip_leading_noise(raw: &str) -> String {
    let mut text = raw.trim_start().to_string();

    loop {
        let before = text.clone();
        text = strip_leading_square_metadata(&text);
        text = strip_leading_label_colon(&text);
        text = text
            .trim_start_matches(|ch: char| {
                ch.is_whitespace()
                    || is_circled_number(ch)
                    || matches!(ch, '・' | '･' | '-' | 'ー' | '※')
            })
            .trim_start()
            .to_string();
        if text == before {
            break;
        }
    }

    text.trim().to_string()
}

fn strip_leading_square_metadata(raw: &str) -> String {
    let text = raw.trim_start();
    if !text.starts_with('[') {
        return text.to_string();
    }

    let metadata_end = text
        .find('・')
        .and_then(|bullet_at| text[..bullet_at].rfind(']'))
        .or_else(|| text.find(']').filter(|end| *end <= 24));

    match metadata_end {
        Some(end) => text[end + 1..].trim_start().to_string(),
        None => text.to_string(),
    }
}

fn strip_leading_label_colon(raw: &str) -> String {
    let text = raw.trim_start();
    let Some(colon_at) = text.find(':') else {
        return text.to_string();
    };
    if colon_at <= 18 {
        return text[colon_at + 1..].trim_start().to_string();
    }
    text.to_string()
}

fn strip_leading_example_marker(raw: &str) -> String {
    let text = raw.trim_start();
    for marker in ["(例.", "(例:", "(例)"] {
        if let Some(rest) = text.strip_prefix(marker) {
            return rest.trim().trim_end_matches(')').trim().to_string();
        }
    }
    text.to_string()
}

fn is_circled_number(ch: char) -> bool {
    matches!(
        ch,
        '①' | '②'
            | '③'
            | '④'
            | '⑤'
            | '⑥'
            | '⑦'
            | '⑧'
            | '⑨'
            | '⑩'
            | '⑪'
            | '⑫'
            | '⑬'
            | '⑭'
            | '⑮'
            | '⑯'
            | '⑰'
            | '⑱'
            | '⑲'
            | '⑳'
    )
}

fn collapse_sentence_spaces(raw: &str) -> String {
    let mut text = raw.split_whitespace().collect::<Vec<_>>().join(" ");
    for particle in [
        "を", "が", "に", "の", "へ", "と", "で", "は", "も", "から", "まで", "より",
    ] {
        text = text.replace(&format!(" {particle}"), particle);
    }
    for punctuation in ["。", "、", "」", "』", "）", ")", "！", "？"] {
        text = text.replace(&format!(" {punctuation}"), punctuation);
    }
    for punctuation in ["「", "『", "（", "("] {
        text = text.replace(&format!("{punctuation} "), punctuation);
    }
    text.trim().to_string()
}

fn write_file_atomically(path: &Path, data: &[u8]) -> Result<()> {
    let parent = path
        .parent()
        .context("generated audio path should have a parent directory")?;
    fs::create_dir_all(parent)?;
    let tmp_path = path.with_file_name(format!(
        ".{}.tmp",
        path.file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("generated_sentence.mp3")
    ));
    if tmp_path.exists() {
        fs::remove_file(&tmp_path)?;
    }
    // Write a sibling temp file first so an interrupted generation never leaves
    // the final mp3 path pointing at a partial file.
    fs::write(&tmp_path, data)?;
    if path.exists() {
        fs::remove_file(path)?;
    }
    fs::rename(&tmp_path, path)?;
    Ok(())
}

fn short_title(header: &str) -> Option<String> {
    // Headers look like "Unit 01 名詞 A & ...". The UI wants the compact left
    // side, so this strips the leading Unit number and any secondary column.
    let mut parts = header.splitn(3, ' ');
    let first = parts.next()?;
    let second = parts.next();
    let rest = parts.next();
    let without_unit = if first == "Unit" && second.is_some() {
        rest.unwrap_or("")
    } else {
        header
    };
    let before_column = without_unit
        .split('&')
        .next()
        .unwrap_or(without_unit)
        .trim()
        .to_string();
    if before_column.is_empty() {
        None
    } else {
        Some(before_column)
    }
}

fn int_to_bool(value: i64) -> bool {
    value != 0
}

fn bool_to_int(value: bool) -> i64 {
    if value { 1 } else { 0 }
}

fn now_utc() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%S.%6fZ").to_string()
}
