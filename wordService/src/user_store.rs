//! Per-user authentication and study state stored separately from vocabulary.

use crate::scheduler::{ReviewGrade, initial_due_at, schedule_review};
use anyhow::{Context, Result, bail};
use argon2::Argon2;
use argon2::password_hash::{
    PasswordHash, PasswordHasher, PasswordVerifier, SaltString, rand_core::OsRng,
};
use chrono::{Duration, Utc};
use rand::random;
use rusqlite::{Connection, OptionalExtension, params};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration as StdDuration, Instant};

pub const SESSION_COOKIE: &str = "n2_word_session";
const SESSION_DAYS: i64 = 30;

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

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
pub struct StudyCard {
    pub item_uuid: String,
    pub known: bool,
    pub flagged: bool,
    pub enrolled_at: Option<String>,
    pub due_at: Option<String>,
    pub good_step: u8,
    pub last_reviewed_at: Option<String>,
    pub last_played_at: Option<String>,
    pub preferred_book_code: Option<String>,
    pub preferred_source_index: Option<i64>,
    pub updated_at: String,
}

#[derive(Debug, Serialize)]
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

    pub fn ensure_ready(&self) -> Result<()> {
        if let Some(parent) = self.db_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let conn = self.connect()?;
        conn.execute_batch(
            r#"
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
              token_hash TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              csrf_token TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              last_used_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS study_cards (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              item_uuid TEXT NOT NULL,
              known INTEGER NOT NULL DEFAULT 0 CHECK(known IN (0,1)),
              flagged INTEGER NOT NULL DEFAULT 0 CHECK(flagged IN (0,1)),
              enrolled_at TEXT,
              due_at TEXT,
              good_step INTEGER NOT NULL DEFAULT 0 CHECK(good_step BETWEEN 0 AND 6),
              last_reviewed_at TEXT,
              last_played_at TEXT,
              preferred_book_code TEXT,
              preferred_source_index INTEGER,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(user_id, item_uuid)
            );
            CREATE TABLE IF NOT EXISTS guest_imports (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              import_id TEXT NOT NULL,
              snapshot_checksum TEXT NOT NULL,
              imported_at TEXT NOT NULL,
              PRIMARY KEY(user_id, import_id)
            );
            CREATE INDEX IF NOT EXISTS study_cards_due ON study_cards(user_id, due_at);
            CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
            "#,
        )?;
        Ok(())
    }

    fn connect(&self) -> Result<Connection> {
        let conn = Connection::open(&self.db_path)
            .with_context(|| format!("open user database {}", self.db_path.display()))?;
        conn.execute_batch("PRAGMA foreign_keys = ON; PRAGMA busy_timeout = 5000;")?;
        Ok(conn)
    }

    pub fn register(&self, email: &str, password: &str) -> Result<NewSession> {
        let email = normalize_email(email)?;
        validate_password(password)?;
        let salt = SaltString::generate(&mut OsRng);
        let password_hash = Argon2::default()
            .hash_password(password.as_bytes(), &salt)
            .map_err(|error| anyhow::anyhow!(error.to_string()))?
            .to_string();
        let _guard = self.write_lock.lock().expect("user write lock");
        let conn = self.connect()?;
        let now = now_utc();
        conn.execute(
            "INSERT INTO users(email,password_hash,created_at,updated_at) VALUES(?,?,?,?)",
            params![email, password_hash, now, now],
        )
        .map_err(|error| {
            anyhow::anyhow!(if error.to_string().contains("UNIQUE") {
                "email already registered".to_string()
            } else {
                error.to_string()
            })
        })?;
        let user = AuthUser {
            id: conn.last_insert_rowid(),
            email,
        };
        create_session(&conn, user)
    }

    pub fn login(&self, email: &str, password: &str) -> Result<NewSession> {
        let email = normalize_email(email)?;
        {
            let mut failures = self.login_failures.lock().expect("login failure lock");
            if let Some((count, started)) = failures.get(&email) {
                if *count >= 5 && started.elapsed() < StdDuration::from_secs(60) {
                    bail!("too many login attempts; try again shortly");
                }
                if started.elapsed() >= StdDuration::from_secs(60) {
                    failures.remove(&email);
                }
            }
        }
        let _guard = self.write_lock.lock().expect("user write lock");
        let conn = self.connect()?;
        let row: Option<(i64, String)> = conn
            .query_row(
                "SELECT id,password_hash FROM users WHERE email=?",
                [&email],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;
        let valid = row.as_ref().is_some_and(|(_, hash)| {
            PasswordHash::new(hash).ok().is_some_and(|parsed| {
                Argon2::default()
                    .verify_password(password.as_bytes(), &parsed)
                    .is_ok()
            })
        });
        if !valid {
            let mut failures = self.login_failures.lock().expect("login failure lock");
            let entry = failures.entry(email).or_insert((0, Instant::now()));
            entry.0 += 1;
            bail!("invalid email or password");
        }
        self.login_failures
            .lock()
            .expect("login failure lock")
            .remove(&email);
        create_session(
            &conn,
            AuthUser {
                id: row.unwrap().0,
                email,
            },
        )
    }

    pub fn authenticate(&self, token: &str) -> Result<Option<AuthContext>> {
        if token.is_empty() {
            return Ok(None);
        }
        let token_hash = hash_token(token);
        let _guard = self.write_lock.lock().expect("user write lock");
        let conn = self.connect()?;
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", [now_utc()])?;
        let context = conn
            .query_row(
                r#"SELECT u.id,u.email,s.csrf_token FROM sessions s
               JOIN users u ON u.id=s.user_id WHERE s.token_hash=?"#,
                [&token_hash],
                |row| {
                    Ok(AuthContext {
                        user: AuthUser {
                            id: row.get(0)?,
                            email: row.get(1)?,
                        },
                        csrf_token: row.get(2)?,
                        session_token_hash: token_hash.clone(),
                    })
                },
            )
            .optional()?;
        if context.is_some() {
            conn.execute(
                "UPDATE sessions SET last_used_at=? WHERE token_hash=?",
                params![now_utc(), token_hash],
            )?;
        }
        Ok(context)
    }

    pub fn logout(&self, token_hash: &str) -> Result<()> {
        let _guard = self.write_lock.lock().expect("user write lock");
        self.connect()?
            .execute("DELETE FROM sessions WHERE token_hash=?", [token_hash])?;
        Ok(())
    }

    pub fn snapshot(&self, user_id: i64) -> Result<StudySnapshot> {
        let conn = self.connect()?;
        let mut statement = conn.prepare(
            r#"SELECT item_uuid,known,flagged,enrolled_at,due_at,good_step,last_reviewed_at,
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
            version: 1,
            updated_at,
            cards,
        })
    }

    pub fn set_marks(
        &self,
        user_id: i64,
        item_uuid: &str,
        known: bool,
        flagged: bool,
    ) -> Result<StudyCard> {
        let _guard = self.write_lock.lock().expect("user write lock");
        let conn = self.connect()?;
        let now = now_utc();
        conn.execute(
            r#"INSERT INTO study_cards(user_id,item_uuid,known,flagged,good_step,updated_at)
               VALUES(?,?,?,?,0,?) ON CONFLICT(user_id,item_uuid) DO UPDATE SET
               known=excluded.known, flagged=excluded.flagged, updated_at=excluded.updated_at"#,
            params![user_id, item_uuid, int(known), int(flagged), now],
        )?;
        get_card(&conn, user_id, item_uuid)
    }

    pub fn record_played(
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
        let due = initial_due_at(now).to_rfc3339();
        conn.execute(
            r#"INSERT INTO study_cards(user_id,item_uuid,known,flagged,enrolled_at,due_at,good_step,
                    last_played_at,preferred_book_code,preferred_source_index,updated_at)
               VALUES(?,?,0,0,?,?,0,?,?,?,?)
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
                due,
                now_text,
                book,
                source_index,
                now_text
            ],
        )?;
        get_card(&conn, user_id, item_uuid)
    }

    pub fn grade(&self, user_id: i64, item_uuid: &str, grade: ReviewGrade) -> Result<StudyCard> {
        let _guard = self.write_lock.lock().expect("user write lock");
        let conn = self.connect()?;
        let current = get_card(&conn, user_id, item_uuid)?;
        if current.enrolled_at.is_none() {
            bail!("cannot grade an unenrolled card");
        }
        let reviewed_at = Utc::now();
        let result = schedule_review(current.good_step, grade, reviewed_at);
        conn.execute(
            r#"UPDATE study_cards SET known=?,flagged=?,good_step=?,due_at=?,
                    last_reviewed_at=?,updated_at=? WHERE user_id=? AND item_uuid=?"#,
            params![
                int(current.known || result.set_known),
                int(current.flagged || result.set_flagged),
                result.good_step,
                result.due_at.to_rfc3339(),
                reviewed_at.to_rfc3339(),
                reviewed_at.to_rfc3339(),
                user_id,
                item_uuid
            ],
        )?;
        get_card(&conn, user_id, item_uuid)
    }
}

fn normalize_email(email: &str) -> Result<String> {
    let email = email.trim().to_lowercase();
    if email.len() > 254 || !email.contains('@') || email.starts_with('@') || email.ends_with('@') {
        bail!("enter a valid email address");
    }
    Ok(email)
}

fn validate_password(password: &str) -> Result<()> {
    if password.len() < 8 || password.len() > 256 {
        bail!("password must be 8 to 256 characters");
    }
    Ok(())
}

fn create_session(conn: &Connection, user: AuthUser) -> Result<NewSession> {
    let token = random_hex();
    let csrf_token = random_hex();
    let now = Utc::now();
    conn.execute(
        "INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at,created_at,last_used_at) VALUES(?,?,?,?,?,?)",
        params![hash_token(&token), user.id, csrf_token, (now + Duration::days(SESSION_DAYS)).to_rfc3339(), now.to_rfc3339(), now.to_rfc3339()],
    )?;
    Ok(NewSession {
        user,
        token,
        csrf_token,
    })
}

fn random_hex() -> String {
    random::<[u8; 32]>()
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}
fn hash_token(value: &str) -> String {
    format!("{:x}", Sha256::digest(value.as_bytes()))
}
fn now_utc() -> String {
    Utc::now().to_rfc3339()
}
fn int(value: bool) -> i64 {
    if value { 1 } else { 0 }
}

fn row_to_card(row: &rusqlite::Row<'_>) -> rusqlite::Result<StudyCard> {
    Ok(StudyCard {
        item_uuid: row.get(0)?,
        known: row.get::<_, i64>(1)? != 0,
        flagged: row.get::<_, i64>(2)? != 0,
        enrolled_at: row.get(3)?,
        due_at: row.get(4)?,
        good_step: row.get(5)?,
        last_reviewed_at: row.get(6)?,
        last_played_at: row.get(7)?,
        preferred_book_code: row.get(8)?,
        preferred_source_index: row.get(9)?,
        updated_at: row.get(10)?,
    })
}

fn get_card(conn: &Connection, user_id: i64, item_uuid: &str) -> Result<StudyCard> {
    conn.query_row(
        r#"SELECT item_uuid,known,flagged,enrolled_at,due_at,good_step,last_reviewed_at,
                  last_played_at,preferred_book_code,preferred_source_index,updated_at
           FROM study_cards WHERE user_id=? AND item_uuid=?"#,
        params![user_id, item_uuid],
        row_to_card,
    )
    .context("study card not found")
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn fixture() -> (TempDir, UserStore) {
        let dir = TempDir::new().unwrap();
        let store = UserStore::new(dir.path().join("users.sqlite"));
        store.ensure_ready().unwrap();
        (dir, store)
    }

    #[test]
    fn accounts_are_isolated_and_sessions_store_only_token_hashes() {
        let (_dir, store) = fixture();
        let first = store
            .register(" Test@Example.com ", "password-one")
            .unwrap();
        let second = store.register("other@example.com", "password-two").unwrap();
        assert_eq!(first.user.email, "test@example.com");
        store
            .set_marks(first.user.id, "shared", true, false)
            .unwrap();
        assert!(store.snapshot(first.user.id).unwrap().cards["shared"].known);
        assert!(store.snapshot(second.user.id).unwrap().cards.is_empty());
        let conn = Connection::open(store.db_path()).unwrap();
        let stored: String = conn
            .query_row(
                "SELECT token_hash FROM sessions WHERE user_id=?",
                [first.user.id],
                |row| row.get(0),
            )
            .unwrap();
        assert_ne!(stored, first.token);
        assert!(store.authenticate(&first.token).unwrap().is_some());
    }

    #[test]
    fn played_and_grade_updates_are_durable_and_atomic() {
        let (_dir, store) = fixture();
        let session = store.register("review@example.com", "password").unwrap();
        let played = store
            .record_played(session.user.id, "item", "N2", 7)
            .unwrap();
        assert!(played.due_at.is_some());
        let hard = store
            .grade(session.user.id, "item", ReviewGrade::Hard)
            .unwrap();
        assert!(hard.flagged);
        let good = store
            .grade(session.user.id, "item", ReviewGrade::Good)
            .unwrap();
        assert!(good.known && good.flagged);
    }
}
