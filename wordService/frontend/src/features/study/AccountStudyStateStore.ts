import {gradeAccountCard, recordAccountPlayback, updateAccountMarks} from "../../api";
import type {ReviewGrade, StudyCardState, StudySnapshot, StudyStateStore} from "./studyStateTypes";

export class AccountStudyStateStore implements StudyStateStore {
  private listeners = new Set<(snapshot: StudySnapshot) => void>();

  constructor(private csrfToken: string, private snapshot: StudySnapshot) {}

  load() { return this.snapshot; }
  subscribe(listener: (snapshot: StudySnapshot) => void) { this.listeners.add(listener); return () => this.listeners.delete(listener); }
  seedLegacy() { return this.snapshot; }
  private update(card: StudyCardState) {
    this.snapshot = {...this.snapshot, updated_at: card.updated_at, cards: {...this.snapshot.cards, [card.item_uuid]: card}};
    for (const listener of this.listeners) listener(this.snapshot);
    return card;
  }
  async setMark(itemUuid: string, mark: {known: boolean; flagged: boolean}) {
    return this.update((await updateAccountMarks(this.csrfToken, itemUuid, mark)).card);
  }
  async recordPlayed(entry: {item_uuid: string; book_code: string; source_index: number}) {
    return this.update((await recordAccountPlayback(this.csrfToken, entry)).card);
  }
  async grade(itemUuid: string, grade: ReviewGrade) {
    return this.update((await gradeAccountCard(this.csrfToken, itemUuid, grade)).card);
  }
  dueCards(at = new Date()) {
    const timestamp = at.getTime();
    return Object.values(this.snapshot.cards).filter(card => card.due_at && Date.parse(card.due_at) <= timestamp)
      .sort((left, right) => left.due_at!.localeCompare(right.due_at!) || (left.enrolled_at || "").localeCompare(right.enrolled_at || "") || left.item_uuid.localeCompare(right.item_uuid));
  }
  nextDueAt() { return Object.values(this.snapshot.cards).map(card => card.due_at).filter((value): value is string => !!value).sort()[0]; }
}
