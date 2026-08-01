use n2_word_service_rust::audio_review::{AudioReviewStore, AudioReviewUpdate};
use serde_json::json;
use std::fs;

#[test]
fn review_store_seeds_updates_clears_and_does_not_reseed() {
    let temp = tempfile::tempdir().unwrap();
    let db_path = temp.path().join("audio_reviews.sqlite");
    let evidence_path = temp.path().join("candidates.json");
    let seed_path = temp.path().join("seed.json");

    fs::write(
        &evidence_path,
        serde_json::to_vec_pretty(&json!({
            "version": 1,
            "source_sha256": "signed-source",
            "items": [
                {
                    "source_index": 233,
                    "unit": 3,
                    "headword": "仕方(が)ない",
                    "classification": "source_supports_db",
                    "audit_score": 0.91,
                    "asr_vs_raw": 0.95,
                    "db_vs_raw": 1.0,
                    "evidence_margin": -0.05,
                    "expected": "借金を返すには、休日も働くよりほかにしかたない。",
                    "transcript": "仕方がない。借金を返すには休日も働くよりほかに仕方ない。",
                    "raw_line": "借金を返すには、休日も働くよりほかにしかたない。",
                    "raw_page": "page.json",
                    "audio_clip": "clips/sentences/sentence233.mp3"
                },
                {
                    "source_index": 1118,
                    "unit": 13,
                    "headword": "続々（と）",
                    "classification": "source_confirmed",
                    "audit_score": 0.96,
                    "asr_vs_raw": 1.0,
                    "db_vs_raw": 0.8,
                    "evidence_margin": 0.2,
                    "expected": "客が続々と訪めかけた。",
                    "transcript": "客が続々と詰めかけた。",
                    "raw_line": "客が続々と詰めかけた。",
                    "raw_page": "page.json",
                    "audio_clip": "clips/sentences/sentence1118.mp3"
                }
            ]
        }))
        .unwrap(),
    )
    .unwrap();
    fs::write(
        &seed_path,
        serde_json::to_vec_pretty(&json!({
            "source_sha256": "signed-source",
            "decisions": [{
                "source_index": 233,
                "decision": "audio_problem",
                "original_text": "借金を返すには、休日も働くよりほかにしかたない。",
                "replacement_text": "借金を返すには、休日も働くよりほかにしかたない。",
                "note": "word audio is included",
                "updated_at": "2026-07-26T00:00:00Z"
            }]
        }))
        .unwrap(),
    )
    .unwrap();

    let store = AudioReviewStore::load(&db_path, &evidence_path, &seed_path).unwrap();
    let initial = store.list().unwrap();
    assert_eq!(initial.total, 2);
    assert_eq!(initial.reviewed, 1);
    assert_eq!(initial.pending, 1);
    assert_eq!(
        initial.items[0].decision.as_ref().unwrap().decision,
        "audio_problem"
    );
    assert!(!initial.items[0].has_text_replacement);
    assert_eq!(
        initial.items[1].audio_url,
        "/audio/clips/sentences/sentence1118.mp3"
    );

    let saved = store
        .set_decision(
            1118,
            AudioReviewUpdate {
                decision: "custom".to_string(),
                replacement_text: "客が続々と詰めかけた。".to_string(),
                note: "human edit".to_string(),
            },
        )
        .unwrap();
    assert_eq!(saved.decision, "custom");
    assert_eq!(store.list().unwrap().reviewed, 2);

    assert!(store.clear_decision(233).unwrap());
    drop(store);

    let reopened = AudioReviewStore::load(&db_path, &evidence_path, &seed_path).unwrap();
    let after_reopen = reopened.list().unwrap();
    assert_eq!(after_reopen.reviewed, 1);
    assert!(
        after_reopen
            .items
            .iter()
            .find(|item| item.candidate.source_index == 233)
            .unwrap()
            .decision
            .is_none()
    );

    let error = reopened
        .set_decision(
            233,
            AudioReviewUpdate {
                decision: "replace".to_string(),
                replacement_text: "借金を返すには休日も働くよりほかにしかたない".to_string(),
                note: String::new(),
            },
        )
        .unwrap_err();
    assert!(error.to_string().contains("equivalent to the original"));

    let custom_error = reopened
        .set_decision(
            233,
            AudioReviewUpdate {
                decision: "custom".to_string(),
                replacement_text: "借金を返すには休日も働くよりほかにしかたない".to_string(),
                note: String::new(),
            },
        )
        .unwrap_err();
    assert!(
        custom_error
            .to_string()
            .contains("equivalent to the original")
    );
}
