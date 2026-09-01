use n2_word_service_rust::repository::WordRepository;
use rusqlite::{Connection, OptionalExtension};
use serde_json::Value as JsonValue;
use std::fs;

#[path = "support/repository.rs"]
mod support;
use support::{Fixture, assert_versioned_audio_url};

#[test]
fn summary_and_units_include_mark_counts() {
    let fixture = Fixture::new();

    let summary = fixture.repo.get_summary().unwrap();
    assert_eq!(summary.entries, 4);
    assert_eq!(summary.units, 2);
    assert_eq!(summary.known, 1);
    assert_eq!(summary.flagged, 0);
    assert_eq!(summary.unmarked, 3);
    assert!(
        !summary.content_revision.is_empty(),
        "summary should carry a content revision for the client cache"
    );

    let unit = fixture.repo.list_units().unwrap().remove(0);
    assert_eq!(unit.entry_count, 2);
    assert_eq!(unit.known, 1);
}

#[test]
fn content_revision_is_stable_across_handles_and_ensure_ready() {
    let fixture = Fixture::new();
    let first = fixture.repo.get_summary().unwrap().content_revision;
    assert!(
        !first.is_empty(),
        "content revision should be a fingerprint of the database"
    );

    // A second handle over the same database shares the same cached revision.
    let second = WordRepository::new(fixture.db_path.clone(), fixture.clips_dir.clone(), "N2");
    assert_eq!(second.get_summary().unwrap().content_revision, first);

    // ensure_ready may run startup migrations; the in-process revision must not
    // change even if those writes touch the file.
    fixture.repo.ensure_ready().unwrap();
    assert_eq!(fixture.repo.get_summary().unwrap().content_revision, first);
}

#[test]
fn content_revision_changes_for_a_fresh_process_after_a_content_edit() {
    let fixture = Fixture::new();
    let before = fixture.repo.get_summary().unwrap().content_revision;
    {
        let conn = Connection::open(&fixture.db_path).unwrap();
        conn.execute(
            "UPDATE vocabulary_items SET meaning_en = 'changed' WHERE item_id = 1",
            [],
        )
        .unwrap();
    }
    // A brand-new handle (a fresh process with no cached revision) recomputes and
    // sees the changed file, so the browser refetches after an offline edit.
    let fresh = WordRepository::new(fixture.db_path.clone(), fixture.clips_dir.clone(), "N2");
    let after = fresh.get_summary().unwrap().content_revision;
    assert_ne!(after, before);
    // The original handle still serves its cached revision for this process.
    assert_eq!(fixture.repo.get_summary().unwrap().content_revision, before);
}

#[test]
fn ensure_ready_normalizes_legacy_dual_marks_and_is_idempotent() {
    let fixture = Fixture::new();
    {
        let conn = Connection::open(&fixture.db_path).unwrap();
        conn.execute(
            "UPDATE item_marks SET known = 1, flagged = 1 WHERE item_id = 1",
            [],
        )
        .unwrap();
        conn.execute(
            "UPDATE word_marks SET known = 1, flagged = 1 WHERE entry_id = 1",
            [],
        )
        .unwrap();
    }

    fixture.repo.ensure_ready().unwrap();
    let conn = Connection::open(&fixture.db_path).unwrap();
    let item_mark: (i64, i64) = conn
        .query_row(
            "SELECT known, flagged FROM item_marks WHERE item_id = 1",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap();
    let word_mark: (i64, i64) = conn
        .query_row(
            "SELECT known, flagged FROM word_marks WHERE entry_id = 1",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap();
    assert_eq!(item_mark, (0, 1));
    assert_eq!(word_mark, (0, 1));
    assert_eq!(
        conn.query_row(
            "SELECT COUNT(*) FROM word_service_migrations WHERE name = 'exclusive-mark-v1'",
            [],
            |row| row.get::<_, i64>(0),
        )
        .unwrap(),
        1
    );

    drop(conn);
    fixture.repo.ensure_ready().unwrap();
    let conn = Connection::open(&fixture.db_path).unwrap();
    assert_eq!(
        conn.query_row(
            "SELECT COUNT(*) FROM item_marks WHERE known = 1 AND flagged = 1",
            [],
            |row| row.get::<_, i64>(0),
        )
        .unwrap(),
        0
    );
}

#[test]
fn deprecated_mark_writer_gives_flagged_precedence() {
    let fixture = Fixture::new();

    fixture.repo.set_mark(1, true, true).unwrap();

    let conn = Connection::open(&fixture.db_path).unwrap();
    let mark: (i64, i64) = conn
        .query_row(
            "SELECT known, flagged FROM item_marks WHERE item_id = 1",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .unwrap();
    assert_eq!(mark, (0, 1));
}

#[test]
fn entry_listing_search_and_state_filters() {
    let fixture = Fixture::new();

    let known = fixture.repo.list_entries(Some(1), "known", "").unwrap();
    assert_eq!(known.items[0].entry_id, 1);

    let unmarked = fixture.repo.list_entries(Some(1), "unmarked", "").unwrap();
    assert_eq!(unmarked.items[0].entry_id, 2);

    let searched = fixture.repo.list_entries(Some(1), "all", "happy").unwrap();
    assert_eq!(searched.items[0].entry_id, 1);

    fixture.repo.set_mark(4, false, true).unwrap();

    let global_known = fixture.repo.list_entries(None, "known", "").unwrap();
    assert_eq!(
        global_known
            .items
            .iter()
            .map(|entry| entry.entry_id)
            .collect::<Vec<_>>(),
        vec![1]
    );

    let global_flagged = fixture.repo.list_entries(None, "flagged", "").unwrap();
    assert_eq!(
        global_flagged
            .items
            .iter()
            .map(|entry| entry.entry_id)
            .collect::<Vec<_>>(),
        vec![4]
    );

    let global_unmarked = fixture.repo.list_entries(None, "unmarked", "").unwrap();
    assert_eq!(
        global_unmarked
            .items
            .iter()
            .map(|entry| entry.entry_id)
            .collect::<Vec<_>>(),
        vec![2, 3]
    );
}

#[test]
fn review_resolution_uses_shared_uuid_and_legacy_seed_is_unique() {
    let fixture = Fixture::new();
    let listed = fixture.repo.list_entries(Some(1), "all", "").unwrap();
    let shared_uuid = listed.items[0].item_uuid.clone();
    assert_eq!(shared_uuid, "uuid-1");

    let resolved = fixture
        .repo
        .resolve_item_for_review(&shared_uuid, Some("N2"), Some(1))
        .unwrap()
        .expect("shared review item");
    assert_eq!(resolved.entry_id, 1);
    assert_eq!(resolved.item_uuid, shared_uuid);

    let seed = fixture.repo.legacy_mark_seed().unwrap();
    assert_eq!(seed.items.len(), 1);
    assert_eq!(seed.items[0].item_uuid, "uuid-1");
    assert!(seed.items[0].known);
    assert!(!seed.items[0].flagged);
}

#[test]
fn entry_listing_can_search_current_unit_or_all_units() {
    let fixture = Fixture::new();

    let unit_scoped = fixture.repo.list_entries(Some(1), "all", "覆う").unwrap();
    assert_eq!(
        unit_scoped
            .items
            .iter()
            .map(|entry| entry.entry_id)
            .collect::<Vec<_>>(),
        vec![1]
    );

    let global = fixture.repo.list_entries(None, "all", "覆う").unwrap();
    assert_eq!(
        global
            .items
            .iter()
            .map(|entry| entry.entry_id)
            .collect::<Vec<_>>(),
        vec![1, 3, 4]
    );

    let entry_one_matches = global.items[0]
        .search_matches
        .as_ref()
        .expect("entry one should include matching examples");
    assert_eq!(entry_one_matches.len(), 1);
    assert_eq!(entry_one_matches[0].position, 2);
    assert_eq!(entry_one_matches[0].text, "不安が人生を覆う。");

    let entry_three_matches = global.items[1]
        .search_matches
        .as_ref()
        .expect("inflected example should match the searched verb stem");
    assert_eq!(entry_three_matches.len(), 1);
    assert_eq!(entry_three_matches[0].text, "山頂は雪で覆われていた。");

    let no_search = fixture.repo.list_entries(None, "all", "").unwrap();
    assert!(
        no_search
            .items
            .iter()
            .all(|entry| entry.search_matches.is_none())
    );
    let serialized = serde_json::to_value(&no_search.items[0]).unwrap();
    assert_eq!(serialized.get("search_matches"), None::<&JsonValue>);
    assert_eq!(
        no_search.items[0].word_audio_url.as_deref(),
        Some("/audio/clips/words/word1.mp3")
    );
    assert_eq!(
        no_search.items[0].sentence_audio_url.as_deref(),
        Some("/audio/clips/sentences/sentence1.mp3")
    );

    let list_examples = no_search.items[0]
        .examples
        .as_ref()
        .expect("card list payload should include extra examples");
    assert_eq!(
        list_examples
            .iter()
            .map(|example| example.position)
            .collect::<Vec<_>>(),
        vec![1, 2]
    );
    assert_eq!(list_examples[0].text, "人生経験が豊富だ。");
}

#[test]
fn card_payload_keeps_book_specific_main_sentence_at_its_real_position() {
    let fixture = Fixture::new();
    let conn = Connection::open(&fixture.db_path).unwrap();
    conn.execute(
        "UPDATE book_entries SET sentence = '人生経験が豊富だ。' WHERE book_code = 'N2' AND entry_id = 1",
        [],
    )
    .unwrap();
    drop(conn);

    let listed = fixture.repo.list_entries(Some(1), "all", "人生").unwrap();
    let entry = listed
        .items
        .iter()
        .find(|entry| entry.entry_id == 1)
        .expect("entry exists");
    assert_eq!(entry.sentence, "人生経験が豊富だ。");
    assert_eq!(entry.sentence_translation_en, "Has rich life experience.");
    assert_eq!(entry.sentence_position, 1);

    let examples = entry.examples.as_ref().expect("card examples");
    assert!(
        examples.iter().all(|example| example.position != 1),
        "the selected main stays in compact top-level fields"
    );
    assert_eq!(
        examples
            .iter()
            .find(|example| example.position == 0)
            .expect("the shared sentence remains available as an extra")
            .text,
        "幸せな人生を送る。"
    );
}

#[test]
fn mimikara_main_sentences_take_priority_in_n1_n2_n3_order() {
    let fixture = Fixture::new();
    for clip in ["n1-main.mp3", "n3-main.mp3", "gwb-main.mp3"] {
        fs::write(fixture.clips_dir.join("sentences").join(clip), clip).unwrap();
        fixture
            .repo
            .record_audio_id(&format!("clips/sentences/{clip}"))
            .unwrap();
    }

    let conn = Connection::open(&fixture.db_path).unwrap();
    conn.execute_batch(
        r#"
        INSERT INTO books(code, title) VALUES
          ('N1', 'Mimikara N1'),
          ('N3', 'Mimikara N3'),
          ('GWB_N2', 'Green Word Book N2');
        INSERT INTO units(book_code, number, header, title) VALUES
          ('N1', 1, 'N1 unit', 'N1 unit'),
          ('N3', 1, 'N3 unit', 'N3 unit'),
          ('GWB_N2', 1, 'GWB unit', 'GWB unit');

        INSERT INTO book_entries(
          entry_id, item_id, uuid, book_code, unit_number, source_index, position,
          sentence, sentence_clip
        ) VALUES
          (101, 1, 'uuid-n1-shared', 'N1', 1, 101, 1,
           'N1で人生を学ぶ。', 'clips/sentences/n1-main.mp3'),
          (102, 1, 'uuid-n3-shared', 'N3', 1, 102, 1,
           'N3で人生を学ぶ。', 'clips/sentences/n3-main.mp3'),
          (103, 1, 'uuid-gwb-shared', 'GWB_N2', 1, 103, 1,
           '別の本で人生を学ぶ。', 'clips/sentences/gwb-main.mp3');

        INSERT INTO item_examples(
          item_id, position, kind, text, translation_en
        ) VALUES
          (1, 3, 'example_sentence', 'N3で人生を学ぶ。', 'Learn about life in N3.'),
          (1, 4, 'example_sentence', '別の本で人生を学ぶ。', 'Learn about life in another book.'),
          (1, 5, 'example_sentence', 'N1で人生を学ぶ。', 'Learn about life in N1.');

        INSERT OR IGNORE INTO item_source_notes(
          item_id, source_book_code, source_entry_uuid, source_index, source_sentence
        ) VALUES
          (1, 'N2', 'uuid-1', 1, '幸せな人生を送る。'),
          (1, 'N1', 'uuid-n1-shared', 101, 'N1で人生を学ぶ。'),
          (1, 'N3', 'uuid-n3-shared', 102, 'N3で人生を学ぶ。'),
          (1, 'GWB_N2', 'uuid-gwb-shared', 103, '別の本で人生を学ぶ。');
        INSERT OR IGNORE INTO item_example_sources(
          item_id, position, source_book_code, source_index
        ) VALUES
          (1, 0, 'N2', 1),
          (1, 3, 'N3', 102),
          (1, 4, 'GWB_N2', 103),
          (1, 5, 'N1', 101);
        "#,
    )
    .unwrap();
    drop(conn);

    let preferred = fixture.repo.get_entry(1).unwrap().expect("entry exists");
    assert_eq!(preferred.sentence, "N1で人生を学ぶ。");
    assert_eq!(preferred.sentence_position, 5);
    assert_versioned_audio_url(
        preferred.sentence_audio_url.as_deref(),
        "clips/sentences/n1-main.mp3",
    );

    let conn = Connection::open(&fixture.db_path).unwrap();
    conn.execute_batch(
        r#"
        DELETE FROM item_examples WHERE item_id = 1 AND position = 5;
        DELETE FROM item_source_notes
          WHERE item_id = 1 AND source_book_code = 'N1' AND source_index = 101;
        DELETE FROM book_entries WHERE entry_id = 101;
        "#,
    )
    .unwrap();
    drop(conn);

    let without_n1 = fixture.repo.get_entry(1).unwrap().expect("entry exists");
    assert_eq!(without_n1.sentence, "幸せな人生を送る。");
    assert_eq!(without_n1.sentence_position, 0);

    let conn = Connection::open(&fixture.db_path).unwrap();
    conn.execute_batch(
        r#"
        UPDATE book_entries SET sentence = NULL, sentence_clip = NULL WHERE entry_id = 1;
        DELETE FROM item_examples WHERE item_id = 1 AND position = 0;
        DELETE FROM item_source_notes
          WHERE item_id = 1 AND source_book_code = 'N2' AND source_index = 1;
        "#,
    )
    .unwrap();
    drop(conn);

    let without_n1_or_n2 = fixture.repo.get_entry(1).unwrap().expect("entry exists");
    assert_eq!(without_n1_or_n2.sentence, "N3で人生を学ぶ。");
    assert_eq!(without_n1_or_n2.sentence_position, 3);
}

#[test]
fn detail_includes_examples_and_audio_urls() {
    let fixture = Fixture::new();

    let entry = fixture.repo.get_entry(1).unwrap().expect("entry exists");
    let examples = entry.examples.as_ref().expect("entry examples");
    assert_eq!(examples.len(), 3);
    assert!(
        entry.word_audio_id.is_some(),
        "word audio should expose its DB ID"
    );
    assert!(
        entry.sentence_audio_id.is_some(),
        "sentence audio should expose its DB ID"
    );
    assert_eq!(examples[0].audio_id, entry.sentence_audio_id);
    assert_versioned_audio_url(entry.word_audio_url.as_deref(), "clips/words/word1.mp3");
    assert_versioned_audio_url(
        entry.sentence_audio_url.as_deref(),
        "clips/sentences/sentence1.mp3",
    );
}

#[test]
fn retired_sentence_star_tables_are_absent() {
    let fixture = Fixture::new();
    let conn = Connection::open(&fixture.db_path).unwrap();

    for table in ["sentence_stars", "item_sentence_stars"] {
        let present: Option<String> = conn
            .query_row(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                [table],
                |row| row.get(0),
            )
            .optional()
            .unwrap();
        assert_eq!(present, None, "retired table {table} should stay absent");
    }
}

#[test]
fn book_entry_audio_overrides_shared_item_audio() {
    let fixture = Fixture::new();
    fs::create_dir_all(fixture.clips_dir.join("book_audio")).unwrap();
    fs::create_dir_all(fixture.clips_dir.join("generated")).unwrap();
    fs::write(
        fixture.clips_dir.join("book_audio").join("word1.mp3"),
        b"human word",
    )
    .unwrap();
    fs::write(
        fixture.clips_dir.join("book_audio").join("sentence1.mp3"),
        b"human sentence",
    )
    .unwrap();
    fs::write(
        fixture.clips_dir.join("generated").join("shared_word1.mp3"),
        b"generated word",
    )
    .unwrap();
    fs::write(
        fixture
            .clips_dir
            .join("generated")
            .join("shared_sentence1.mp3"),
        b"generated sentence",
    )
    .unwrap();
    for clip in [
        "clips/book_audio/word1.mp3",
        "clips/book_audio/sentence1.mp3",
        "clips/generated/shared_word1.mp3",
        "clips/generated/shared_sentence1.mp3",
    ] {
        fixture.repo.record_audio_id(clip).unwrap();
    }

    let conn = Connection::open(&fixture.db_path).unwrap();
    conn.execute(
        "UPDATE vocabulary_items SET word_clip = 'clips/generated/shared_word1.mp3' WHERE item_id = 1",
        [],
    )
    .unwrap();
    conn.execute(
        "UPDATE item_examples SET audio_clip = 'clips/generated/shared_sentence1.mp3' WHERE item_id = 1 AND position = 0",
        [],
    )
    .unwrap();
    conn.execute(
        "UPDATE book_entries SET word_clip = 'clips/book_audio/word1.mp3', sentence_clip = 'clips/book_audio/sentence1.mp3' WHERE book_code = 'N2' AND entry_id = 1",
        [],
    )
    .unwrap();
    drop(conn);

    let listed = fixture.repo.list_entries(Some(1), "all", "人生").unwrap();
    let list_entry = &listed.items[0];
    assert_eq!(
        list_entry.word_audio_url.as_deref(),
        Some("/audio/clips/book_audio/word1.mp3")
    );
    assert_eq!(
        list_entry.sentence_audio_url.as_deref(),
        Some("/audio/clips/book_audio/sentence1.mp3")
    );

    let detail = fixture.repo.get_entry(1).unwrap().expect("entry exists");
    assert_versioned_audio_url(
        detail.word_audio_url.as_deref(),
        "clips/book_audio/word1.mp3",
    );
    assert_versioned_audio_url(
        detail.sentence_audio_url.as_deref(),
        "clips/book_audio/sentence1.mp3",
    );
}

#[test]
fn detail_includes_merged_source_notes_and_example_provenance() {
    let fixture = Fixture::new();
    let conn = Connection::open(&fixture.db_path).unwrap();
    conn.execute(
        "INSERT INTO item_source_notes(item_id,source_book_code,source_entry_uuid,source_index,source_title,source_page,source_cd_track,source_reading,source_meaning_zh,source_explanation_md,source_notes_md,source_sentence) VALUES(1,'GWB_N2','gwb-uuid',42,'Green Word Book',12,'track-42','じんせい','人生；生涯','legacy explanation','source notes','GWB例文。')",
        [],
    ).unwrap();
    conn.execute(
        "INSERT INTO item_example_sources(item_id,position,source_book_code,source_index) VALUES(1,1,'GWB_N2',42)",
        [],
    ).unwrap();
    drop(conn);

    let entry = fixture.repo.get_entry(1).unwrap().expect("entry exists");
    let notes = entry.source_notes.expect("detail source notes");
    assert_eq!(notes[0].source_book_code, "GWB_N2");
    assert_eq!(notes[0].source_index, 42);
    assert_eq!(notes[0].source_title.as_deref(), Some("Green Word Book"));
    assert_eq!(notes[0].source_page, Some(12));
    assert_eq!(notes[0].source_cd_track.as_deref(), Some("track-42"));
    assert_eq!(notes[0].notes_md, "source notes");
    let examples = entry.examples.expect("detail examples");
    assert_eq!(examples[1].source_book_code.as_deref(), Some("GWB_N2"));
    assert_eq!(examples[1].source_index, Some(42));
}

#[test]
fn legacy_source_explanation_is_not_exposed_as_source_note() {
    let fixture = Fixture::new();
    let conn = Connection::open(&fixture.db_path).unwrap();
    conn.execute(
        "INSERT INTO item_source_notes(item_id,source_book_code,source_entry_uuid,source_index,source_reading,source_meaning_zh,source_explanation_md,source_sentence) VALUES(1,'N2','n2-legacy',74,'にっちゅう','白天；日中','learner sentence explanation copied into legacy source field','朝晩は冷え込むが、日中は穏やかな天気が続いている。')",
        [],
    ).unwrap();
    drop(conn);

    let entry = fixture.repo.get_entry(1).unwrap().expect("entry exists");
    assert!(entry.source_notes.unwrap().is_empty());
}

#[test]
fn mark_upsert_delete_and_unknown_entry() {
    let fixture = Fixture::new();

    fixture.repo.set_mark(2, false, true).unwrap();
    let row = fixture.repo.get_entry(2).unwrap().expect("entry exists");
    assert!(row.mark.flagged);

    fixture.repo.set_mark(2, false, false).unwrap();
    let row = fixture.repo.get_entry(2).unwrap().expect("entry exists");
    assert!(!row.mark.known);
    assert!(!row.mark.flagged);

    assert!(fixture.repo.set_mark(999, true, false).is_err());
}
