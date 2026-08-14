import {completeAccountReview, recordAccountPlayback, updateAccountMarks} from "../../api";
import type {MarkStatus} from "./markStatus";
import type {StudyCardState, StudySnapshot, StudyStateStore} from "./studyStateTypes";

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
  async setMark(itemUuid: string, status: MarkStatus) {
    return this.update((await updateAccountMarks(this.csrfToken, itemUuid, status)).card);
  }
  async recordStudyCompleted(entry: {item_uuid: string; book_code: string; source_index: number}) {
    return this.update((await recordAccountPlayback(this.csrfToken, entry)).card);
  }
  async completeReview(entry: {item_uuid: string; book_code: string; source_index: number}, expectedDueAt: string) {
    const result = await completeAccountReview(this.csrfToken, entry, expectedDueAt);
    if (result.card) this.update(result.card);
    return result;
  }
}
