use super::*;
use tempfile::TempDir;

fn fixture() -> (TempDir, UserStore) {
    let dir = TempDir::new().unwrap();
    let store = UserStore::new(dir.path().join("users.sqlite"));
    store.ensure_ready().unwrap();
    (dir, store)
}

#[test]
fn legacy_boolean_table_is_rebuilt_with_flagged_precedence() {
    let dir = TempDir::new().unwrap();
    let path = dir.path().join("legacy.sqlite");
    let conn = Connection::open(&path).unwrap();
    conn.execute_batch(
        r#"
            PRAGMA foreign_keys = ON;
            CREATE TABLE users (
              id INTEGER PRIMARY KEY,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE study_cards (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              item_uuid TEXT NOT NULL,
              known INTEGER NOT NULL DEFAULT 0 CHECK(known IN (0,1)),
              flagged INTEGER NOT NULL DEFAULT 0 CHECK(flagged IN (0,1)),
              enrolled_at TEXT,
              due_at TEXT,
              good_step INTEGER NOT NULL DEFAULT 0 CHECK(good_step BETWEEN 0 AND 6),
              review_level INTEGER NOT NULL DEFAULT 0 CHECK(review_level >= 0),
              last_reviewed_at TEXT,
              last_played_at TEXT,
              preferred_book_code TEXT,
              preferred_source_index INTEGER,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(user_id, item_uuid)
            );
            INSERT INTO users(id,email,password_hash,created_at,updated_at)
            VALUES(1,'legacy@example.com','hash','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z');
            INSERT INTO study_cards(
              user_id,item_uuid,known,flagged,enrolled_at,due_at,good_step,review_level,
              last_reviewed_at,last_played_at,preferred_book_code,preferred_source_index,updated_at
            ) VALUES(
              1,'both',1,1,'2026-01-01T00:00:00Z','2026-01-02T00:00:00Z',4,4,
              '2026-01-01T00:00:00Z','2026-01-01T00:00:00Z','N2',7,'2026-01-03T00:00:00Z'
            );
            "#,
    )
    .unwrap();
    drop(conn);

    let store = UserStore::new(path);
    store.ensure_ready().unwrap();
    let card = &store.snapshot(1).unwrap().cards["both"];
    assert_eq!(card.status, MarkStatus::Flagged);
    assert!(card.enrolled_at.is_none());
    assert!(card.due_at.is_none());

    let conn = Connection::open(store.db_path()).unwrap();
    let columns = conn
        .prepare("PRAGMA table_info(study_cards)")
        .unwrap()
        .query_map([], |row| row.get::<_, String>(1))
        .unwrap()
        .collect::<std::result::Result<Vec<_>, _>>()
        .unwrap();
    assert!(columns.iter().any(|column| column == "status"));
    assert!(!columns.iter().any(|column| column == "known"));
    assert!(!columns.iter().any(|column| column == "flagged"));
    assert!(!columns.iter().any(|column| column == "good_step"));
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
        .set_mark_status(first.user.id, "shared", MarkStatus::Known)
        .unwrap();
    assert_eq!(
        store.snapshot(first.user.id).unwrap().cards["shared"].status,
        MarkStatus::Known
    );
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
fn expired_sessions_are_rejected_and_deleted() {
    let (_dir, store) = fixture();
    let session = store.register("expired@example.com", "password").unwrap();
    let conn = Connection::open(store.db_path()).unwrap();
    conn.execute(
        "UPDATE sessions SET expires_at=? WHERE user_id=?",
        params!["2000-01-01T00:00:00Z", session.user.id],
    )
    .unwrap();
    assert!(store.authenticate(&session.token).unwrap().is_none());
    let remaining: i64 = conn
        .query_row("SELECT COUNT(*) FROM sessions", [], |row| row.get(0))
        .unwrap();
    assert_eq!(remaining, 0);
}

#[test]
fn marks_do_not_enroll_and_normal_study_creates_level_zero_due_state() {
    let (_dir, store) = fixture();
    let session = store.register("review@example.com", "password").unwrap();
    let marked = store
        .set_mark_status(session.user.id, "item", MarkStatus::Flagged)
        .unwrap();
    assert_eq!(marked.status, MarkStatus::Flagged);
    assert!(marked.enrolled_at.is_none());
    assert!(marked.due_at.is_none());
    let played = store
        .record_study_completed(session.user.id, "item", "N2", 7)
        .unwrap();
    assert!(played.due_at.is_some());
    assert_eq!(played.review_level, 0);
    assert_eq!(played.status, MarkStatus::Flagged);
}

#[test]
fn normal_study_replay_does_not_postpone_an_existing_review() {
    let (_dir, store) = fixture();
    let session = store.register("replay@example.com", "password").unwrap();
    let first = store
        .record_study_completed(session.user.id, "item", "N2", 7)
        .unwrap();
    let replayed = store
        .record_study_completed(session.user.id, "item", "GWB_N2", 44)
        .unwrap();
    assert_eq!(replayed.review_level, 0);
    assert_eq!(replayed.due_at, first.due_at);
    assert_eq!(replayed.preferred_book_code.as_deref(), Some("GWB_N2"));
}

#[test]
fn review_completion_advances_once_and_rejects_a_stale_due_time() {
    let (_dir, store) = fixture();
    let session = store.register("level@example.com", "password").unwrap();
    store
        .record_study_completed(session.user.id, "item", "N2", 7)
        .unwrap();
    let expected_due = "2026-08-12T00:00:00+00:00";
    let conn = Connection::open(store.db_path()).unwrap();
    conn.execute(
            "UPDATE study_cards SET due_at=?, enrolled_at=?, review_level=0 WHERE user_id=? AND item_uuid=?",
            params![expected_due, "2026-08-11T00:00:00+00:00", session.user.id, "item"],
        )
        .unwrap();
    let now = DateTime::parse_from_rfc3339("2026-08-13T00:00:00+00:00")
        .unwrap()
        .with_timezone(&Utc);
    let completed = store
        .complete_review_at(session.user.id, "item", expected_due, "N2", 7, now)
        .unwrap();
    let ReviewCompletion::Completed(card) = completed else {
        panic!("expected completion");
    };
    assert_eq!(card.review_level, 1);
    assert_eq!(card.due_at.as_deref(), Some("2026-08-15T00:00:00+00:00"));
    assert_eq!(
        card.last_reviewed_at.as_deref(),
        Some("2026-08-13T00:00:00+00:00")
    );
    assert!(matches!(
        store
            .complete_review_at(session.user.id, "item", expected_due, "N2", 7, now)
            .unwrap(),
        ReviewCompletion::Conflict(Some(_))
    ));
}

#[test]
fn review_interval_doubles_with_checked_bounds() {
    let start = DateTime::parse_from_rfc3339("2026-08-13T00:00:00+00:00")
        .unwrap()
        .with_timezone(&Utc);
    assert_eq!(
        next_review_due_at(start, 0).unwrap(),
        start + Duration::days(1)
    );
    assert_eq!(
        next_review_due_at(start, 1).unwrap(),
        start + Duration::days(2)
    );
    assert_eq!(
        next_review_due_at(start, 5).unwrap(),
        start + Duration::days(32)
    );
    assert!(next_review_due_at(start, 63).is_err());
}

#[test]
fn migration_clears_old_schedules_but_preserves_tags() {
    let (_dir, store) = fixture();
    let session = store.register("migrate@example.com", "password").unwrap();
    store
        .set_mark_status(session.user.id, "item", MarkStatus::Flagged)
        .unwrap();
    let conn = Connection::open(store.db_path()).unwrap();
    conn.execute(
            "UPDATE study_cards SET enrolled_at=?,due_at=?,review_level=4,last_reviewed_at=? WHERE user_id=? AND item_uuid=?",
            params!["2026-08-01T00:00:00Z", "2026-08-02T00:00:00Z", "2026-08-01T00:00:00Z", session.user.id, "item"],
        )
        .unwrap();
    conn.execute(
        "DELETE FROM study_schema_migrations WHERE name=?",
        [SPACED_REVIEW_MIGRATION],
    )
    .unwrap();
    store.ensure_ready().unwrap();
    let card = &store.snapshot(session.user.id).unwrap().cards["item"];
    assert_eq!(card.status, MarkStatus::Flagged);
    assert!(card.enrolled_at.is_none() && card.due_at.is_none());
    assert_eq!(card.review_level, 0);
    assert!(card.last_reviewed_at.is_none());
}

#[test]
fn guest_import_is_conservative_and_idempotent() {
    let (_dir, store) = fixture();
    let session = store.register("import@example.com", "password").unwrap();
    store
        .set_mark_status(session.user.id, "item", MarkStatus::Flagged)
        .unwrap();
    let guest = StudyCard {
        item_uuid: "item".into(),
        status: MarkStatus::Known,
        mark_updated_at: Some("2026-01-01T00:00:00Z".into()),
        enrolled_at: Some("2026-01-01T00:00:00Z".into()),
        due_at: Some("2026-01-02T00:00:00Z".into()),
        review_level: 1,
        last_reviewed_at: Some("2026-01-01T00:00:00Z".into()),
        last_played_at: Some("2026-01-01T00:00:00Z".into()),
        preferred_book_code: Some("N2".into()),
        preferred_source_index: Some(7),
        updated_at: "2026-01-01T00:00:00Z".into(),
    };
    let snapshot = store
        .import_guest(
            session.user.id,
            "once",
            "abc",
            STUDY_STATE_VERSION,
            vec![guest.clone()],
        )
        .unwrap();
    let card = &snapshot.cards["item"];
    assert_eq!(card.status, MarkStatus::Flagged);
    assert_eq!(card.preferred_source_index, Some(7));
    assert_eq!(
        store
            .import_guest(
                session.user.id,
                "once",
                "abc",
                STUDY_STATE_VERSION,
                vec![guest]
            )
            .unwrap()
            .cards
            .len(),
        1
    );
    assert!(
        store
            .import_guest(
                session.user.id,
                "once",
                "different",
                STUDY_STATE_VERSION,
                vec![]
            )
            .is_err()
    );
}
