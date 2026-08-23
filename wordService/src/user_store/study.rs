use super::{
    MarkStatus, ReviewCompletion, STUDY_STATE_VERSION, StudyCard, StudySnapshot, UserStore, now_utc,
};
use anyhow::{Context, Result};
use chrono::{DateTime, Duration, Utc};
use rusqlite::{Connection, OptionalExtension, params};
use std::collections::HashMap;

impl UserStore {
    pub fn snapshot(&self, user_id: i64) -> Result<StudySnapshot> {
        let conn = self.connect()?;
        let mut statement = conn.prepare(
            r#"SELECT item_uuid,status,mark_updated_at,enrolled_at,due_at,review_level,last_reviewed_at,
                      last_played_at,preferred_book_code,preferred_source_index,updated_at
               FROM study_cards WHERE user_id=? ORDER BY item_uuid"#,
        )?;
        let rows = statement.query_map([user_id], row_to_card)?;
        let mut cards = HashMap::new();
        let mut updated_at = "1970-01-01T00:00:00Z".to_string();
        for row in rows {
            let card = row?;
            if card.updated_at > updated_at {
                updated_at = card.updated_at.clone();
            }
            cards.insert(card.item_uuid.clone(), card);
        }
        Ok(StudySnapshot {
            version: STUDY_STATE_VERSION,
            updated_at,
            cards,
        })
    }

    pub fn set_mark_status(
        &self,
        user_id: i64,
        item_uuid: &str,
        status: MarkStatus,
    ) -> Result<StudyCard> {
        let _guard = self.write_lock.lock().expect("user write lock");
        let conn = self.connect()?;
        let now = now_utc();
        conn.execute(
            r#"INSERT INTO study_cards(user_id,item_uuid,status,mark_updated_at,updated_at)
               VALUES(?,?,?,?,?) ON CONFLICT(user_id,item_uuid) DO UPDATE SET
               status=excluded.status, mark_updated_at=excluded.mark_updated_at,
               updated_at=excluded.updated_at"#,
            params![user_id, item_uuid, status, now, now],
        )?;
        get_card(&conn, user_id, item_uuid)
    }

    pub fn record_study_completed(
        &self,
        user_id: i64,
        item_uuid: &str,
        book: &str,
        source_index: i64,
    ) -> Result<StudyCard> {
        let _guard = self.write_lock.lock().expect("user write lock");
        let conn = self.connect()?;
        let now = Utc::now();
        let now_text = now.to_rfc3339();
        let due = next_review_due_at(now, 0)?.to_rfc3339();
        conn.execute(
            r#"INSERT INTO study_cards(user_id,item_uuid,status,mark_updated_at,enrolled_at,due_at,review_level,
                    last_played_at,preferred_book_code,preferred_source_index,updated_at)
               VALUES(?,?,'unmarked',?,?,?,0,?,?,?,?)
               ON CONFLICT(user_id,item_uuid) DO UPDATE SET
                 enrolled_at=COALESCE(study_cards.enrolled_at,excluded.enrolled_at),
                 due_at=COALESCE(study_cards.due_at,excluded.due_at),
                 last_played_at=excluded.last_played_at,
                 preferred_book_code=excluded.preferred_book_code,
                 preferred_source_index=excluded.preferred_source_index,
                 updated_at=excluded.updated_at"#,
            params![
                user_id,
                item_uuid,
                now_text,
                now_text,
                due,
                now_text,
                book,
                source_index,
                now_text
            ],
        )?;
        get_card(&conn, user_id, item_uuid)
    }

    pub fn complete_review(
        &self,
        user_id: i64,
        item_uuid: &str,
        expected_due_at: &str,
        book: &str,
        source_index: i64,
    ) -> Result<ReviewCompletion> {
        self.complete_review_at(
            user_id,
            item_uuid,
            expected_due_at,
            book,
            source_index,
            Utc::now(),
        )
    }

    pub(super) fn complete_review_at(
        &self,
        user_id: i64,
        item_uuid: &str,
        expected_due_at: &str,
        book: &str,
        source_index: i64,
        now: DateTime<Utc>,
    ) -> Result<ReviewCompletion> {
        let expected_due = DateTime::parse_from_rfc3339(expected_due_at)
            .context("expected due time must be RFC3339")?
            .with_timezone(&Utc);
        let _guard = self.write_lock.lock().expect("user write lock");
        let mut conn = self.connect()?;
        let transaction = conn.transaction()?;
        let Some(current) = get_card_optional(&transaction, user_id, item_uuid)? else {
            transaction.commit()?;
            return Ok(ReviewCompletion::Conflict(None));
        };
        let Some(current_due_text) = current.due_at.as_deref() else {
            transaction.commit()?;
            return Ok(ReviewCompletion::Conflict(Some(current)));
        };
        let current_due = DateTime::parse_from_rfc3339(current_due_text)
            .context("stored due time must be RFC3339")?
            .with_timezone(&Utc);
        if current_due != expected_due || current_due > now {
            transaction.commit()?;
            return Ok(ReviewCompletion::Conflict(Some(current)));
        }

        let next_level = current
            .review_level
            .checked_add(1)
            .context("review level is too large to advance")?;
        let next_due = next_review_due_at(now, next_level)?.to_rfc3339();
        let now_text = now.to_rfc3339();
        let rows = transaction.execute(
            r#"UPDATE study_cards SET review_level=?,due_at=?,last_reviewed_at=?,last_played_at=?,
                   preferred_book_code=?,preferred_source_index=?,updated_at=?
               WHERE user_id=? AND item_uuid=? AND due_at=?"#,
            params![
                next_level,
                next_due,
                now_text,
                now_text,
                book,
                source_index,
                now_text,
                user_id,
                item_uuid,
                expected_due_at,
            ],
        )?;
        if rows != 1 {
            let latest = get_card_optional(&transaction, user_id, item_uuid)?;
            transaction.commit()?;
            return Ok(ReviewCompletion::Conflict(latest));
        }
        let card = get_card(&transaction, user_id, item_uuid)?;
        transaction.commit()?;
        Ok(ReviewCompletion::Completed(card))
    }
}

pub(super) fn next_review_due_at(completed_at: DateTime<Utc>, level: i64) -> Result<DateTime<Utc>> {
    let shift = u32::try_from(level).context("review level must be non-negative")?;
    let days = 1_i64
        .checked_shl(shift)
        .context("review interval is too large")?;
    let seconds = days
        .checked_mul(24 * 60 * 60)
        .context("review interval is too large")?;
    let interval = Duration::try_seconds(seconds).context("review interval is too large")?;
    completed_at
        .checked_add_signed(interval)
        .context("next review date is out of range")
}

fn row_to_card(row: &rusqlite::Row<'_>) -> rusqlite::Result<StudyCard> {
    Ok(StudyCard {
        item_uuid: row.get(0)?,
        status: row.get(1)?,
        mark_updated_at: row.get(2)?,
        enrolled_at: row.get(3)?,
        due_at: row.get(4)?,
        review_level: row.get(5)?,
        last_reviewed_at: row.get(6)?,
        last_played_at: row.get(7)?,
        preferred_book_code: row.get(8)?,
        preferred_source_index: row.get(9)?,
        updated_at: row.get(10)?,
    })
}

fn get_card(conn: &Connection, user_id: i64, item_uuid: &str) -> Result<StudyCard> {
    conn.query_row(
        r#"SELECT item_uuid,status,mark_updated_at,enrolled_at,due_at,review_level,last_reviewed_at,
                  last_played_at,preferred_book_code,preferred_source_index,updated_at
           FROM study_cards WHERE user_id=? AND item_uuid=?"#,
        params![user_id, item_uuid],
        row_to_card,
    )
    .context("study card not found")
}

pub(super) fn get_card_optional(
    conn: &Connection,
    user_id: i64,
    item_uuid: &str,
) -> Result<Option<StudyCard>> {
    conn.query_row(
        r#"SELECT item_uuid,status,mark_updated_at,enrolled_at,due_at,review_level,last_reviewed_at,
                  last_played_at,preferred_book_code,preferred_source_index,updated_at
           FROM study_cards WHERE user_id=? AND item_uuid=?"#,
        params![user_id, item_uuid],
        row_to_card,
    )
    .optional()
    .context("read optional study card")
}
