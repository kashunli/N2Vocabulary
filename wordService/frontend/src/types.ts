export interface UnitRef {
  number: number;
  header: string;
  title: string;
}

export interface Entry {
  entry_id: number;
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
}

export interface UnitSummary {
  number: number;
  header: string;
  title: string;
  entry_count: number;
}

export interface AudioTarget {
  entry: Entry;
  phase: "word" | "sentence";
  url: string;
}
