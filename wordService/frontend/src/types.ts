import type { MarkStatus } from "./features/study/markStatus";

export interface UnitRef {
  number: number;
  header: string;
  title: string;
}

export interface Entry {
  entry_id: number;
  item_uuid: string;
  source_index: number;
  book_code: string;
  unit: UnitRef;
  kanji: string;
  reading: string;
  meaning_en: string;
  meaning_zh: string;
  sentence: string;
  sentence_translation_en: string;
  sentence_translation_zh: string;
  word_audio_url?: string;
  sentence_audio_url?: string;
  explanation_md?: string;
  mark?: Mark;
  examples?: Example[];
  source_notes?: SourceNote[];
}

export interface UnitSummary {
  number: number;
  header: string;
  title: string;
  entry_count: number;
  known?: number;
  flagged?: number;
  review?: number;
  unmarked?: number;
}

export interface BookSummary {
  code: string;
  entries: number;
  title: string;
  units: number;
}

export interface VocabularySummary {
  entries: number;
  units: number;
  known: number;
  flagged: number;
  review?: number;
  unmarked: number;
}

export interface Mark {
  // The API may still return legacy content marks while the vocabulary DB is
  // being retired. Active study state uses status as the canonical field.
  status?: MarkStatus;
  known?: boolean;
  flagged?: boolean;
  due_at?: string;
  review_level?: number;
  last_reviewed_at?: string;
  updated_at?: string;
}

export interface Example {
  position: number;
  kind: string;
  text: string;
  reading?: string;
  translation_en?: string;
  translation_zh?: string;
  explanation_md?: string;
  audio_url?: string;
}

export interface SourceNote {
  source_book_code: string;
  source_index: number;
  source_title?: string;
  source_page?: number;
  source_cd_track?: string;
  reading?: string;
  meaning_en?: string;
  meaning_zh?: string;
  notes_md?: string;
}

export interface AudioTarget {
  entry: Entry;
  phase: "word" | "sentence";
  url: string;
  /** Distinguishes repeated recipe occurrences that use the same audio URL. */
  sequenceOccurrenceId?: string;
}
