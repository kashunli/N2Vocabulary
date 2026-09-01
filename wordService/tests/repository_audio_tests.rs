use n2_word_service_rust::repository::{WordRepository, clean_sentence_text_for_tts};
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

    assert_eq!(
        fixture
            .repo
            .audio_path_url(Some("output\\clips\\unit07\\word003.mp3"))
            .as_deref(),
        Some("/audio/clips/unit07/word003.mp3")
    );
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
    assert_eq!(
        fixture.repo.audio_path_url(Some("clips/words/missing.mp3")),
        None
    );

    let before = fixture.repo.audio_url(Some("clips/unit07/word003.mp3"));
    let before_id = fixture
        .repo
        .audio_id("clips/unit07/word003.mp3")
        .expect("audio ID should be present");
    fs::write(
        fixture.clips_dir.join("unit07").join("word003.mp3"),
        b"replaced legacy word",
    )
    .unwrap();
    let stale = fixture.repo.audio_url(Some("clips/unit07/word003.mp3"));
    assert_eq!(
        stale, None,
        "runtime must reject a clip whose DB metadata is stale"
    );
    fixture
        .repo
        .record_audio_id("clips/unit07/word003.mp3")
        .unwrap();
    let reloaded = WordRepository::new(fixture.db_path.clone(), fixture.clips_dir.clone(), "N2");
    let after = reloaded.audio_url(Some("clips/unit07/word003.mp3"));
    assert_ne!(before, after, "changed bytes must receive a new cache key");
    let after_id = reloaded
        .audio_id("clips/unit07/word003.mp3")
        .expect("updated audio ID should be present");
    assert_ne!(
        before_id.to_string(),
        after_id,
        "updated clips must get a new ID"
    );
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
