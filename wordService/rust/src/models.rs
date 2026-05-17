use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Debug, Serialize, PartialEq)]
pub struct Summary {
    pub entries: i64,
    pub units: i64,
    pub known: i64,
    pub flagged: i64,
    pub unmarked: i64,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct UnitSummary {
    pub number: i64,
    pub header: String,
    pub title: String,
    pub entry_count: i64,
    pub known: i64,
    pub flagged: i64,
    pub unmarked: i64,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct UnitRef {
    pub number: i64,
    pub header: String,
    pub title: String,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct MarkState {
    pub known: bool,
    pub flagged: bool,
    pub updated_at: Option<String>,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct MarksResponse {
    pub version: i64,
    pub updated_at: String,
    pub marks: BTreeMap<String, MarkState>,
}

#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct EntryExample {
    pub position: i64,
    pub text: String,
    pub translation_en: String,
    pub translation_zh: String,
    pub explanation_md: String,
    pub audio_url: Option<String>,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct EntryPayload {
    pub entry_id: i64,
    pub source_index: i64,
    pub uuid: String,
    pub book_code: String,
    pub unit: UnitRef,
    pub kanji: String,
    pub reading: String,
    pub verb_pattern: String,
    pub meaning_en: String,
    pub meaning_zh: String,
    pub sentence: String,
    pub sentence_translation_en: String,
    pub sentence_translation_zh: String,
    pub word_audio_url: Option<String>,
    pub sentence_audio_url: Option<String>,
    pub mark: MarkState,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub examples: Option<Vec<EntryExample>>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub explanation_md: Option<String>,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct EntryListResponse {
    pub items: Vec<EntryPayload>,
    pub total: usize,
}
