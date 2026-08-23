//! Per-user authentication and study state stored separately from vocabulary.

use anyhow::{Context, Result};
use chrono::Utc;
use rusqlite::Connection;
use rusqlite::types::{FromSql, FromSqlError, ToSql, ToSqlOutput, ValueRef};
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
mod guest_import;
mod schema;
mod study;

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
}

fn now_utc() -> String {
    Utc::now().to_rfc3339()
}

#[cfg(test)]
mod tests;
