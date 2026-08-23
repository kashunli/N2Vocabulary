use super::{AuthContext, AuthUser, NewSession, SESSION_DAYS, UserStore, now_utc};
use anyhow::{Result, bail};
use argon2::Argon2;
use argon2::password_hash::{
    PasswordHash, PasswordHasher, PasswordVerifier, SaltString, rand_core::OsRng,
};
use chrono::{Duration, Utc};
use rand::random;
use rusqlite::{Connection, OptionalExtension, params};
use sha2::{Digest, Sha256};
use std::time::{Duration as StdDuration, Instant};

impl UserStore {
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
