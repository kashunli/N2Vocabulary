import type { MarkStatus } from "./markStatus";

export interface StudyCardState {
  item_uuid: string;
  status: MarkStatus;
  mark_updated_at?: string;
  enrolled_at?: string;
  due_at?: string;
  review_level: number;
  last_reviewed_at?: string;
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

export type ImportedMark = {
  item_uuid: string;
  status: Exclude<MarkStatus, "unmarked">;
};

export function isReviewDue(dueAt?: string, now = Date.now()) {
  if (!dueAt) return false;
  const timestamp = Date.parse(dueAt);
  return Number.isFinite(timestamp) && timestamp <= now;
}

export interface StudyStateStore {
  load(): StudySnapshot;
  subscribe(listener: (snapshot: StudySnapshot) => void): () => void;
  seedLegacy(items: Array<{item_uuid: string; known: boolean; flagged: boolean}>): StudySnapshot;
  setMark(itemUuid: string, status: MarkStatus): Promise<StudyCardState>;
  importMarks(items: ImportedMark[]): Promise<StudySnapshot>;
  recordStudyCompleted(entry: {item_uuid: string; book_code: string; source_index: number}): Promise<StudyCardState>;
  completeReview(entry: {item_uuid: string; book_code: string; source_index: number}, expectedDueAt: string): Promise<ReviewCompletionResult>;
}

export interface ReviewCompletionResult {
  completed: boolean;
  card?: StudyCardState;
}

export interface ReviewSession {
  scopeKey: string;
  expectedDueAtByItemUuid: Record<string, string>;
  completedByItemUuid: Record<string, {reviewLevel: number; nextDueAt: string}>;
}
