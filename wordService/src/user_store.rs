//! Per-user authentication and study state stored separately from vocabulary.

use anyhow::{Context, Result, bail};
use chrono::{DateTime, Duration, Utc};
use rusqlite::types::{FromSql, FromSqlError, ToSql, ToSqlOutput, ValueRef};
use rusqlite::{Connection, OptionalExtension, params};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Instant;

pub const SESSION_COOKIE: &str = "n2_word_session";
const SESSION_DAYS: i64 = 30;
pub const STUDY_STATE_VERSION: i64 = 3;
const SPACED_REVIEW_STATE_VERSION: i64 = 2;
const SPACED_REVIEW_MIGRATION: &str = "spaced-review-v1";
const EXCLUSIVE_MARK_MIGRATION: &str = "exclusive-mark-v1";

mod auth;
mod schema;

#[derive(Clone, Debug)]
pub struct UserStore {
    db_path: PathBuf,
    write_lock: Arc<Mutex<()>>,
    login_failures: Arc<Mutex<HashMap<String, (u32, Instant)>>>,
}

#[derive(Clone, Debug, Serialize)]
pub struct AuthUser {
    pub id: i64,
    pub email: String,
}

#[derive(Clone, Debug)]
pub struct AuthContext {
    pub user: AuthUser,
    pub csrf_token: String,
    pub session_token_hash: String,
}

#[derive(Clone, Debug)]
pub struct NewSession {
    pub user: AuthUser,
    pub token: String,
    pub csrf_token: String,
}

#[derive(Clone, Copy, Debug, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MarkStatus {
    #[default]
    Unmarked,
    Known,
    Flagged,
}

impl MarkStatus {
    pub fn from_legacy(known: bool, flagged: bool) -> Self {
        if flagged {
            Self::Flagged
        } else if known {
            Self::Known
        } else {
            Self::Unmarked
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::Unmarked => "unmarked",
            Self::Known => "known",
            Self::Flagged => "flagged",
        }
    }
}

impl ToSql for MarkStatus {
    fn to_sql(&self) -> rusqlite::Result<ToSqlOutput<'_>> {
        Ok(ToSqlOutput::Owned(self.as_str().to_string().into()))
    }
}

impl FromSql for MarkStatus {
    fn column_result(value: ValueRef<'_>) -> std::result::Result<Self, FromSqlError> {
        let ValueRef::Text(value) = value else {
            return Err(FromSqlError::InvalidType);
        };
        match value {
            b"unmarked" => Ok(Self::Unmarked),
            b"known" => Ok(Self::Known),
            b"flagged" => Ok(Self::Flagged),
            _ => Err(FromSqlError::Other("invalid mark status".into())),
        }
    }
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct StudyCard {
    pub item_uuid: String,
    pub status: MarkStatus,
    pub mark_updated_at: Option<String>,
    pub enrolled_at: Option<String>,
    pub due_at: Option<String>,
    #[serde(default)]
    pub review_level: i64,
    #[serde(default)]
    pub last_reviewed_at: Option<String>,
    pub last_played_at: Option<String>,
    pub preferred_book_code: Option<String>,
    pub preferred_source_index: Option<i64>,
    pub updated_at: String,
}

/// The import reader accepts both the old boolean shape and the new status
/// shape. This keeps a browser with a cached guest snapshot safe during the
/// deployment window; all values are normalized before they reach storage.
#[derive(Debug, Deserialize)]
struct StudyCardInput {
    item_uuid: String,
    #[serde(default)]
    status: Option<MarkStatus>,
    #[serde(default)]
    known: bool,
    #[serde(default)]
    flagged: bool,
    #[serde(default)]
    mark_updated_at: Option<String>,
    enrolled_at: Option<String>,
    due_at: Option<String>,
    #[serde(default)]
    review_level: i64,
    #[serde(default)]
    last_reviewed_at: Option<String>,
    last_played_at: Option<String>,
    preferred_book_code: Option<String>,
    preferred_source_index: Option<i64>,
    updated_at: String,
}

impl<'de> Deserialize<'de> for StudyCard {
    fn deserialize<D>(deserializer: D) -> std::result::Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        let input = StudyCardInput::deserialize(deserializer)?;
        let status = if input.flagged || input.status == Some(MarkStatus::Flagged) {
            MarkStatus::Flagged
        } else if input.status == Some(MarkStatus::Known) || input.known {
            MarkStatus::Known
        } else {
            MarkStatus::Unmarked
        };
        Ok(Self {
            item_uuid: input.item_uuid,
            status,
            mark_updated_at: input.mark_updated_at,
            enrolled_at: input.enrolled_at,
            due_at: input.due_at,
            review_level: input.review_level,
            last_reviewed_at: input.last_reviewed_at,
            last_played_at: input.last_played_at,
            preferred_book_code: input.preferred_book_code,
            preferred_source_index: input.preferred_source_index,
            updated_at: input.updated_at,
        })
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum ReviewCompletion {
    Completed(StudyCard),
    Conflict(Option<StudyCard>),
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct StudySnapshot {
    pub version: i64,
    pub updated_at: String,
    pub cards: HashMap<String, StudyCard>,
}

impl UserStore {
    pub fn new(path: impl Into<PathBuf>) -> Self {
        Self {
            db_path: path.into(),
            write_lock: Arc::new(Mutex::new(())),
            login_failures: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    pub fn db_path(&self) -> &Path {
        &self.db_path
    }

    fn connect(&self) -> Result<Connection> {
        let conn = Connection::open(&self.db_path)
            .with_context(|| format!("open user database {}", self.db_path.display()))?;
        conn.execute_batch("PRAGMA foreign_keys = ON; PRAGMA busy_timeout = 5000;")?;
        Ok(conn)
    }

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

    fn complete_review_at(
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

    pub fn import_guest(
        &self,
        user_id: i64,
        import_id: &str,
        checksum: &str,
        guest_version: i64,
        guest_cards: Vec<StudyCard>,
    ) -> Result<StudySnapshot> {
        if import_id.trim().is_empty() || checksum.trim().is_empty() {
            bail!("import ID and snapshot checksum are required");
        }
        let _guard = self.write_lock.lock().expect("user write lock");
        let mut conn = self.connect()?;
        let transaction = conn.transaction()?;
        let prior: Option<String> = transaction
            .query_row(
                "SELECT snapshot_checksum FROM guest_imports WHERE user_id=? AND import_id=?",
                params![user_id, import_id],
                |row| row.get(0),
            )
            .optional()?;
        if let Some(prior_checksum) = prior {
            if prior_checksum != checksum {
                bail!("import ID was already used for a different snapshot");
            }
            transaction.commit()?;
            return self.snapshot(user_id);
        }

        let now = now_utc();
        for mut guest in guest_cards {
            if guest_version < SPACED_REVIEW_STATE_VERSION {
                // A cached pre-level client can carry the old one-time due
                // timestamps. Keep its tags and playback provenance only.
                guest.enrolled_at = None;
                guest.due_at = None;
                guest.review_level = 0;
                guest.last_reviewed_at = None;
            }
            let account = get_card_optional(&transaction, user_id, &guest.item_uuid)?;
            let merged = match account {
                Some(card) => merge_import_cards(card, guest, &now),
                None => StudyCard {
                    updated_at: now.clone(),
                    ..guest
                },
            };
            upsert_card(&transaction, user_id, &merged)?;
        }
        transaction.execute(
            "INSERT INTO guest_imports(user_id,import_id,snapshot_checksum,imported_at) VALUES(?,?,?,?)",
            params![user_id, import_id, checksum, now],
        )?;
        transaction.commit()?;
        self.snapshot(user_id)
    }
}

fn earlier(left: &Option<String>, right: &Option<String>) -> Option<String> {
    match (left, right) {
        (Some(left), Some(right)) => Some(
            if parsed_at(left) <= parsed_at(right) {
                left
            } else {
                right
            }
            .clone(),
        ),
        (Some(value), None) | (None, Some(value)) => Some(value.clone()),
        (None, None) => None,
    }
}

fn parsed_at(value: &str) -> DateTime<chrono::FixedOffset> {
    DateTime::parse_from_rfc3339(value).unwrap_or(DateTime::UNIX_EPOCH.fixed_offset())
}

fn merge_import_cards(account: StudyCard, guest: StudyCard, now: &str) -> StudyCard {
    let guest_due_wins = match (&account.due_at, &guest.due_at) {
        (None, Some(_)) => true,
        (Some(account_due), Some(guest_due)) => parsed_at(guest_due) < parsed_at(account_due),
        _ => false,
    };
    let played_from_guest = match (&account.last_played_at, &guest.last_played_at) {
        (None, Some(_)) => true,
        (Some(account_played), Some(guest_played)) => {
            parsed_at(guest_played) > parsed_at(account_played)
        }
        _ => false,
    };
    StudyCard {
        item_uuid: account.item_uuid.clone(),
        status: merge_mark_status(account.status, guest.status),
        mark_updated_at: Some(now.to_string()),
        enrolled_at: earlier(&account.enrolled_at, &guest.enrolled_at),
        due_at: if guest_due_wins {
            guest.due_at.clone()
        } else {
            account.due_at.clone()
        },
        review_level: if guest_due_wins {
            guest.review_level
        } else {
            account.review_level
        },
        last_reviewed_at: if guest_due_wins {
            guest.last_reviewed_at.clone()
        } else {
            account.last_reviewed_at.clone()
        },
        last_played_at: if played_from_guest {
            guest.last_played_at.clone()
        } else {
            account.last_played_at.clone()
        },
        preferred_book_code: if played_from_guest {
            guest.preferred_book_code.clone()
        } else {
            account.preferred_book_code.clone()
        },
        preferred_source_index: if played_from_guest {
            guest.preferred_source_index
        } else {
            account.preferred_source_index
        },
        updated_at: now.to_string(),
    }
}

fn upsert_card(conn: &Connection, user_id: i64, card: &StudyCard) -> Result<()> {
    conn.execute(
        r#"INSERT INTO study_cards(user_id,item_uuid,status,mark_updated_at,enrolled_at,due_at,review_level,
             last_reviewed_at,last_played_at,preferred_book_code,preferred_source_index,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,item_uuid) DO UPDATE SET
             status=excluded.status,mark_updated_at=excluded.mark_updated_at,enrolled_at=excluded.enrolled_at,
             due_at=excluded.due_at,review_level=excluded.review_level,last_reviewed_at=excluded.last_reviewed_at,
             last_played_at=excluded.last_played_at,preferred_book_code=excluded.preferred_book_code,
             preferred_source_index=excluded.preferred_source_index,updated_at=excluded.updated_at"#,
        params![user_id, card.item_uuid, card.status, card.mark_updated_at, card.enrolled_at,
            card.due_at, card.review_level, card.last_reviewed_at, card.last_played_at,
            card.preferred_book_code, card.preferred_source_index, card.updated_at],
    )?;
    Ok(())
}

fn merge_mark_status(account: MarkStatus, guest: MarkStatus) -> MarkStatus {
    if account == MarkStatus::Flagged || guest == MarkStatus::Flagged {
        MarkStatus::Flagged
    } else if account == MarkStatus::Known || guest == MarkStatus::Known {
        MarkStatus::Known
    } else {
        MarkStatus::Unmarked
    }
}

fn now_utc() -> String {
    Utc::now().to_rfc3339()
}

fn next_review_due_at(completed_at: DateTime<Utc>, level: i64) -> Result<DateTime<Utc>> {
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

fn get_card_optional(
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

#[cfg(test)]
mod tests;
