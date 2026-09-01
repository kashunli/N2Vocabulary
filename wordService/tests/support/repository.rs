use n2_word_service_rust::repository::WordRepository;
use rusqlite::Connection;
use std::fs;
use std::path::PathBuf;
use tempfile::TempDir;

/// Small integration-test fixture.
///
/// The temp directory owns both SQLite and fake clip files, so each test starts
/// isolated and can freely mutate marks/audio metadata without touching the
/// real study database.
pub struct Fixture {
    _tempdir: TempDir,
    pub repo: WordRepository,
    pub db_path: PathBuf,
    pub clips_dir: PathBuf,
}

pub fn assert_versioned_audio_url(actual: Option<&str>, path: &str) {
    let actual = actual.expect("audio URL should be present");
    let (base, version) = actual
        .split_once("?v=")
        .expect("audio URL should carry a version query parameter");
    assert_eq!(base, format!("/audio/{path}"));
    assert!(!version.is_empty(), "audio URL must carry a database ID");
    assert!(version.bytes().all(|byte| byte.is_ascii_digit()));
}

impl Fixture {
    pub fn new() -> Self {
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

        let fixture = Self {
            repo: WordRepository::new(db_path.clone(), clips_dir.clone(), "N2"),
            _tempdir: tempdir,
            db_path,
            clips_dir,
        };
        fixture
            .repo
            .record_audio_id("clips/words/word1.mp3")
            .expect("record test word audio ID");
        fixture
            .repo
            .record_audio_id("clips/sentences/sentence1.mp3")
            .expect("record test sentence audio ID");
        fixture
            .repo
            .record_audio_id("clips/unit07/word003.mp3")
            .expect("record legacy test audio ID");
        fixture
    }
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
          kind TEXT NOT NULL DEFAULT 'example_sentence',
          text TEXT NOT NULL,
          reading TEXT,
          translation_en TEXT,
          translation_zh TEXT,
          explanation_md TEXT,
          audio_clip TEXT,
          category TEXT,
          PRIMARY KEY(entry_id, position)
        );
        -- Legacy table required only while migration 007 is exercised below.
        -- Migration 010 removes it before the repository is used.
        CREATE TABLE sentence_stars (
          entry_id INTEGER NOT NULL,
          position INTEGER NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(entry_id, position),
          FOREIGN KEY(entry_id, position)
            REFERENCES entry_examples(entry_id, position)
            ON DELETE CASCADE
        );
        CREATE TABLE entry_source_notes (
          entry_id INTEGER NOT NULL REFERENCES entries(entry_id) ON DELETE CASCADE,
          source_book_code TEXT NOT NULL,
          source_entry_uuid TEXT NOT NULL,
          source_index INTEGER NOT NULL,
          source_reading TEXT,
          source_meaning_en TEXT,
          source_meaning_zh TEXT,
          source_explanation_md TEXT,
          source_sentence TEXT,
          source_translation_en TEXT,
          source_translation_zh TEXT,
          source_word_clip TEXT,
          source_sentence_clip TEXT,
          PRIMARY KEY(entry_id,source_book_code,source_index)
        );
        CREATE TABLE entry_example_sources (
          entry_id INTEGER NOT NULL,
          position INTEGER NOT NULL,
          source_book_code TEXT NOT NULL,
          source_index INTEGER NOT NULL,
          PRIMARY KEY(entry_id,position,source_book_code,source_index),
          FOREIGN KEY(entry_id,position) REFERENCES entry_examples(entry_id,position) ON DELETE CASCADE,
          FOREIGN KEY(entry_id,source_book_code,source_index)
            REFERENCES entry_source_notes(entry_id,source_book_code,source_index) ON DELETE CASCADE
        );
        CREATE TABLE word_marks (
          entry_id INTEGER PRIMARY KEY REFERENCES entries(entry_id),
          known INTEGER NOT NULL DEFAULT 0 CHECK(known IN (0,1)),
          flagged INTEGER NOT NULL DEFAULT 0 CHECK(flagged IN (0,1)),
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO books(code, title) VALUES('N2', 'N2');
        INSERT INTO units(book_code, number, header, title)
        VALUES
          ('N2', 1, 'Unit 01 名詞 A', '名詞 A'),
          ('N2', 2, 'Unit 02 動詞 A', '動詞 A');
        INSERT INTO entries(
          entry_id, uuid, book_code, unit_number, source_index, position,
          kanji, reading, meaning_en, meaning_zh,
          sentence, explanation_md, word_clip, sentence_clip
        )
        VALUES
          (1, 'uuid-1', 'N2', 1, 1, 1, '人生', 'じんせい',
           'life', '人生', '幸せな人生を送る。', 'explain one',
           'clips/words/word1.mp3', 'clips/sentences/sentence1.mp3'),
          (2, 'uuid-2', 'N2', 1, 2, 2, '男性', 'だんせい',
           'man', '男性', '男性の友人。', NULL, NULL, NULL),
          (3, 'uuid-3', 'N2', 2, 3, 1, '覆う', 'おおう',
           'cover', '覆盖', '山頂は雪で覆われていた。', NULL, NULL, NULL),
          (4, 'uuid-4', 'N2', 2, 4, 2, 'カバー', 'カバー',
           'cover', '罩子', 'ソファーをカバーで覆う。', NULL, NULL, NULL);
        INSERT INTO entry_examples(
          entry_id, position, kind, text, translation_en, translation_zh, explanation_md, audio_clip
        )
        VALUES
          (1, 0, 'main_sentence', '幸せな人生を送る。', 'Live a happy life.', '度过幸福的人生。',
           'main explanation', 'clips/sentences/sentence1.mp3'),
          (1, 1, 'example_sentence', '人生経験が豊富だ。', 'Has rich life experience.', '人生经验丰富。', NULL, NULL),
          (1, 2, 'example_sentence', '不安が人生を覆う。', 'Anxiety covers life.', '不安笼罩人生。', NULL, NULL),
          (3, 0, 'main_sentence', '山頂は雪で覆われていた。', 'The summit was covered with snow.', '山顶被雪覆盖。', NULL, NULL),
          (4, 0, 'main_sentence', 'ソファーをカバーで覆う。', 'Cover the sofa with a cover.', '用罩子盖住沙发。', NULL, NULL);
        INSERT INTO word_marks(entry_id, known, flagged)
        VALUES(1, 1, 0);
        "#,
    )
    .expect("create schema");
    conn.execute_batch(include_str!(
        "../../../db/migrations/007_vocabulary_items.sql"
    ))
    .expect("create canonical item schema");
    conn.execute_batch(include_str!(
        "../../../db/migrations/008_book_entry_word_clip.sql"
    ))
    .expect("create book-specific word audio schema");
    conn.execute_batch(include_str!(
        "../../../db/migrations/009_n1_source_metadata.sql"
    ))
    .expect("create structured source metadata schema");
    conn.execute_batch(include_str!(
        "../../../db/migrations/010_remove_sentence_stars.sql"
    ))
    .expect("remove retired sentence-star schema");
    conn.execute_batch(include_str!(
        "../../../db/migrations/011_audio_versions.sql"
    ))
    .expect("create legacy audio version schema");
    conn.execute_batch(include_str!("../../../db/migrations/012_audio_ids.sql"))
        .expect("create audio ID schema");
}
