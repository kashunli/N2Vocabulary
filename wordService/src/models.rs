use serde::Serialize;
use std::collections::BTreeMap;

/// A book-level source that can be browsed in the same card UI.
#[derive(Debug, Serialize, PartialEq)]
pub struct BookSummary {
    pub code: String,
    pub title: String,
    pub entries: i64,
    pub units: i64,
}

/// Counts shown in the top-level dashboard.
#[derive(Debug, Serialize, PartialEq)]
pub struct Summary {
    pub entries: i64,
    pub units: i64,
    pub known: i64,
    pub flagged: i64,
    pub unmarked: i64,
    /// Stable fingerprint of the immutable content database. The frontend keys
    /// its local content cache on this value and refetches only when it changes.
    pub content_revision: String,
}

/// Per-unit counts used by the unit sidebar/list.
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

/// A compact unit reference embedded inside an entry response.
#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct UnitRef {
    pub number: i64,
    pub header: String,
    pub title: String,
}

/// User study state for one vocabulary entry.
///
/// SQLite stores booleans as integers, but the API returns real JSON booleans
/// because that is easier for the frontend to consume.
#[derive(Debug, Serialize, PartialEq)]
pub struct MarkState {
    pub known: bool,
    pub flagged: bool,
    pub updated_at: Option<String>,
}

/// Full mark snapshot returned by `/api/marks`.
#[derive(Debug, Serialize, PartialEq)]
pub struct MarksResponse {
    pub version: i64,
    pub updated_at: String,
    pub marks: BTreeMap<String, MarkState>,
}

/// One sentence/example attached to an entry.
///
/// `kind` names the content role, while `position` is only display order.
#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct EntryExample {
    pub position: i64,
    pub kind: String,
    pub text: String,
    pub reading: String,
    pub translation_en: String,
    pub translation_zh: String,
    pub explanation_md: String,
    pub audio_url: Option<String>,
    pub source_book_code: Option<String>,
    pub source_index: Option<i64>,
    pub category: Option<String>,

    // Internal selection metadata. A merged example can be the originating
    // sentence of a source book even when its shared item position is not 0.
    #[serde(skip)]
    pub main_source_book_code: Option<String>,
}

/// Provenance and source-specific notes retained from a merged source-book
/// occurrence. These fields are deliberately separate from sentence
/// explanations: a page/CD reference describes where the material came from,
/// not how to understand the sentence.
#[derive(Clone, Debug, Serialize, PartialEq)]
pub struct EntrySourceNote {
    pub source_book_code: String,
    pub source_index: i64,
    pub source_title: Option<String>,
    pub source_page: Option<i64>,
    pub source_cd_track: Option<String>,
    pub reading: String,
    pub meaning_en: String,
    pub meaning_zh: String,
    pub notes_md: String,
}

/// The main entry payload served to the browser.
///
/// List views and detail views share this shape. Detail-only fields are
/// optional so the list endpoint can stay lightweight without inventing a
/// second nearly-identical struct.
#[derive(Debug, Serialize, PartialEq)]
pub struct EntryPayload {
    pub entry_id: i64,
    pub source_index: i64,
    pub uuid: String,
    /// Stable identity of the shared vocabulary item across book appearances.
    pub item_uuid: String,
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
    pub sentence_position: i64,
    pub word_audio_url: Option<String>,
    pub sentence_audio_url: Option<String>,
    pub mark: MarkState,

    // Serde skips absent detail fields entirely, so the frontend can distinguish
    // "not loaded in this endpoint" from "loaded but empty".
    #[serde(skip_serializing_if = "Option::is_none")]
    pub examples: Option<Vec<EntryExample>>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_notes: Option<Vec<EntrySourceNote>>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub search_matches: Option<Vec<EntryExample>>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub explanation_md: Option<String>,
}

/// Pageless list response. `total` is still useful to the frontend even though
/// this local service currently returns all matching entries.
#[derive(Debug, Serialize, PartialEq)]
pub struct EntryListResponse {
    pub items: Vec<EntryPayload>,
    pub total: usize,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct LegacyMarkSeed {
    pub item_uuid: String,
    pub known: bool,
    pub flagged: bool,
}

#[derive(Debug, Serialize, PartialEq)]
pub struct LegacyMarkSeedResponse {
    pub items: Vec<LegacyMarkSeed>,
}

/// Response for lazy sentence-audio generation.
///
/// `generated` tells the UI whether the backend reused an existing clip or made
/// a new one during this request.
#[derive(Debug, Serialize, PartialEq)]
pub struct AudioGenerationResponse {
    pub ok: bool,
    pub audio_url: String,
    pub generated: bool,
}

/// Response for the per-unit flagged-word listening export.
///
/// The backend writes one MP3 per unit and returns it through the same `/audio`
/// route as normal clips so the browser can download it directly.
#[derive(Debug, Serialize, PartialEq)]
pub struct FlaggedAudioExportResponse {
    pub ok: bool,
    pub unit: i64,
    pub word_count: usize,
    pub audio_url: String,
    pub file_name: String,
}
