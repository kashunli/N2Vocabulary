use n2_word_service_rust::repository::{WordRepository, clean_sentence_text_for_tts};
use rusqlite::Connection;
use std::fs;
use std::path::PathBuf;
use tempfile::TempDir;

/// Small integration-test fixture.
///
/// The temp directory owns both SQLite and fake clip files, so each test starts
/// isolated and can freely mutate marks/audio metadata without touching the
/// real study database.
struct Fixture {
    _tempdir: TempDir,
    repo: WordRepository,
    db_path: PathBuf,
    clips_dir: PathBuf,
}

impl Fixture {
    fn new() -> Self {
        let tempdir = TempDir::new().expect("create tempdir");
        let root = tempdir.path();
        let db_path = root.join("n2vocab.sqlite");
        let clips_dir = root.join("clips");
        fs::create_dir_all(clips_dir.join("words")).expect("create word clip folder");
        fs::create_dir_all(clips_dir.join("sentences")).expect("create sentence clip folder");
        fs::create_dir_all(clips_dir.join("unit07")).expect("create legacy clip folder");
        fs::write(clips_dir.join("words").join("word1.mp3"), b"word").unwrap();
        fs::write(
            clips_dir.join("sentences").join("sentence1.mp3"),
            b"sentence",
        )
        .unwrap();
        fs::write(clips_dir.join("unit07").join("word003.mp3"), b"legacy word").unwrap();

        create_test_db(&db_path);

        Self {
            repo: WordRepository::new(db_path.clone(), clips_dir.clone(), "N2"),
            _tempdir: tempdir,
            db_path,
            clips_dir,
        }
    }
}

#[test]
fn summary_and_units_include_mark_counts() {
    let fixture = Fixture::new();

    let summary = fixture.repo.get_summary().unwrap();
    assert_eq!(summary.entries, 2);
    assert_eq!(summary.units, 1);
    assert_eq!(summary.known, 1);
    assert_eq!(summary.flagged, 0);
    assert_eq!(summary.unmarked, 1);

    let unit = fixture.repo.list_units().unwrap().remove(0);
    assert_eq!(unit.entry_count, 2);
    assert_eq!(unit.known, 1);
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
}

#[test]
fn detail_includes_examples_and_audio_urls() {
    let fixture = Fixture::new();

    let entry = fixture.repo.get_entry(1).unwrap().expect("entry exists");
    assert_eq!(entry.examples.unwrap().len(), 2);
    assert_eq!(
        entry.word_audio_url.as_deref(),
        Some("/audio/clips/words/word1.mp3")
    );
    assert_eq!(
        entry.sentence_audio_url.as_deref(),
        Some("/audio/clips/sentences/sentence1.mp3")
    );
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

    assert_eq!(
        fixture
            .repo
            .audio_url(Some("output\\clips\\unit07\\word003.mp3")),
        Some("/audio/clips/unit07/word003.mp3".to_string())
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
}

#[test]
fn entry_omits_missing_audio_urls() {
    let fixture = Fixture::new();
    fs::remove_file(fixture.clips_dir.join("words").join("word1.mp3")).unwrap();

    let entry = fixture.repo.get_entry(1).unwrap().expect("entry exists");
    assert_eq!(entry.word_audio_url, None);
    assert_eq!(
        entry.sentence_audio_url.as_deref(),
        Some("/audio/clips/sentences/sentence1.mp3")
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
    assert_eq!(
        response.audio_url,
        "/audio/clips/generated_sentences/edge_tts/word1_sentence1.mp3"
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
            "SELECT audio_clip FROM entry_examples WHERE entry_id = 1 AND position = 1",
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
fn missing_example_audio_uses_clean_sentence_text_for_tts() {
    let fixture = Fixture::new();
    let conn = Connection::open(&fixture.db_path).unwrap();
    conn.execute(
        "INSERT INTO entry_examples(entry_id, position, text) VALUES(2, 1, ?)",
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
    assert_eq!(response.audio_url, "/audio/clips/sentences/sentence1.mp3");
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
        "INSERT INTO entry_examples(entry_id, position, text) VALUES(2, 1, '')",
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

fn create_test_db(db_path: &PathBuf) {
    let conn = Connection::open(db_path).expect("open test db");
    // Keep the schema close to the production tables used by repository.rs.
    // These tests are most valuable when they exercise real SQL assumptions,
    // not a heavily mocked shape.
    conn.execute_batch(
        r#"
        PRAGMA foreign_keys = ON;

        CREATE TABLE books (
          code TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          notes TEXT
        );
        CREATE TABLE units (
          book_code TEXT NOT NULL REFERENCES books(code),
          number INTEGER NOT NULL,
          header TEXT NOT NULL,
          title TEXT NOT NULL,
          PRIMARY KEY(book_code, number)
        );
        CREATE TABLE entries (
          entry_id INTEGER PRIMARY KEY,
          uuid TEXT NOT NULL UNIQUE,
          book_code TEXT NOT NULL,
          unit_number INTEGER NOT NULL,
          source_index INTEGER NOT NULL,
          position INTEGER NOT NULL,
          kanji TEXT NOT NULL,
          reading TEXT,
          headword_text TEXT NOT NULL,
          verb_pattern TEXT,
          meaning_en TEXT,
          meaning_zh TEXT,
          sentence TEXT,
          explanation_md TEXT,
          word_clip TEXT,
          sentence_clip TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(book_code, source_index),
          FOREIGN KEY(book_code, unit_number) REFERENCES units(book_code, number)
        );
        CREATE TABLE entry_examples (
          entry_id INTEGER NOT NULL REFERENCES entries(entry_id),
          position INTEGER NOT NULL,
          text TEXT NOT NULL,
          translation_en TEXT,
          translation_zh TEXT,
          explanation_md TEXT,
          audio_clip TEXT,
          PRIMARY KEY(entry_id, position)
        );
        CREATE TABLE word_marks (
          entry_id INTEGER PRIMARY KEY REFERENCES entries(entry_id),
          known INTEGER NOT NULL DEFAULT 0 CHECK(known IN (0,1)),
          flagged INTEGER NOT NULL DEFAULT 0 CHECK(flagged IN (0,1)),
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO books(code, title) VALUES('N2', 'N2');
        INSERT INTO units(book_code, number, header, title)
        VALUES('N2', 1, 'Unit 01 名詞 A', '名詞 A');
        INSERT INTO entries(
          entry_id, uuid, book_code, unit_number, source_index, position,
          kanji, reading, headword_text, meaning_en, meaning_zh,
          sentence, explanation_md, word_clip, sentence_clip
        )
        VALUES
          (1, 'uuid-1', 'N2', 1, 1, 1, '人生', 'じんせい', '人生',
           'life', '人生', '幸せな人生を送る。', 'explain one',
           'clips/words/word1.mp3', 'clips/sentences/sentence1.mp3'),
          (2, 'uuid-2', 'N2', 1, 2, 2, '男性', 'だんせい', '男性',
           'man', '男性', '男性の友人。', NULL, NULL, NULL);
        INSERT INTO entry_examples(
          entry_id, position, text, translation_en, translation_zh, explanation_md, audio_clip
        )
        VALUES
          (1, 0, '幸せな人生を送る。', 'Live a happy life.', '度过幸福的人生。',
           'main explanation', 'clips/sentences/sentence1.mp3'),
          (1, 1, '人生経験が豊富だ。', 'Has rich life experience.', '人生经验丰富。', NULL, NULL);
        INSERT INTO word_marks(entry_id, known, flagged)
        VALUES(1, 1, 0);
        "#,
    )
    .expect("create schema");
}
