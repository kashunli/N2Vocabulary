//! Per-user authentication and study state stored separately from vocabulary.

use anyhow::{Context, Result, bail};
use chrono::{DateTime, Utc};
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
mod study;

use study::get_card_optional;

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

#[cfg(test)]
mod tests;
