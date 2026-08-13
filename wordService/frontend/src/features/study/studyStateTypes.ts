export interface StudyCardState {
  item_uuid: string;
  known: boolean;
  flagged: boolean;
  enrolled_at?: string;
  due_at?: string;
  last_played_at?: string;
  preferred_book_code?: string;
  preferred_source_index?: number;
  updated_at: string;
}

export interface StudySnapshot {
  version: number;
  updated_at: string;
  cards: Record<string, StudyCardState>;
}

export interface StudyStateStore {
  load(): StudySnapshot;
  subscribe(listener: (snapshot: StudySnapshot) => void): () => void;
  seedLegacy(items: Array<{item_uuid: string; known: boolean; flagged: boolean}>): StudySnapshot;
  setMark(itemUuid: string, mark: {known: boolean; flagged: boolean}): Promise<StudyCardState>;
  recordPlayed(entry: {item_uuid: string; book_code: string; source_index: number}): Promise<StudyCardState>;
  dueCards(at?: Date): StudyCardState[];
}
