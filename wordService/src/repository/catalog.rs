use super::search::{search_matches, search_terms};
use super::{STATE_VALUES, WordRepository, collect_rows, int_to_bool};
use crate::models::{
    BookSummary, EntryListResponse, EntryPayload, LegacyMarkSeed, LegacyMarkSeedResponse, Summary,
    UnitSummary,
};
use anyhow::{Result, bail};
use rusqlite::Connection;
use rusqlite::types::Value;

impl WordRepository {
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
            content_revision: self.content_revision(),
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
                "COALESCE(v.kanji, '') LIKE ?".to_string(),
                "COALESCE(v.reading, '') LIKE ?".to_string(),
                "COALESCE(v.meaning_en, '') LIKE ?".to_string(),
                "COALESCE(v.meaning_zh, '') LIKE ?".to_string(),
            ];
            // The same search text is bound to each LIKE placeholder. Binding
            // instead of interpolating prevents user input from becoming SQL.
            for _ in 0..4 {
                query_params.push(Value::Text(format!("%{}%", terms[0])));
            }
            let mut example_search_clauses = vec![
                "COALESCE(ex.text, '') LIKE ?".to_string(),
                "COALESCE(ex.reading, '') LIKE ?".to_string(),
                "COALESCE(ex.translation_en, '') LIKE ?".to_string(),
                "COALESCE(ex.translation_zh, '') LIKE ?".to_string(),
            ];
            for _ in 0..4 {
                query_params.push(Value::Text(format!("%{}%", terms[0])));
            }
            for term in terms.iter().skip(1) {
                // Japanese verbs often appear in examples as inflected forms:
                // searching `覆う` should still find sentences with `覆われる`
                // or `覆った`. Keep the wider stem match limited to examples so
                // word/meaning searches remain predictable.
                example_search_clauses.push("COALESCE(ex.text, '') LIKE ?".to_string());
                query_params.push(Value::Text(format!("%{term}%")));
            }
            // Search examples with EXISTS instead of joining every example row
            // into the entry result.  This preserves one result per entry and
            // lets SQLite use item_examples(item_id, position) directly.
            search_clauses.push(format!(
                "EXISTS (SELECT 1 FROM item_examples ex WHERE ex.item_id = be.item_id AND ({}))",
                example_search_clauses.join(" OR ")
            ));
            clauses.push(format!("({})", search_clauses.join(" OR ")));
        }

        let conn = self.connect()?;
        let sql = format!(
            r#"
            SELECT
              be.entry_id, be.item_id, be.uuid, v.uuid AS item_uuid,
              be.book_code, be.source_index, be.unit_number,
              u.header AS unit_header, u.title AS unit_title, v.kanji, v.reading,
              COALESCE(NULLIF(be.verb_pattern, ''), v.verb_pattern) AS verb_pattern,
              COALESCE(NULLIF(be.meaning_en, ''), v.meaning_en) AS meaning_en,
              COALESCE(NULLIF(be.meaning_zh, ''), v.meaning_zh) AS meaning_zh,
              be.sentence,
              COALESCE(be.explanation_md, v.explanation_md) AS explanation_md,
              COALESCE(be.word_clip, v.word_clip) AS word_clip, be.sentence_clip,
              m.known, m.flagged, m.updated_at AS mark_updated_at
            FROM book_entries be
            JOIN vocabulary_items v ON v.item_id = be.item_id
            JOIN units u
              ON u.book_code = be.book_code AND u.number = be.unit_number
            LEFT JOIN item_marks m ON m.item_id = be.item_id
            WHERE {}
            ORDER BY be.unit_number, be.position, be.source_index
            "#,
            clauses.join(" AND ")
        );

        let rows = self.query_entry_rows(&conn, &sql, query_params)?;
        let item_ids = rows.iter().map(|row| row.item_id).collect::<Vec<_>>();
        // Load examples in one follow-up query instead of one query per entry.
        // This keeps list rendering fast while still leaving the SQL readable.
        let examples = self.load_examples(&conn, &item_ids, false)?;
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
              be.entry_id, be.item_id, be.uuid, v.uuid AS item_uuid,
              be.book_code, be.source_index, be.unit_number,
              u.header AS unit_header, u.title AS unit_title, v.kanji, v.reading,
              COALESCE(NULLIF(be.verb_pattern, ''), v.verb_pattern) AS verb_pattern,
              COALESCE(NULLIF(be.meaning_en, ''), v.meaning_en) AS meaning_en,
              COALESCE(NULLIF(be.meaning_zh, ''), v.meaning_zh) AS meaning_zh,
              be.sentence,
              COALESCE(be.explanation_md, v.explanation_md) AS explanation_md,
              COALESCE(be.word_clip, v.word_clip) AS word_clip, be.sentence_clip,
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

        let examples = self.load_examples(&conn, &[row.item_id], true)?;
        let source_notes = self.load_source_notes(&conn, row.item_id)?;
        Ok(Some(self.serialize_entry(
            row,
            examples.get(&row.item_id),
            true,
            None,
            Some(source_notes),
        )))
    }

    /// Resolve a shared item to the best book occurrence for a review card.
    pub fn resolve_item_for_review(
        &self,
        item_uuid: &str,
        preferred_book_code: Option<&str>,
        preferred_source_index: Option<i64>,
    ) -> Result<Option<EntryPayload>> {
        let conn = self.connect()?;
        let sql = r#"
            SELECT
              be.entry_id, be.item_id, be.uuid, v.uuid AS item_uuid,
              be.book_code, be.source_index, be.unit_number,
              u.header, u.title, v.kanji, v.reading,
              COALESCE(NULLIF(be.verb_pattern, ''), v.verb_pattern),
              COALESCE(NULLIF(be.meaning_en, ''), v.meaning_en),
              COALESCE(NULLIF(be.meaning_zh, ''), v.meaning_zh),
              be.sentence, COALESCE(be.explanation_md, v.explanation_md),
              COALESCE(be.word_clip, v.word_clip), be.sentence_clip,
              m.known, m.flagged, m.updated_at
            FROM vocabulary_items v
            JOIN book_entries be ON be.item_id = v.item_id
            JOIN units u ON u.book_code = be.book_code AND u.number = be.unit_number
            LEFT JOIN item_marks m ON m.item_id = v.item_id
            WHERE v.uuid = ?
            ORDER BY
              CASE WHEN be.book_code = ? AND be.source_index = ? THEN 0
                   WHEN be.book_code = 'N2' THEN 1 ELSE 2 END,
              be.book_code, be.source_index
            LIMIT 1
        "#;
        let rows = self.query_entry_rows(
            &conn,
            sql,
            vec![
                Value::Text(item_uuid.to_string()),
                Value::Text(preferred_book_code.unwrap_or("").to_string()),
                Value::Integer(preferred_source_index.unwrap_or(-1)),
            ],
        )?;
        let Some(row) = rows.first() else {
            return Ok(None);
        };
        let examples = self.load_examples(&conn, &[row.item_id], true)?;
        let source_notes = self.load_source_notes(&conn, row.item_id)?;
        Ok(Some(self.serialize_entry(
            row,
            examples.get(&row.item_id),
            true,
            None,
            Some(source_notes),
        )))
    }

    pub fn legacy_mark_seed(&self) -> Result<LegacyMarkSeedResponse> {
        let conn = self.connect()?;
        let mut statement = conn.prepare(
            r#"
            SELECT v.uuid, m.known, m.flagged
            FROM item_marks m
            JOIN vocabulary_items v ON v.item_id = m.item_id
            WHERE m.known = 1 OR m.flagged = 1
            ORDER BY v.uuid
            "#,
        )?;
        let rows = statement.query_map([], |row| {
            Ok(LegacyMarkSeed {
                item_uuid: row.get(0)?,
                known: int_to_bool(row.get(1)?),
                flagged: int_to_bool(row.get(2)?),
            })
        })?;
        Ok(LegacyMarkSeedResponse {
            items: collect_rows(rows)?,
        })
    }
}
