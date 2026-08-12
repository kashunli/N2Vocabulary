import { MarkdownContent } from "./MarkdownContent";
import type { SourceNote } from "../../types";

interface SourceMetadataProps {
  notes?: SourceNote[];
}

function sourceLabel(note: SourceNote): string {
  const parts = [note.source_title || note.source_book_code];
  if (note.source_page !== undefined) parts.push(`page ${note.source_page}`);
  if (note.source_cd_track) parts.push(`CD ${note.source_cd_track}`);
  return parts.join(", ");
}

/** Show provenance as provenance, never as a sentence explanation. */
export function SourceMetadata({notes = []}: SourceMetadataProps) {
  const visibleNotes = notes.filter((note) => note.source_title || note.source_page !== undefined || note.source_cd_track || note.notes_md);
  if (!visibleNotes.length) return null;

  return (
    <section className="react-source-metadata" aria-label="Source information">
      <h3>Source</h3>
      {visibleNotes.map((note) => (
        <article className="react-source-reference" key={`${note.source_book_code}:${note.source_index}`}>
          <p><strong>{sourceLabel(note)}</strong> <span>({note.source_book_code} #{note.source_index})</span></p>
          {note.notes_md ? <div className="react-source-notes"><span>Source notes</span><MarkdownContent value={note.notes_md} /></div> : null}
        </article>
      ))}
    </section>
  );
}
