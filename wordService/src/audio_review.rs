use anyhow::{Context, Result, bail};
use chrono::Utc;
use rusqlite::{Connection, OptionalExtension, params};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

const DECISIONS: [&str; 4] = ["replace", "keep", "custom", "audio_problem"];

#[derive(Clone, Debug)]
pub struct AudioReviewStore {
    db_path: PathBuf,
    source_sha256: String,
    items: Arc<Vec<AudioReviewCandidate>>,
    item_positions: Arc<HashMap<i64, usize>>,
    write_lock: Arc<Mutex<()>>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct AudioReviewCandidate {
    pub source_index: i64,
    pub unit: i64,
    pub headword: String,
    pub classification: String,
    pub audit_score: f64,
    pub asr_vs_raw: f64,
    pub db_vs_raw: f64,
    pub evidence_margin: f64,
    pub expected: String,
    pub transcript: String,
    #[serde(default)]
    pub raw_line: String,
    #[serde(default)]
    pub raw_page: String,
    pub audio_clip: String,
}

#[derive(Clone, Debug, Deserialize)]
struct EvidenceBundle {
    version: i64,
    source_sha256: String,
    items: Vec<AudioReviewCandidate>,
}

#[derive(Clone, Debug, Deserialize)]
struct SeedPayload {
    source_sha256: String,
    decisions: Vec<SeedDecision>,
}

#[derive(Clone, Debug, Deserialize)]
struct SeedDecision {
    source_index: i64,
    decision: String,
    original_text: String,
    replacement_text: String,
    #[serde(default)]
    note: String,
    #[serde(default)]
    updated_at: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct AudioReviewUpdate {
    pub decision: String,
    #[serde(default)]
    pub replacement_text: String,
    #[serde(default)]
    pub note: String,
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct AudioReviewDecision {
    pub source_index: i64,
    pub decision: String,
    pub replacement_text: String,
    pub note: String,
    pub updated_at: String,
}

#[derive(Clone, Debug, Serialize)]
pub struct AudioReviewItem {
    #[serde(flatten)]
    pub candidate: AudioReviewCandidate,
    pub suggested_text: String,
    pub has_text_replacement: bool,
    pub audio_url: String,
    pub decision: Option<AudioReviewDecision>,
}

#[derive(Debug, Serialize)]
pub struct AudioReviewListResponse {
    pub version: i64,
    pub source_sha256: String,
    pub items: Vec<AudioReviewItem>,
    pub total: usize,
    pub reviewed: usize,
    pub pending: usize,
}

impl AudioReviewStore {
    pub fn load(
        db_path: impl Into<PathBuf>,
        evidence_path: &Path,
        seed_path: &Path,
    ) -> Result<Self> {
        let bundle: EvidenceBundle =
            serde_json::from_slice(&fs::read(evidence_path).with_context(|| {
                format!("read audio review evidence {}", evidence_path.display())
            })?)
            .context("parse audio review evidence")?;
        if bundle.version != 1 {
            bail!(
                "unsupported audio review evidence version: {}",
                bundle.version
            );
        }
        if bundle.source_sha256.trim().is_empty() {
            bail!("audio review evidence source_sha256 is empty");
        }
        if bundle.items.is_empty() {
            bail!("audio review evidence has no items");
        }

        let mut item_positions = HashMap::new();
        for (position, item) in bundle.items.iter().enumerate() {
            if item_positions.insert(item.source_index, position).is_some() {
                bail!("duplicate audio review source_index: {}", item.source_index);
            }
            validate_audio_clip(&item.audio_clip)?;
        }

        let store = Self {
            db_path: db_path.into(),
            source_sha256: bundle.source_sha256,
            items: Arc::new(bundle.items),
            item_positions: Arc::new(item_positions),
            write_lock: Arc::new(Mutex::new(())),
        };
        store.ensure_ready(seed_path)?;
        Ok(store)
    }

    pub fn list(&self) -> Result<AudioReviewListResponse> {
        let conn = self.connect()?;
        let mut statement = conn.prepare(
            r#"
            SELECT source_index, decision, replacement_text, note, updated_at
            FROM audio_review_decisions
            WHERE source_sha256 = ?
            ORDER BY source_index
            "#,
        )?;
        let rows = statement.query_map([&self.source_sha256], |row| {
            Ok(AudioReviewDecision {
                source_index: row.get(0)?,
                decision: row.get(1)?,
                replacement_text: row.get(2)?,
                note: row.get(3)?,
                updated_at: row.get(4)?,
            })
        })?;
        let decisions = rows
            .collect::<rusqlite::Result<Vec<_>>>()?
            .into_iter()
            .map(|decision| (decision.source_index, decision))
            .collect::<HashMap<_, _>>();

        let items = self
            .items
            .iter()
            .cloned()
            .map(|candidate| {
                let suggested_text = candidate.suggested_text().to_string();
                let has_text_replacement =
                    comparable_text(&suggested_text) != comparable_text(&candidate.expected);
                let audio_url = format!("/audio/{}", candidate.audio_clip.replace('\\', "/"));
                let decision = decisions.get(&candidate.source_index).cloned();
                AudioReviewItem {
                    candidate,
                    suggested_text,
                    has_text_replacement,
                    audio_url,
                    decision,
                }
            })
            .collect::<Vec<_>>();
        let reviewed = items.iter().filter(|item| item.decision.is_some()).count();
        let total = items.len();
        Ok(AudioReviewListResponse {
            version: 1,
            source_sha256: self.source_sha256.clone(),
            items,
            total,
            reviewed,
            pending: total - reviewed,
        })
    }

    pub fn set_decision(
        &self,
        source_index: i64,
        update: AudioReviewUpdate,
    ) -> Result<AudioReviewDecision> {
        let candidate = self
            .candidate(source_index)
            .context("unknown audio review item")?;
        let decision = update.decision.trim();
        if !DECISIONS.contains(&decision) {
            bail!("invalid audio review decision");
        }

        let replacement_text = match decision {
            "keep" | "audio_problem" => candidate.expected.clone(),
            "replace" => {
                let text = update.replacement_text.trim();
                if text.is_empty() {
                    bail!("replacement text cannot be empty");
                }
                if comparable_text(text) == comparable_text(&candidate.expected) {
                    bail!("replacement is equivalent to the original");
                }
                text.to_string()
            }
            "custom" => {
                let text = update.replacement_text.trim();
                if text.is_empty() {
                    bail!("custom text cannot be empty");
                }
                if comparable_text(text) == comparable_text(&candidate.expected) {
                    bail!("custom text is equivalent to the original");
                }
                text.to_string()
            }
            _ => unreachable!(),
        };
        let saved = AudioReviewDecision {
            source_index,
            decision: decision.to_string(),
            replacement_text,
            note: update.note.trim().to_string(),
            updated_at: Utc::now().to_rfc3339(),
        };

        let _guard = self
            .write_lock
            .lock()
            .expect("audio review write lock should not be poisoned");
        let conn = self.connect()?;
        conn.execute(
            r#"
            INSERT INTO audio_review_decisions(
              source_sha256, source_index, decision, replacement_text, note, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_sha256, source_index) DO UPDATE SET
              decision = excluded.decision,
              replacement_text = excluded.replacement_text,
              note = excluded.note,
              updated_at = excluded.updated_at
            "#,
            params![
                &self.source_sha256,
                saved.source_index,
                &saved.decision,
                &saved.replacement_text,
                &saved.note,
                &saved.updated_at,
            ],
        )?;
        Ok(saved)
    }

    pub fn clear_decision(&self, source_index: i64) -> Result<bool> {
        if self.candidate(source_index).is_none() {
            bail!("unknown audio review item");
        }
        let _guard = self
            .write_lock
            .lock()
            .expect("audio review write lock should not be poisoned");
        let conn = self.connect()?;
        let changed = conn.execute(
            "DELETE FROM audio_review_decisions WHERE source_sha256 = ? AND source_index = ?",
            params![&self.source_sha256, source_index],
        )?;
        Ok(changed > 0)
    }

    fn candidate(&self, source_index: i64) -> Option<&AudioReviewCandidate> {
        self.item_positions
            .get(&source_index)
            .map(|position| &self.items[*position])
    }

    fn connect(&self) -> Result<Connection> {
        let conn = Connection::open(&self.db_path)
            .with_context(|| format!("open audio review database {}", self.db_path.display()))?;
        conn.execute_batch("PRAGMA foreign_keys = ON; PRAGMA journal_mode = DELETE;")?;
        Ok(conn)
    }

    fn ensure_ready(&self, seed_path: &Path) -> Result<()> {
        if let Some(parent) = self.db_path.parent() {
            fs::create_dir_all(parent)?;
        }
        let _guard = self
            .write_lock
            .lock()
            .expect("audio review write lock should not be poisoned");
        let mut conn = self.connect()?;
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS audio_review_meta (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audio_review_decisions (
              source_sha256 TEXT NOT NULL,
              source_index INTEGER NOT NULL,
              decision TEXT NOT NULL CHECK(
                decision IN ('replace', 'keep', 'custom', 'audio_problem')
              ),
              replacement_text TEXT NOT NULL,
              note TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL,
              PRIMARY KEY(source_sha256, source_index)
            );
            "#,
        )?;

        if !seed_path.is_file() {
            return Ok(());
        }
        let marker = format!("seeded:{}", self.source_sha256);
        let already_seeded = conn
            .query_row(
                "SELECT 1 FROM audio_review_meta WHERE key = ?",
                [&marker],
                |_| Ok(()),
            )
            .optional()?
            .is_some();
        if already_seeded {
            return Ok(());
        }

        let seed: SeedPayload = serde_json::from_slice(
            &fs::read(seed_path)
                .with_context(|| format!("read audio review seed {}", seed_path.display()))?,
        )
        .context("parse audio review seed")?;
        if seed.source_sha256 != self.source_sha256 {
            bail!("audio review seed does not match evidence source_sha256");
        }

        let transaction = conn.transaction()?;
        for decision in seed.decisions {
            let candidate = self.candidate(decision.source_index).with_context(|| {
                format!(
                    "seed contains unknown source_index {}",
                    decision.source_index
                )
            })?;
            if decision.original_text != candidate.expected {
                bail!(
                    "seed original text is stale for source_index {}",
                    decision.source_index
                );
            }
            if !DECISIONS.contains(&decision.decision.as_str()) {
                bail!(
                    "seed has invalid decision for source_index {}",
                    decision.source_index
                );
            }
            let updated_at = if decision.updated_at.trim().is_empty() {
                Utc::now().to_rfc3339()
            } else {
                decision.updated_at
            };
            transaction.execute(
                r#"
                INSERT OR IGNORE INTO audio_review_decisions(
                  source_sha256, source_index, decision, replacement_text, note, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                "#,
                params![
                    &self.source_sha256,
                    decision.source_index,
                    decision.decision,
                    decision.replacement_text,
                    decision.note,
                    updated_at,
                ],
            )?;
        }
        transaction.execute(
            "INSERT INTO audio_review_meta(key, value) VALUES(?, ?)",
            params![marker, Utc::now().to_rfc3339()],
        )?;
        transaction.commit()?;
        Ok(())
    }
}

impl AudioReviewCandidate {
    fn suggested_text(&self) -> &str {
        if !self.raw_line.trim().is_empty() {
            &self.raw_line
        } else if !self.transcript.trim().is_empty() {
            &self.transcript
        } else {
            &self.expected
        }
    }
}

fn comparable_text(value: &str) -> String {
    value
        .chars()
        .filter(|character| {
            !character.is_whitespace()
                && !"、。！？!?「」『』（）()［］[]・…〜～,./".contains(*character)
        })
        .collect()
}

fn validate_audio_clip(value: &str) -> Result<()> {
    let normalized = value.replace('\\', "/");
    if !normalized.starts_with("clips/") {
        bail!("audio review clip must start with clips/: {value}");
    }
    if normalized
        .split('/')
        .any(|part| part.is_empty() || part == "." || part == ".." || part.contains(':'))
    {
        bail!("invalid audio review clip path: {value}");
    }
    Ok(())
}
