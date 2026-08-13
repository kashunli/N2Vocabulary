import {recordAccountPlayback, updateAccountMarks} from "../../api";
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
  async setMark(itemUuid: string, mark: {known: boolean; flagged: boolean}) {
    return this.update((await updateAccountMarks(this.csrfToken, itemUuid, mark)).card);
  }
  async recordPlayed(entry: {item_uuid: string; book_code: string; source_index: number}) {
    return this.update((await recordAccountPlayback(this.csrfToken, entry)).card);
  }
}
