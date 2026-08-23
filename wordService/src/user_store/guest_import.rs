use super::study::get_card_optional;
use super::{
    MarkStatus, SPACED_REVIEW_STATE_VERSION, StudyCard, StudySnapshot, UserStore, now_utc,
};
use anyhow::{Result, bail};
use chrono::DateTime;
use rusqlite::{Connection, OptionalExtension, params};

impl UserStore {
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
