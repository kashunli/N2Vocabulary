use n2_word_service_rust::repository::{WordRepository, clean_sentence_text_for_tts};
use rusqlite::Connection;
use std::fs;

#[path = "support/repository.rs"]
mod support;
use support::{Fixture, assert_versioned_audio_url};

#[test]
fn audio_resolution_stays_inside_clips() {
    let fixture = Fixture::new();

    let valid = fixture.repo.resolve_audio_path("clips/words/word1.mp3");
    assert!(valid.is_some());
    assert!(
        fixture
            .repo
            .resolve_audio_path("../output/n2vocab.sqlite")
            .is_none()
    );
    assert!(
        fixture
            .repo
            .resolve_audio_path("output/clips/unit1_track02/word001.mp3")
            .is_none()
    );
    assert!(
        fixture
            .repo
            .resolve_audio_path("clips/../output/n2vocab.sqlite")
            .is_none()
    );
}

#[test]
fn audio_urls_require_existing_files_and_normalize_legacy_db_prefixes() {
    let fixture = Fixture::new();

    assert_versioned_audio_url(
        fixture
            .repo
            .audio_url(Some("output\\clips\\unit07\\word003.mp3"))
            .as_deref(),
        "clips/unit07/word003.mp3",
    );
    assert_eq!(
        fixture
            .repo
            .audio_url(Some("output\\clips\\unit07\\word999.mp3")),
        None
    );
    assert_eq!(
        fixture.repo.audio_url(Some("clips/words/missing.mp3")),
        None
    );

    let before = fixture.repo.audio_url(Some("clips/unit07/word003.mp3"));
    fs::write(
        fixture.clips_dir.join("unit07").join("word003.mp3"),
        b"replaced legacy word",
    )
    .unwrap();
    let reloaded = WordRepository::new(fixture.db_path.clone(), fixture.clips_dir.clone(), "N2");
    let after = reloaded.audio_url(Some("clips/unit07/word003.mp3"));
    assert_ne!(before, after, "changed bytes must receive a new cache key");
}

#[test]
fn entry_omits_missing_audio_urls() {
    let fixture = Fixture::new();
    fs::remove_file(fixture.clips_dir.join("words").join("word1.mp3")).unwrap();

    let entry = fixture.repo.get_entry(1).unwrap().expect("entry exists");
    assert_eq!(entry.word_audio_url, None);
    assert_versioned_audio_url(
        entry.sentence_audio_url.as_deref(),
        "clips/sentences/sentence1.mp3",
    );
}

#[test]
fn missing_example_audio_is_generated_and_stored() {
    let fixture = Fixture::new();

    // The repository accepts a synthesis closure. In production that closure
    // calls Edge TTS; in tests it returns fixed bytes so we can verify file and
    // database behavior without network access.
    let response = fixture
        .repo
        .ensure_example_audio(1, 1, "clips/generated_sentences/edge_tts", |sentence| {
            assert_eq!(sentence, "人生経験が豊富だ。");
            Ok(b"generated sentence audio".to_vec())
        })
        .unwrap();

    assert!(response.generated);
    assert_versioned_audio_url(
        Some(response.audio_url.as_str()),
        "clips/generated_sentences/edge_tts/word1_sentence1.mp3",
    );
    assert_eq!(
        fs::read(
            fixture
                .clips_dir
                .join("generated_sentences")
                .join("edge_tts")
                .join("word1_sentence1.mp3")
        )
        .unwrap(),
        b"generated sentence audio"
    );

    let conn = Connection::open(&fixture.db_path).unwrap();
    let stored: String = conn
        .query_row(
            "SELECT audio_clip FROM item_examples WHERE item_id = 1 AND position = 1",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(
        stored,
        "clips/generated_sentences/edge_tts/word1_sentence1.mp3"
    );
}

#[test]
fn missing_word_audio_is_generated_and_stored() {
    let fixture = Fixture::new();
    fs::remove_file(fixture.clips_dir.join("words").join("word1.mp3")).unwrap();

    let response = fixture
        .repo
        .ensure_word_audio(1, "clips/generated_sentences/edge_tts", |word| {
            assert_eq!(word, "人生");
            Ok(b"generated word audio".to_vec())
        })
        .unwrap();

    assert!(response.generated);
    assert_versioned_audio_url(
        Some(response.audio_url.as_str()),
        "clips/generated_sentences/edge_tts/word1.mp3",
    );
    assert_eq!(
        fs::read(
            fixture
                .clips_dir
                .join("generated_sentences")
                .join("edge_tts")
                .join("word1.mp3")
        )
        .unwrap(),
        b"generated word audio"
    );

    let conn = Connection::open(&fixture.db_path).unwrap();
    let stored: String = conn
        .query_row(
            "SELECT word_clip FROM book_entries WHERE book_code = 'N2' AND entry_id = 1",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert_eq!(stored, "clips/generated_sentences/edge_tts/word1.mp3");
}

#[test]
fn existing_word_audio_is_reused_without_tts() {
    let fixture = Fixture::new();

    let response = fixture
        .repo
        .ensure_word_audio(1, "clips/generated_sentences/edge_tts", |_word| {
            panic!("existing word audio should not synthesize")
        })
        .unwrap();

    assert!(!response.generated);
    assert_versioned_audio_url(Some(response.audio_url.as_str()), "clips/words/word1.mp3");
}

#[test]
fn missing_example_audio_uses_clean_sentence_text_for_tts() {
    let fixture = Fixture::new();
    let conn = Connection::open(&fixture.db_path).unwrap();
    conn.execute(
        "INSERT INTO item_examples(item_id, position, kind, text) VALUES(2, 1, 'example_sentence', ?)",
        ["今期は相当｛な／の｝赤字になりそうだ。"],
    )
    .unwrap();
    drop(conn);

    fixture
        .repo
        .ensure_example_audio(2, 1, "clips/generated_sentences/edge_tts", |sentence| {
            assert_eq!(sentence, "今期は相当な赤字になりそうだ。");
            Ok(b"generated sentence audio".to_vec())
        })
        .unwrap();
}

#[test]
fn sentence_cleaner_removes_textbook_markers() {
    assert_eq!(
        clean_sentence_text_for_tts("②・彼は神経(しんけい)が鋭くて、すぐに気づく。"),
        "彼は神経が鋭くて、すぐに気づく。"
    );
    assert_eq!(
        clean_sentence_text_for_tts("｛砂／ほこり …｝が舞い上がる。"),
        "砂が舞い上がる。"
    );
    assert_eq!(
        clean_sentence_text_for_tts("時計／注射／ホチキス …… の針"),
        "時計の針"
    );
    assert_eq!(
        clean_sentence_text_for_tts("（友(とも)だちに）「あ、おいしそうなケーキ」"),
        "「あ、おいしそうなケーキ」"
    );
}

#[test]
fn existing_example_audio_is_reused_without_tts() {
    let fixture = Fixture::new();

    let response = fixture
        .repo
        .ensure_example_audio(1, 0, "clips/generated_sentences/edge_tts", |_sentence| {
            panic!("existing audio should not synthesize")
        })
        .unwrap();

    assert!(!response.generated);
    assert_versioned_audio_url(
        Some(response.audio_url.as_str()),
        "clips/sentences/sentence1.mp3",
    );
}

#[test]
fn example_audio_rejects_unknown_and_empty_examples() {
    let fixture = Fixture::new();

    assert!(
        fixture
            .repo
            .ensure_example_audio(999, 0, "clips/generated_sentences/edge_tts", |_| Ok(vec![
                1
            ]))
            .unwrap_err()
            .to_string()
            .contains("unknown example")
    );

    let conn = Connection::open(&fixture.db_path).unwrap();
    conn.execute(
        "INSERT INTO item_examples(item_id, position, kind, text) VALUES(2, 1, 'example_sentence', '')",
        [],
    )
    .unwrap();
    drop(conn);

    assert!(
        fixture
            .repo
            .ensure_example_audio(2, 1, "clips/generated_sentences/edge_tts", |_| Ok(vec![1]))
            .unwrap_err()
            .to_string()
            .contains("empty sentence")
    );
}

#[test]
fn generated_audio_directory_stays_inside_clips() {
    let fixture = Fixture::new();

    let error = fixture
        .repo
        .ensure_example_audio(1, 1, "../output", |_| Ok(vec![1]))
        .unwrap_err();
    assert!(
        error
            .to_string()
            .contains("generated audio directory must stay inside clips")
    );
}

#[test]
fn flagged_audio_export_rejects_empty_unit() {
    let fixture = Fixture::new();

    let error = fixture.repo.export_unit_flagged_audio(1).unwrap_err();
    assert!(error.to_string().contains("no flagged words in this unit"));
}

#[test]
fn flagged_audio_export_reports_missing_clips_before_ffmpeg() {
    let fixture = Fixture::new();
    fixture.repo.set_mark(2, false, true).unwrap();

    let error = fixture.repo.export_unit_flagged_audio(1).unwrap_err();
    let message = error.to_string();
    assert!(message.contains("missing audio clips"));
    assert!(message.contains("word #2 word audio"));
    assert!(message.contains("word #2 sentence audio"));
}
