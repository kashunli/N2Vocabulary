use crate::models::{
    AudioGenerationResponse, BookSummary, EntryExample, EntryListResponse, EntryPayload,
    EntrySourceNote, FlaggedAudioExportResponse, MarkState, MarksResponse,
    StarredSentenceListResponse, StarredSentencePayload, Summary, UnitRef, UnitSummary,
};
use anyhow::{Context, Result, bail};
use chrono::Utc;
use rusqlite::types::Value;
use rusqlite::{Connection, OptionalExtension, params, params_from_iter};
use std::collections::{BTreeMap, HashMap};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;
use tempfile::TempDir;

mod audio_export;
mod paths;
mod search;
mod text;

use audio_export::{
    FlaggedAudioExportItem, ensure_silence_clip, run_ffmpeg, write_flagged_audio_concat_list,
};
use paths::{
    generated_sentence_clip_path, generated_word_clip_path, normalize_clip_path,
    normalize_generated_audio_dir,
};
use search::{search_matches, search_terms};
use text::word_text_for_tts;

pub use text::clean_sentence_text_for_tts;

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
    item_id: i64,
    uuid: String,
    book_code: String,
    source_index: i64,
    unit_number: i64,
    unit_header: String,
    unit_title: String,
    kanji: String,
    reading: Option<String>,
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

/// The audio export works from concrete clip paths rather than serialized entry
/// payloads. Keeping this small type private makes the export contract obvious:
/// one flagged word contributes exactly word audio, then sentence audio.
#[derive(Debug)]
struct FlaggedAudioExportItem {
    source_index: i64,
    word_clip: String,
    sentence_clip: String,
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

    pub fn for_book(&self, book_code: &str) -> Self {
        Self {
            db_path: self.db_path.clone(),
            clips_dir: self.clips_dir.clone(),
            book_code: normalize_book_code(book_code),
            write_lock: self.write_lock.clone(),
        }
    }

    pub fn ensure_ready(&self) -> Result<()> {
        if !self.db_path.exists() {
            bail!("Database not found: {}", self.db_path.display());
        }
        let conn = self.connect()?;
        self.ensure_sentence_star_schema(&conn)?;
        self.ensure_source_provenance_schema(&conn)?;
        self.ensure_example_metadata_schema(&conn)?;
        // rusqlite separates row-returning statements from mutation-style
        // execute calls. query_row is the right startup probe for SELECT.
        conn.query_row("SELECT 1 FROM book_entries LIMIT 1", [], |_| Ok(()))?;
        conn.query_row("SELECT 1 FROM vocabulary_items LIMIT 1", [], |_| Ok(()))?;
        Ok(())
    }

    pub fn list_books(&self) -> Result<Vec<BookSummary>> {
        let conn = self.connect()?;
        let mut statement = conn.prepare(
            r#"
            SELECT
              b.code,
              b.title,
              (
                SELECT COUNT(*)
                FROM book_entries be
                WHERE be.book_code = b.code
              ) AS entries,
              (
                SELECT COUNT(DISTINCT be.unit_number)
                FROM book_entries be
                WHERE be.book_code = b.code
              ) AS units
            FROM books b
            WHERE EXISTS (
              SELECT 1
              FROM book_entries be
              WHERE be.book_code = b.code
            )
            ORDER BY b.code
            "#,
        )?;
        let rows = statement.query_map([], |row| {
            Ok(BookSummary {
                code: row.get(0)?,
                title: row.get(1)?,
                entries: row.get(2)?,
                units: row.get(3)?,
            })
        })?;
        collect_rows(rows)
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

    fn ensure_sentence_star_schema(&self, conn: &Connection) -> Result<()> {
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS sentence_stars (
              entry_id INTEGER NOT NULL,
              position INTEGER NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(entry_id, position),
              FOREIGN KEY(entry_id, position)
                REFERENCES entry_examples(entry_id, position)
                ON DELETE CASCADE
            );
            "#,
        )?;
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

    pub fn get_marks(&self) -> Result<MarksResponse> {
        let conn = self.connect()?;
        let mut statement = conn.prepare(
            r#"
            SELECT be.entry_id, im.known, im.flagged, im.updated_at
            FROM book_entries be
            JOIN item_marks im ON im.item_id = be.item_id
            ORDER BY be.entry_id
            "#,
        )?;
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
            conn.query_row("SELECT MAX(updated_at) FROM item_marks", [], |row| {
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
            FROM book_entries be
            LEFT JOIN item_marks m ON m.item_id = be.item_id
            WHERE be.book_code = ?
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
            FROM book_entries be
            JOIN item_marks m ON m.item_id = be.item_id
            WHERE be.book_code = ? AND (m.known = 1 OR m.flagged = 1)
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
              COUNT(be.entry_id) AS entry_count,
              SUM(CASE WHEN COALESCE(m.known, 0) = 1 THEN 1 ELSE 0 END) AS known,
              SUM(CASE WHEN COALESCE(m.flagged, 0) = 1 THEN 1 ELSE 0 END) AS flagged,
              SUM(CASE WHEN m.item_id IS NULL THEN 1 ELSE 0 END) AS unmarked
            FROM units u
            JOIN book_entries be
              ON be.book_code = u.book_code AND be.unit_number = u.number
            LEFT JOIN item_marks m ON m.item_id = be.item_id
            WHERE u.book_code = ?
            GROUP BY u.number, u.header, u.title
            ORDER BY u.number
            "#,
        )?;

        let rows = statement.query_map([&self.book_code], |row| {
            let title: String = row.get(2)?;
            Ok(UnitSummary {
                number: row.get(0)?,
                header: row.get(1)?,
                title,
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
        let mut clauses = vec!["be.book_code = ?".to_string()];
        let mut query_params = vec![Value::Text(self.book_code.clone())];

        if let Some(unit_number) = unit {
            clauses.push("be.unit_number = ?".to_string());
            query_params.push(Value::Integer(unit_number));
        }
        match state {
            "known" => clauses.push("COALESCE(m.known, 0) = 1".to_string()),
            "flagged" => clauses.push("COALESCE(m.flagged, 0) = 1".to_string()),
            "unmarked" => clauses.push("m.item_id IS NULL".to_string()),
            _ => {}
        }
        let trimmed_search = search.trim();
        if !trimmed_search.is_empty() {
            let terms = search_terms(trimmed_search);
            let mut search_clauses = vec![
                r#"
                COALESCE(v.kanji, '') LIKE ?
                OR COALESCE(v.reading, '') LIKE ?
                OR COALESCE(v.meaning_en, '') LIKE ?
                OR COALESCE(v.meaning_zh, '') LIKE ?
                OR COALESCE(ex.text, '') LIKE ?
                OR COALESCE(ex.reading, '') LIKE ?
                OR COALESCE(ex.translation_en, '') LIKE ?
                OR COALESCE(ex.translation_zh, '') LIKE ?
                "#
                .to_string(),
            ];
            // The same search text is bound to each LIKE placeholder. Binding
            // instead of interpolating prevents user input from becoming SQL.
            for _ in 0..8 {
                query_params.push(Value::Text(format!("%{}%", terms[0])));
            }
            for term in terms.iter().skip(1) {
                // Japanese verbs often appear in examples as inflected forms:
                // searching `覆う` should still find sentences with `覆われる`
                // or `覆った`. Keep the wider stem match limited to examples so
                // word/meaning searches remain predictable.
                search_clauses.push("COALESCE(ex.text, '') LIKE ?".to_string());
                query_params.push(Value::Text(format!("%{term}%")));
            }
            clauses.push(format!("({})", search_clauses.join(" OR ")));
        }

        let conn = self.connect()?;
        let sql = format!(
            r#"
            SELECT DISTINCT
              be.entry_id, be.item_id, be.uuid, be.book_code, be.source_index, be.unit_number,
              u.header AS unit_header, u.title AS unit_title, v.kanji, v.reading,
              v.verb_pattern, v.meaning_en, v.meaning_zh, be.sentence,
              COALESCE(be.explanation_md, v.explanation_md) AS explanation_md,
              v.word_clip, be.sentence_clip,
              m.known, m.flagged, m.updated_at AS mark_updated_at
            FROM book_entries be
            JOIN vocabulary_items v ON v.item_id = be.item_id
            JOIN units u
              ON u.book_code = be.book_code AND u.number = be.unit_number
            LEFT JOIN item_marks m ON m.item_id = be.item_id
            LEFT JOIN item_examples ex ON ex.item_id = be.item_id
            WHERE {}
            ORDER BY be.unit_number, be.position, be.source_index
            "#,
            clauses.join(" AND ")
        );

        let rows = self.query_entry_rows(&conn, &sql, query_params)?;
        let item_ids = rows.iter().map(|row| row.item_id).collect::<Vec<_>>();
        // Load examples in one follow-up query instead of one query per entry.
        // This keeps list rendering fast while still leaving the SQL readable.
        let examples = self.load_examples(&conn, &item_ids)?;
        let items = rows
            .iter()
            .map(|row| {
                let row_examples = examples.get(&row.item_id);
                self.serialize_entry(
                    row,
                    row_examples,
                    false,
                    search_matches(row_examples, &search_terms(trimmed_search)),
                    None,
                )
            })
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
              be.entry_id, be.item_id, be.uuid, be.book_code, be.source_index, be.unit_number,
              u.header AS unit_header, u.title AS unit_title, v.kanji, v.reading,
              v.verb_pattern, v.meaning_en, v.meaning_zh, be.sentence,
              COALESCE(be.explanation_md, v.explanation_md) AS explanation_md,
              v.word_clip, be.sentence_clip,
              m.known, m.flagged, m.updated_at AS mark_updated_at
            FROM book_entries be
            JOIN vocabulary_items v ON v.item_id = be.item_id
            JOIN units u
              ON u.book_code = be.book_code AND u.number = be.unit_number
            LEFT JOIN item_marks m ON m.item_id = be.item_id
            WHERE be.book_code = ? AND be.entry_id = ?
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

        let examples = self.load_examples(&conn, &[row.item_id])?;
        let source_notes = self.load_source_notes(&conn, row.item_id)?;
        Ok(Some(self.serialize_entry(
            row,
            examples.get(&row.item_id),
            true,
            None,
            Some(source_notes),
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
                item_id: row.get(1)?,
                uuid: row.get(2)?,
                book_code: row.get(3)?,
                source_index: row.get(4)?,
                unit_number: row.get(5)?,
                unit_header: row.get(6)?,
                unit_title: row.get(7)?,
                kanji: row.get(8)?,
                reading: row.get(9)?,
                verb_pattern: row.get(10)?,
                meaning_en: row.get(11)?,
                meaning_zh: row.get(12)?,
                sentence: row.get(13)?,
                explanation_md: row.get(14)?,
                word_clip: row.get(15)?,
                sentence_clip: row.get(16)?,
                known: row.get(17)?,
                flagged: row.get(18)?,
                mark_updated_at: row.get(19)?,
            })
        })?;

        collect_rows(rows)
    }

    fn load_examples(
        &self,
        conn: &Connection,
        item_ids: &[i64],
    ) -> Result<HashMap<i64, Vec<EntryExample>>> {
        if item_ids.is_empty() {
            return Ok(HashMap::new());
        }
        // SQLite does not accept a Vec directly as one `IN (?)` parameter, so
        // we build exactly one placeholder per already-known numeric entry ID.
        let placeholders = vec!["?"; item_ids.len()].join(",");
        let sql = format!(
            r#"
            SELECT ex.item_id, ex.position, ex.kind, text, reading, translation_en,
                   translation_zh, explanation_md, audio_clip, ex.category,
                   CASE WHEN s.item_id IS NULL THEN 0 ELSE 1 END AS starred,
                   (
                     SELECT p.source_book_code FROM item_example_sources p
                     WHERE p.item_id = ex.item_id AND p.position = ex.position
                     ORDER BY p.source_book_code, p.source_index LIMIT 1
                   ) AS source_book_code,
                   (
                     SELECT p.source_index FROM item_example_sources p
                     WHERE p.item_id = ex.item_id AND p.position = ex.position
                     ORDER BY p.source_book_code, p.source_index LIMIT 1
                   ) AS source_index
            FROM item_examples ex
            LEFT JOIN item_sentence_stars s
              ON s.item_id = ex.item_id AND s.position = ex.position
            WHERE ex.item_id IN ({placeholders})
            ORDER BY ex.item_id, ex.position
            "#
        );
        let mut statement = conn.prepare(&sql)?;
        let rows = statement.query_map(params_from_iter(item_ids.iter()), |row| {
            let item_id: i64 = row.get(0)?;
            let audio_clip: Option<String> = row.get(8)?;
            Ok((
                item_id,
                EntryExample {
                    position: row.get(1)?,
                    kind: row
                        .get::<_, Option<String>>(2)?
                        .unwrap_or_else(|| "example_sentence".to_string()),
                    text: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                    reading: row.get::<_, Option<String>>(4)?.unwrap_or_default(),
                    translation_en: row.get::<_, Option<String>>(5)?.unwrap_or_default(),
                    translation_zh: row.get::<_, Option<String>>(6)?.unwrap_or_default(),
                    explanation_md: row.get::<_, Option<String>>(7)?.unwrap_or_default(),
                    audio_url: self.audio_url(audio_clip.as_deref()),
                    category: row.get(9)?,
                    starred: int_to_bool(row.get(10)?),
                    source_book_code: row.get(11)?,
                    source_index: row.get(12)?,
                },
            ))
        })?;

        let mut by_entry: HashMap<i64, Vec<EntryExample>> = HashMap::new();
        for row in rows {
            let (item_id, example) = row?;
            by_entry.entry(item_id).or_default().push(example);
        }
        Ok(by_entry)
    }

    fn load_source_notes(&self, conn: &Connection, item_id: i64) -> Result<Vec<EntrySourceNote>> {
        let mut statement = conn.prepare(
            r#"
            SELECT source_book_code, source_index, source_reading,
                   source_meaning_en, source_meaning_zh, source_explanation_md
            FROM item_source_notes
            WHERE item_id = ?
            ORDER BY source_book_code, source_index
            "#,
        )?;
        let rows = statement.query_map([item_id], |row| {
            Ok(EntrySourceNote {
                source_book_code: row.get(0)?,
                source_index: row.get(1)?,
                reading: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
                meaning_en: row.get::<_, Option<String>>(3)?.unwrap_or_default(),
                meaning_zh: row.get::<_, Option<String>>(4)?.unwrap_or_default(),
                explanation_md: row.get::<_, Option<String>>(5)?.unwrap_or_default(),
            })
        })?;
        collect_rows(rows)
    }

    fn serialize_entry(
        &self,
        row: &EntryRow,
        examples: Option<&Vec<EntryExample>>,
        detail: bool,
        search_matches: Option<Vec<EntryExample>>,
        source_notes: Option<Vec<EntrySourceNote>>,
    ) -> EntryPayload {
        // Work with slices here so the rest of the function can treat "no
        // examples" and "empty examples Vec" the same way without cloning.
        let examples_slice = examples.map(Vec::as_slice).unwrap_or(&[]);
        let main_example = examples_slice
            .iter()
            .find(|example| example.kind == "main_sentence")
            .or_else(|| examples_slice.iter().find(|example| example.position == 0));

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
                title: row.unit_title.clone(),
            },
            kanji: row.kanji.clone(),
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
            sentence_starred: main_example.map(|example| example.starred).unwrap_or(false),
            word_audio_url: self.audio_url(row.word_clip.as_deref()),
            sentence_audio_url,
            mark: MarkState {
                known: row.known.map(int_to_bool).unwrap_or(false),
                flagged: row.flagged.map(int_to_bool).unwrap_or(false),
                updated_at: row.mark_updated_at.clone(),
            },
            // Card view already has dedicated top-level fields for the main
            // sentence. Keep extra examples in the list payload so related
            // terms stored in entry_examples positions 1+ can render on cards,
            // while detail view still receives the complete example set.
            examples: if detail {
                Some(examples_slice.to_vec())
            } else {
                let extra_examples = examples_slice
                    .iter()
                    .filter(|example| example.position > 0)
                    .cloned()
                    .collect::<Vec<_>>();
                (!extra_examples.is_empty()).then_some(extra_examples)
            },
            source_notes: detail.then(|| source_notes.unwrap_or_default()),
            search_matches,
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

        copy_database_back_with_retry(&temp_db, &self.db_path)?;
        Ok(())
    }

    pub fn list_starred_sentences(&self, unit: Option<i64>) -> Result<StarredSentenceListResponse> {
        let conn = self.connect()?;
        self.ensure_sentence_star_schema(&conn)?;

        let mut query_params = vec![Value::Text(self.book_code.clone())];
        let unit_clause = if let Some(unit_number) = unit {
            query_params.push(Value::Integer(unit_number));
            "AND be.unit_number = ?"
        } else {
            ""
        };

        let sql = format!(
            r#"
            SELECT
              be.entry_id, ex.position, be.source_index, be.unit_number,
              u.header, u.title, v.kanji, v.reading,
              v.meaning_en, v.meaning_zh, ex.text, ex.translation_en,
              ex.translation_zh, ex.explanation_md, ex.audio_clip,
              v.word_clip, s.updated_at
            FROM item_sentence_stars s
            JOIN item_examples ex
              ON ex.item_id = s.item_id AND ex.position = s.position
            JOIN book_entries be ON be.item_id = ex.item_id
            JOIN vocabulary_items v ON v.item_id = be.item_id
            JOIN units u
              ON u.book_code = be.book_code AND u.number = be.unit_number
            WHERE be.book_code = ? {unit_clause}
            ORDER BY be.unit_number, be.position, ex.position, be.source_index
            "#
        );

        let mut statement = conn.prepare(&sql)?;
        let rows = statement.query_map(params_from_iter(query_params.iter()), |row| {
            let unit_header: String = row.get(4)?;
            let unit_title: String = row.get(5)?;
            let kanji: String = row.get(6)?;
            let audio_clip: Option<String> = row.get(14)?;
            let word_clip: Option<String> = row.get(15)?;
            Ok(StarredSentencePayload {
                entry_id: row.get(0)?,
                position: row.get(1)?,
                source_index: row.get(2)?,
                unit: UnitRef {
                    number: row.get(3)?,
                    header: unit_header.clone(),
                    title: unit_title,
                },
                word: kanji,
                reading: row.get::<_, Option<String>>(7)?.unwrap_or_default(),
                meaning_en: row.get::<_, Option<String>>(8)?.unwrap_or_default(),
                meaning_zh: row.get::<_, Option<String>>(9)?.unwrap_or_default(),
                text: row.get::<_, Option<String>>(10)?.unwrap_or_default(),
                translation_en: row.get::<_, Option<String>>(11)?.unwrap_or_default(),
                translation_zh: row.get::<_, Option<String>>(12)?.unwrap_or_default(),
                explanation_md: row.get::<_, Option<String>>(13)?.unwrap_or_default(),
                audio_url: self.audio_url(audio_clip.as_deref()),
                word_audio_url: self.audio_url(word_clip.as_deref()),
                starred_at: row.get(16)?,
            })
        })?;
        let items = collect_rows(rows)?;

        Ok(StarredSentenceListResponse {
            total: items.len(),
            items,
        })
    }

    pub fn set_sentence_star(&self, entry_id: i64, position: i64, starred: bool) -> Result<()> {
        let _guard = self
            .write_lock
            .lock()
            .expect("sentence star write lock should not be poisoned");
        let temp_dir = TempDir::with_prefix("n2_sentence_star_")?;
        let temp_db = temp_dir.path().join(
            self.db_path
                .file_name()
                .context("database path should have a filename")?,
        );
        fs::copy(&self.db_path, &temp_db)?;

        {
            let conn = Connection::open(&temp_db)?;
            conn.execute_batch("PRAGMA foreign_keys = ON; PRAGMA journal_mode = DELETE;")?;
            self.ensure_sentence_star_schema(&conn)?;
            let item_id: Option<i64> = conn
                .query_row(
                    r#"
                    SELECT be.item_id
                    FROM book_entries be
                    JOIN item_examples ex ON ex.item_id = be.item_id
                    WHERE be.book_code = ? AND be.entry_id = ? AND ex.position = ?
                    "#,
                    params![&self.book_code, entry_id, position],
                    |row| row.get(0),
                )
                .optional()?;
            let Some(item_id) = item_id else {
                bail!("unknown example");
            };

            if starred {
                conn.execute(
                    r#"
                    INSERT INTO item_sentence_stars(item_id, position, updated_at)
                    VALUES(?, ?, ?)
                    ON CONFLICT(item_id, position) DO UPDATE SET
                      updated_at = excluded.updated_at
                    "#,
                    params![item_id, position, now_utc()],
                )?;
            } else {
                conn.execute(
                    "DELETE FROM item_sentence_stars WHERE item_id = ? AND position = ?",
                    params![item_id, position],
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
        let row: Option<(i64, String, Option<String>)> = conn
            .query_row(
                r#"
                SELECT be.item_id, ex.text, ex.audio_clip
                FROM book_entries be
                JOIN item_examples ex ON ex.item_id = be.item_id
                WHERE be.book_code = ? AND be.entry_id = ? AND ex.position = ?
                "#,
                params![&self.book_code, entry_id, position],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
            )
            .optional()?;
        drop(conn);

        let Some((item_id, text, current_clip)) = row else {
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
        self.update_example_audio_clip(item_id, position, &generated_rel_path, generated_dir)?;
        let generated_url = self
            .audio_url(Some(&generated_rel_path))
            .context("generated audio path should be servable")?;

        Ok(AudioGenerationResponse {
            ok: true,
            audio_url: generated_url,
            generated: true,
        })
    }

    pub fn ensure_word_audio<F>(
        &self,
        entry_id: i64,
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
        let row: Option<(i64, String, Option<String>, Option<String>)> = conn
            .query_row(
                r#"
                SELECT be.item_id, v.kanji, v.reading, v.word_clip
                FROM book_entries be
                JOIN vocabulary_items v ON v.item_id = be.item_id
                WHERE be.book_code = ? AND be.entry_id = ?
                "#,
                params![&self.book_code, entry_id],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
            )
            .optional()?;
        drop(conn);

        let Some((item_id, word, reading, current_clip)) = row else {
            bail!("unknown entry");
        };
        let word = word_text_for_tts(&word, reading.as_deref());
        if word.is_empty() {
            bail!("empty word");
        }

        if let Some(current) = current_clip.as_deref()
            && let Some(existing_path) = self.resolve_audio_path(current)
            && existing_path.exists()
            && let Some(audio_url) = self.audio_url(Some(current))
        {
            return Ok(AudioGenerationResponse {
                ok: true,
                audio_url,
                generated: false,
            });
        }

        let generated_rel_path = generated_word_clip_path(generated_dir, entry_id)?;
        let final_path = self
            .resolve_audio_path(&generated_rel_path)
            .context("generated word audio path should resolve inside clips")?;
        let audio_bytes = synthesize(&word)?;
        if audio_bytes.is_empty() {
            bail!("TTS returned no audio bytes");
        }
        write_file_atomically(&final_path, &audio_bytes)?;
        self.update_word_audio_clip(item_id, &generated_rel_path, generated_dir)?;
        let generated_url = self
            .audio_url(Some(&generated_rel_path))
            .context("generated word audio path should be servable")?;

        Ok(AudioGenerationResponse {
            ok: true,
            audio_url: generated_url,
            generated: true,
        })
    }

    pub fn export_unit_flagged_audio(
        &self,
        unit_number: i64,
    ) -> Result<FlaggedAudioExportResponse> {
        if unit_number <= 0 {
            bail!("unit must be a positive integer");
        }
        let _guard = self
            .write_lock
            .lock()
            .expect("audio export lock should not be poisoned");

        let items = self.list_flagged_audio_export_items(unit_number)?;
        if items.is_empty() {
            bail!("no flagged words in this unit");
        }

        let mut missing = Vec::new();
        for item in &items {
            if self
                .resolve_audio_path(&item.word_clip)
                .is_none_or(|path| !path.is_file())
            {
                missing.push(format!("word #{} word audio", item.source_index));
            }
            if self
                .resolve_audio_path(&item.sentence_clip)
                .is_none_or(|path| !path.is_file())
            {
                missing.push(format!("word #{} sentence audio", item.source_index));
            }
        }
        if !missing.is_empty() {
            bail!("missing audio clips: {}", missing.join(", "));
        }

        let export_dir = self.clips_dir.join("exports").join("flagged_units");
        fs::create_dir_all(&export_dir)?;
        let file_name = format!("unit{:02}_flagged_review.mp3", unit_number);
        let final_path = export_dir.join(&file_name);
        let temp_dir = TempDir::with_prefix("n2_flagged_audio_export_")?;
        let temp_output = temp_dir.path().join(&file_name);
        let one_second = export_dir.join("_silence_1s.mp3");
        let two_seconds = export_dir.join("_silence_2s.mp3");
        ensure_silence_clip(&one_second, 1)?;
        ensure_silence_clip(&two_seconds, 2)?;
        let concat_list = temp_dir.path().join("concat.txt");
        write_flagged_audio_concat_list(&concat_list, &items, &one_second, &two_seconds, |clip| {
            self.resolve_audio_path(clip)
                .context("clip path should resolve")
        })?;

        run_ffmpeg([
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_list
                .to_str()
                .context("concat list path must be valid UTF-8 for ffmpeg")?,
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "4",
            temp_output
                .to_str()
                .context("temporary export path must be valid UTF-8 for ffmpeg")?,
        ])?;
        fs::copy(&temp_output, &final_path)?;

        let relative = format!("clips/exports/flagged_units/{file_name}");
        let audio_url = self
            .audio_url(Some(&relative))
            .context("exported audio path should be servable")?;
        Ok(FlaggedAudioExportResponse {
            ok: true,
            unit: unit_number,
            word_count: items.len(),
            audio_url,
            file_name,
        })
    }

    fn list_flagged_audio_export_items(
        &self,
        unit_number: i64,
    ) -> Result<Vec<FlaggedAudioExportItem>> {
        let conn = self.connect()?;
        let mut statement = conn.prepare(
            r#"
            SELECT
              be.source_index,
              v.word_clip,
              COALESCE(ex.audio_clip, be.sentence_clip) AS sentence_clip
            FROM book_entries be
            JOIN vocabulary_items v ON v.item_id = be.item_id
            JOIN item_marks m ON m.item_id = be.item_id
            LEFT JOIN item_examples ex
              ON ex.item_id = be.item_id
             AND (ex.kind = 'main_sentence' OR ex.position = 0)
            WHERE be.book_code = ?
              AND be.unit_number = ?
              AND COALESCE(m.flagged, 0) = 1
            ORDER BY be.position, be.source_index
            "#,
        )?;
        let rows = statement.query_map(params![&self.book_code, unit_number], |row| {
            Ok(FlaggedAudioExportItem {
                source_index: row.get(0)?,
                word_clip: row.get::<_, Option<String>>(1)?.unwrap_or_default(),
                sentence_clip: row.get::<_, Option<String>>(2)?.unwrap_or_default(),
            })
        })?;
        collect_rows(rows)
    }

    fn update_example_audio_clip(
        &self,
        item_id: i64,
        position: i64,
        clip_path: &str,
        generated_dir: &str,
    ) -> Result<()> {
        // Audio generation runs inside the service process, so replacing the
        // SQLite file can race with this process' own mapped connections on
        // Windows. The service write lock serializes these direct metadata
        // updates without needing copy-back file replacement.
        let conn = Connection::open(&self.db_path)?;
        conn.execute_batch(
            r#"
            PRAGMA foreign_keys = ON;
            PRAGMA busy_timeout = 5000;
            CREATE TABLE IF NOT EXISTS word_service_settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            "#,
        )?;
        let changed = conn.execute(
            r#"
            UPDATE item_examples
            SET audio_clip = ?
            WHERE item_id = ? AND position = ?
            "#,
            params![clip_path, item_id, position],
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
        Ok(())
    }

    fn update_word_audio_clip(
        &self,
        item_id: i64,
        clip_path: &str,
        generated_dir: &str,
    ) -> Result<()> {
        let conn = Connection::open(&self.db_path)?;
        conn.execute_batch(
            r#"
            PRAGMA foreign_keys = ON;
            PRAGMA busy_timeout = 5000;
            CREATE TABLE IF NOT EXISTS word_service_settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            "#,
        )?;
        let changed = conn.execute(
            "UPDATE vocabulary_items SET word_clip = ? WHERE item_id = ?",
            params![clip_path, item_id],
        )?;
        if changed != 1 {
            bail!("unknown entry");
        }
        conn.execute(
            r#"
            INSERT INTO word_service_settings(key, value, updated_at)
            VALUES('generated_word_audio_dir', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value = excluded.value,
              updated_at = excluded.updated_at
            "#,
            params![normalize_generated_audio_dir(generated_dir)?, now_utc()],
        )?;
        Ok(())
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

fn normalize_book_code(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        "N2".to_string()
    } else {
        trimmed.to_uppercase()
    }
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

fn int_to_bool(value: i64) -> bool {
    value != 0
}

fn bool_to_int(value: bool) -> i64 {
    if value { 1 } else { 0 }
}

fn now_utc() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%S.%6fZ").to_string()
}
