use crate::models::{EntryExample, EntryPayload, EntrySourceNote, MarkState, UnitRef};
use anyhow::{Context, Result};
use chrono::Utc;
use rusqlite::types::Value;
use rusqlite::{Connection, params_from_iter};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

mod audio_export;
mod catalog;
mod marks;
mod media;
mod paths;
mod schema;
mod search;
mod text;

pub use text::clean_sentence_text_for_tts;

const STATE_VALUES: [&str; 4] = ["all", "known", "flagged", "unmarked"];
const EXCLUSIVE_MARK_DATA_MIGRATION: &str = "exclusive-mark-v1";

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
    // Lazily computed SHA-256 of the content database, shared across the
    // per-book clones every request creates. The frontend uses it to validate
    // its local content cache.
    content_revision: Arc<Mutex<Option<String>>>,
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
    item_uuid: String,
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
    word_audio_id: Option<i64>,
    sentence_audio_id: Option<i64>,
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
            content_revision: Arc::new(Mutex::new(None)),
        }
    }

    pub fn for_book(&self, book_code: &str) -> Self {
        Self {
            db_path: self.db_path.clone(),
            clips_dir: self.clips_dir.clone(),
            book_code: normalize_book_code(book_code),
            write_lock: self.write_lock.clone(),
            content_revision: self.content_revision.clone(),
        }
    }

    /// Fingerprint of the immutable content database, computed once per process.
    ///
    /// The hash is taken lazily on first access and cached, so the 35 MB read
    /// happens at most once per run. A fresh process after an offline import or
    /// migration sees a different hash and the browser refetches its content.
    pub fn content_revision(&self) -> String {
        let mut guard = self
            .content_revision
            .lock()
            .expect("content revision lock should not be poisoned");
        if let Some(value) = guard.as_ref() {
            return value.clone();
        }
        // A missing/unreadable database simply becomes an empty revision, which
        // makes the browser treat every cache as stale and refetch. Failing the
        // whole summary request would be worse than a redundant refetch.
        let revision = fs::read(&self.db_path)
            .map(|bytes| {
                let digest = Sha256::digest(&bytes);
                digest
                    .iter()
                    .map(|byte| format!("{:02x}", byte))
                    .collect::<String>()
            })
            .unwrap_or_default();
        *guard = Some(revision.clone());
        revision
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
                item_uuid: row.get(3)?,
                book_code: row.get(4)?,
                source_index: row.get(5)?,
                unit_number: row.get(6)?,
                unit_header: row.get(7)?,
                unit_title: row.get(8)?,
                kanji: row.get(9)?,
                reading: row.get(10)?,
                verb_pattern: row.get(11)?,
                meaning_en: row.get(12)?,
                meaning_zh: row.get(13)?,
                sentence: row.get(14)?,
                explanation_md: row.get(15)?,
                word_clip: row.get(16)?,
                sentence_clip: row.get(17)?,
                known: row.get(18)?,
                flagged: row.get(19)?,
                mark_updated_at: row.get(20)?,
                word_audio_id: row.get(21)?,
                sentence_audio_id: row.get(22)?,
            })
        })?;

        collect_rows(rows)
    }

    fn load_examples(
        &self,
        conn: &Connection,
        item_ids: &[i64],
        versioned_audio: bool,
    ) -> Result<HashMap<i64, Vec<EntryExample>>> {
        if item_ids.is_empty() {
            return Ok(HashMap::new());
        }
        // SQLite does not accept a Vec directly as one `IN (?)` parameter, so
        // we build exactly one placeholder per already-known numeric entry ID.
        let placeholders = vec!["?"; item_ids.len()].join(",");
        let sql = format!(
            r#"
            SELECT example_rows.*, audio_assets.audio_id
            FROM (
              SELECT ex.item_id, ex.position, ex.kind, text, reading, translation_en,
                     translation_zh, explanation_md,
                     COALESCE(
                       (
                         SELECT source_entry.sentence_clip
                         FROM item_example_sources p
                         JOIN book_entries source_entry
                           ON source_entry.item_id = p.item_id
                          AND source_entry.book_code = p.source_book_code
                          AND source_entry.source_index = p.source_index
                         WHERE p.item_id = ex.item_id AND p.position = ex.position
                           AND TRIM(COALESCE(source_entry.sentence, '')) = TRIM(COALESCE(ex.text, ''))
                           AND TRIM(COALESCE(source_entry.sentence_clip, '')) <> ''
                         ORDER BY CASE p.source_book_code
                                    WHEN 'N1' THEN 0 WHEN 'N2' THEN 1 WHEN 'N3' THEN 2 ELSE 3
                                  END,
                                  p.source_book_code, p.source_index
                         LIMIT 1
                       ),
                       ex.audio_clip
                     ) AS resolved_audio_clip,
                     ex.category,
                     (
                       SELECT p.source_book_code FROM item_example_sources p
                       WHERE p.item_id = ex.item_id AND p.position = ex.position
                       ORDER BY p.source_book_code, p.source_index LIMIT 1
                     ) AS source_book_code,
                     (
                       SELECT p.source_index FROM item_example_sources p
                       WHERE p.item_id = ex.item_id AND p.position = ex.position
                       ORDER BY p.source_book_code, p.source_index LIMIT 1
                     ) AS source_index,
                     (
                       SELECT p.source_book_code
                       FROM item_example_sources p
                       JOIN book_entries source_entry
                         ON source_entry.item_id = p.item_id
                        AND source_entry.book_code = p.source_book_code
                        AND source_entry.source_index = p.source_index
                       WHERE p.item_id = ex.item_id AND p.position = ex.position
                         AND TRIM(COALESCE(source_entry.sentence, '')) = TRIM(COALESCE(ex.text, ''))
                       ORDER BY CASE p.source_book_code
                                  WHEN 'N1' THEN 0 WHEN 'N2' THEN 1 WHEN 'N3' THEN 2 ELSE 3
                                END,
                                p.source_book_code, p.source_index
                       LIMIT 1
                     ) AS main_source_book_code
              FROM item_examples ex
              WHERE ex.item_id IN ({placeholders})
            ) AS example_rows
            LEFT JOIN audio_assets
              ON audio_assets.clip_path = example_rows.resolved_audio_clip
            ORDER BY example_rows.item_id, example_rows.position
            "#
        );
        let mut statement = conn.prepare(&sql)?;
        let rows = statement.query_map(params_from_iter(item_ids.iter()), |row| {
            let item_id: i64 = row.get(0)?;
            let audio_clip: Option<String> = row.get(8)?;
            let audio_id: Option<i64> = row.get(13)?;
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
                    audio_id,
                    audio_url: if versioned_audio {
                        self.audio_url(audio_clip.as_deref())
                    } else {
                        self.audio_path_url(audio_clip.as_deref())
                    },
                    category: row.get(9)?,
                    source_book_code: row.get(10)?,
                    source_index: row.get(11)?,
                    main_source_book_code: row.get(12)?,
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
            SELECT source_book_code, source_index, source_title, source_page,
                   source_cd_track, source_reading, source_meaning_en,
                   source_meaning_zh, source_notes_md
            FROM item_source_notes
            WHERE item_id = ?
              -- `source_explanation_md` is a legacy compatibility column. It
              -- contains copied learner explanations and old source-book
              -- bookkeeping, so it must never become a learner-visible
              -- source-note block. Only explicitly structured provenance or
              -- `source_notes_md` belongs in the source metadata API.
              AND (
                NULLIF(TRIM(COALESCE(source_title, '')), '') IS NOT NULL
                OR source_page IS NOT NULL
                OR NULLIF(TRIM(COALESCE(source_cd_track, '')), '') IS NOT NULL
                OR NULLIF(TRIM(COALESCE(source_notes_md, '')), '') IS NOT NULL
              )
            ORDER BY source_book_code, source_index
            "#,
        )?;
        let rows = statement.query_map([item_id], |row| {
            Ok(EntrySourceNote {
                source_book_code: row.get(0)?,
                source_index: row.get(1)?,
                source_title: row.get(2)?,
                source_page: row.get(3)?,
                source_cd_track: row.get(4)?,
                reading: row.get::<_, Option<String>>(5)?.unwrap_or_default(),
                meaning_en: row.get::<_, Option<String>>(6)?.unwrap_or_default(),
                meaning_zh: row.get::<_, Option<String>>(7)?.unwrap_or_default(),
                notes_md: row.get::<_, Option<String>>(8)?.unwrap_or_default(),
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
        // Mimikara is the primary study source. When the same vocabulary item
        // occurs in several books, choose its originating Mimikara sentence in
        // the stable N1 > N2 > N3 order, regardless of which book is open.
        let preferred_mimikara_main = examples_slice
            .iter()
            .filter_map(|example| {
                mimikara_book_priority(example.main_source_book_code.as_deref())
                    .map(|priority| (priority, example.position, example))
            })
            .min_by_key(|(priority, position, _)| (*priority, *position))
            .map(|(_, _, example)| example);
        let main_example = preferred_mimikara_main
            .or_else(|| {
                row.sentence.as_deref().and_then(|sentence| {
                    examples_slice
                        .iter()
                        .find(|example| example.text.trim() == sentence.trim())
                })
            })
            .or_else(|| {
                examples_slice
                    .iter()
                    .find(|example| example.main_source_book_code.is_some())
            })
            .or_else(|| {
                examples_slice
                    .iter()
                    .find(|example| example.kind == "main_sentence")
            })
            .or_else(|| examples_slice.iter().find(|example| example.position == 0));

        // The selected example is authoritative. The book-scoped sentence is
        // retained only as a compatibility fallback for incomplete migrations.
        let sentence = main_example
            .map(|example| example.text.clone())
            .or_else(|| row.sentence.clone())
            .unwrap_or_default();
        let selected_matches_current_book =
            main_example
                .zip(row.sentence.as_deref())
                .is_some_and(|(example, current_sentence)| {
                    example.text.trim() == current_sentence.trim()
                });
        let sentence_audio_url = main_example
            .and_then(|example| example.audio_url.clone())
            .or_else(|| {
                selected_matches_current_book
                    .then(|| {
                        if detail {
                            self.audio_url(row.sentence_clip.as_deref())
                        } else {
                            self.audio_path_url(row.sentence_clip.as_deref())
                        }
                    })
                    .flatten()
            });
        let sentence_audio_id = main_example
            .and_then(|example| example.audio_id)
            .or_else(|| {
                selected_matches_current_book
                    .then_some(row.sentence_audio_id)
                    .flatten()
            });

        // The explanation is static content the card pane renders on every
        // entry, so list and detail payloads both carry it. Keeping it in the
        // list lets the study wall render the pane from the already-loaded
        // queue instead of fetching one entry per card play.
        let explanation_md = {
            let value = main_example
                .map(|example| example.explanation_md.clone())
                .filter(|value| !value.is_empty())
                .or_else(|| row.explanation_md.clone())
                .unwrap_or_default();
            (!value.trim().is_empty()).then_some(value)
        };

        EntryPayload {
            entry_id: row.entry_id,
            source_index: row.source_index,
            uuid: row.uuid.clone(),
            item_uuid: row.item_uuid.clone(),
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
            sentence_position: main_example.map(|example| example.position).unwrap_or(0),
            word_audio_id: row.word_audio_id,
            word_audio_url: if detail {
                self.audio_url(row.word_clip.as_deref())
            } else {
                self.audio_path_url(row.word_clip.as_deref())
            },
            sentence_audio_id,
            sentence_audio_url: sentence_audio_url.clone(),
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
                let mut ordered_examples = examples_slice.to_vec();
                if let Some(main) = main_example {
                    ordered_examples.sort_by_key(|example| {
                        (example.position != main.position, example.position)
                    });
                    if let Some(first) = ordered_examples.first_mut() {
                        first.kind = "main_sentence".to_string();
                        first.audio_url = sentence_audio_url.clone();
                    }
                }
                Some(ordered_examples)
            } else {
                let extra_examples = examples_slice
                    .iter()
                    .filter(|example| {
                        main_example
                            .map(|main| example.position != main.position)
                            .unwrap_or(true)
                    })
                    .cloned()
                    .collect::<Vec<_>>();
                (!extra_examples.is_empty()).then_some(extra_examples)
            },
            source_notes: detail.then(|| source_notes.unwrap_or_default()),
            search_matches,
            explanation_md,
        }
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

fn mimikara_book_priority(book_code: Option<&str>) -> Option<u8> {
    match book_code {
        Some("N1") => Some(0),
        Some("N2") => Some(1),
        Some("N3") => Some(2),
        _ => None,
    }
}

fn normalize_book_code(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        "N2".to_string()
    } else {
        trimmed.to_uppercase()
    }
}

fn int_to_bool(value: i64) -> bool {
    value != 0
}

fn sqlite_table_exists(conn: &Connection, table_name: &str) -> Result<bool> {
    Ok(conn.query_row(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?)",
        [table_name],
        |row| row.get(0),
    )?)
}

fn now_utc() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%S.%6fZ").to_string()
}
