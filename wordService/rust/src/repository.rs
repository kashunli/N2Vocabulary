use crate::models::{
    EntryExample, EntryListResponse, EntryPayload, MarkState, MarksResponse, Summary, UnitRef,
    UnitSummary,
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

#[derive(Clone, Debug)]
pub struct WordRepository {
    db_path: PathBuf,
    clips_dir: PathBuf,
    book_code: String,
    write_lock: Arc<Mutex<()>>,
}

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
        let normalized = normalize_clip_path(clip_path?, true)?;
        Some(format!("/audio/{normalized}"))
    }

    pub fn resolve_audio_path(&self, request_path: &str) -> Option<PathBuf> {
        let normalized = normalize_clip_path(request_path, false)?;
        let clips_parent = self.clips_dir.parent().unwrap_or_else(|| Path::new("."));
        Some(clips_parent.join(normalized))
    }

    pub fn set_mark(&self, entry_id: i64, known: bool, flagged: bool) -> Result<()> {
        // The Python service writes marks through a temporary DB copy because
        // stale WAL sidecars on this Windows workspace have made direct writes
        // fragile. The mutex makes that copy-mutate-copy-back sequence one-at-a-time.
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
}

fn collect_rows<T>(
    rows: rusqlite::MappedRows<'_, impl FnMut(&rusqlite::Row<'_>) -> rusqlite::Result<T>>,
) -> Result<Vec<T>> {
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

fn short_title(header: &str) -> Option<String> {
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
