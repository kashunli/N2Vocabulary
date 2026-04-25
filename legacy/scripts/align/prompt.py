"""LLM prompt builder for the alignment step.

Design notes:
- Piece transcripts are the primary evidence, listed inline. The full-track
  Whisper segments and silence boundaries are sidecar file references — the
  LLM is told to use them only when a piece transcript is too garbled.
- Exact-window mode is the legacy workflow: one track, one exact index range.
- Unit-sequential mode is the new workflow: the track starts at a known index,
  GPT maps a contiguous prefix from a larger candidate file, and the last JSON
  item's index becomes the discovered track boundary.
- The output format requests piece_ids lists (not just timestamps) so we can
  validate full piece coverage server-side after the LLM responds.
- bridge_split is the escape hatch for when two adjacent entries share a
  single speech piece with no silence gap.
"""
from __future__ import annotations

from pathlib import Path


def _add_piece_block(lines: list[str], piece_transcripts: list[dict]) -> None:
    lines.append(
        "## Piece transcriptions (primary evidence; each line is one ffmpeg non-silence piece)"
    )
    for piece in piece_transcripts:
        piece_text = piece["text"] or "<empty>"
        lines.append(
            f"  Piece {piece['piece_id']}: {piece['start']:.3f}-{piece['end']:.3f} "
            f"({piece['duration']:.3f}s) | {piece_text}"
        )
    lines.append("")


def _add_sidecars(
    lines: list[str],
    full_track_segments_ref: str | None,
    silence_boundaries_ref: str | None,
    duration: float,
) -> None:
    lines.append("## Optional sidecar references")
    if full_track_segments_ref:
        lines.append(f"  Full-track Whisper segments: `{full_track_segments_ref}`")
        lines.append(
            "  Use this only if the per-piece transcript is too garbled to resolve locally."
        )
    else:
        lines.append("  Full-track Whisper segments: not included inline.")
    if silence_boundaries_ref:
        lines.append(f"  Silence boundaries: `{silence_boundaries_ref}`")
        lines.append(
            "  This is for fallback cutting review only; the piece timestamps above are usually enough."
        )
    else:
        lines.append("  Silence boundaries: not included inline.")
    lines.append(f"  Track duration: {duration:.3f}")
    lines.append("")


def build_prompt(
    track_path: Path,
    segments: list[dict],
    regions: list[tuple],
    entries: list[dict],
    boundaries: list[tuple],
    duration: float,
    piece_transcripts: list[dict],
    full_track_segments_ref: str | None = None,
    silence_boundaries_ref: str | None = None,
    mapping_mode: str = "exact-window",
    entries_ref: str | None = None,
    current_track_start_index: int | None = None,
) -> str:
    """Build the LLM prompt for matching speech pieces to vocabulary entries."""
    del segments, regions, boundaries  # prompt content depends on prepared artifacts

    first_index = entries[0]["index"]
    last_index = entries[-1]["index"]
    lines: list[str] = []
    lines.append(f"Align the audio track `{track_path.name}` to these vocabulary entries.")
    lines.append("")

    _add_piece_block(lines, piece_transcripts)

    if mapping_mode == "unit-sequential":
        if current_track_start_index is None:
            raise ValueError("current_track_start_index is required for unit-sequential mode")
        candidate_entries = [
            entry for entry in entries if int(entry["index"]) >= current_track_start_index
        ]
        if not candidate_entries:
            raise ValueError(
                f"No candidate entries remain at or after index {current_track_start_index}"
            )
        lines.append("## Sequential mapping constraints")
        lines.append(
            f"  This track starts at index {current_track_start_index} and continues with a contiguous sequence from the candidate list."
        )
        lines.append(
            f"  The candidate file spans indices {first_index}-{last_index} ({len(entries)} entries total)."
        )
        if entries_ref:
            lines.append(f"  Candidate file: `{entries_ref}`")
        lines.append(
            "  Do not invent entries before the known start index."
        )
        lines.append(
            "  Unused candidate entries are allowed only after the final mapped index because they may belong to later tracks."
        )
        lines.append(
            "  Trust the global order more than noisy ASR timestamps."
        )
        lines.append(
            "  Within each entry, the spoken order is `word` first and `sentence` second."
        )
        lines.append("")
        lines.append("## Candidate vocabulary entries from the known start onward")
        for entry in candidate_entries:
            lines.append(
                f"  Index {entry['index']}: {entry['headword']} ({entry['reading']}) — {entry['sentence']}"
            )
        lines.append("")
        _add_sidecars(lines, full_track_segments_ref, silence_boundaries_ref, duration)
        lines.append("## Instructions")
        lines.append("Use the piece transcriptions and piece timestamps as the primary evidence.")
        lines.append(
            "Use the optional full-track file only as backup context when a piece transcript is garbled."
        )
        lines.append(
            "Match each speech piece to the correct vocabulary entry as either `word` or `sentence`."
        )
        lines.append("Rules:")
        lines.append(
            f"1. The track begins at index {current_track_start_index}. The returned JSON must start there."
        )
        lines.append(
            "2. Return one contiguous run only. Do not skip indices, repeat indices, or jump forward and back."
        )
        lines.append(
            "3. Candidate entries after the final mapped index may remain unused because they may belong to later tracks."
        )
        lines.append(
            "4. Determine the final spoken entry on this track from the audio. The last JSON item's `index` is the discovered track end."
        )
        lines.append(
            "5. Each entry normally has one `word` clip followed by one `sentence` clip."
        )
        lines.append(
            "6. Every non-silence piece in this run must appear in exactly one `piece_ids` list. Do not reuse a piece id across clips."
        )
        lines.append(
            "7. Prefer assigning whole pieces to one item. Do not leave trailing closures like った or って unassigned."
        )
        lines.append(
            "8. If a sentence spans multiple pieces, combine them into one sentence clip."
        )
        lines.append(
            "9. Prefer real silence edges for cut boundaries when they reasonably fit the intended item."
        )
        lines.append(
            "10. Final clip spans must not overlap. If silence detection failed and you must split inside a piece, preserve one exact split boundary and keep the adjacent clips non-overlapping."
        )
        lines.append(
            "11. Whisper often misrecognizes Japanese characters or drops leading sounds. Match by reading, sentence context, and sequence position, not exact text."
        )
        lines.append(
            "12. If a very short piece is ambiguous, attach it to the nearest adjacent item and explain that choice in `note`."
        )
    else:
        lines.append("## Exact order constraints")
        lines.append(
            f"  This track covers exactly indices {first_index}-{last_index} "
            f"({len(entries)} entries total)."
        )
        lines.append(
            "  The entries occur in this exact order: no extra entries, no missing entries, no repetition."
        )
        lines.append("  Trust the global order more than noisy ASR timestamps.")
        lines.append("  Within each entry, the spoken order is `word` first and `sentence` second.")
        lines.append("")
        lines.append("## Expected vocabulary entries on this track")
        for entry in entries:
            lines.append(
                f"  Index {entry['index']}: {entry['headword']} ({entry['reading']}) — {entry['sentence']}"
            )
        lines.append("")
        _add_sidecars(lines, full_track_segments_ref, silence_boundaries_ref, duration)
        lines.append("## Instructions")
        lines.append("Use the piece transcriptions and piece timestamps as the primary evidence.")
        lines.append(
            "Use the optional full-track file only as backup context when a piece transcript is garbled."
        )
        lines.append(
            "Match each speech piece to the correct vocabulary entry as either `word` or `sentence`."
        )
        lines.append("Rules:")
        lines.append(
            f"1. The selected entries are the complete contents of this track window. Do not invent content outside indices {first_index}-{last_index}."
        )
        lines.append(
            "2. Keep the exact global order of entries. If ASR is messy, use the neighboring entries and word-then-sentence rhythm to recover the mapping."
        )
        lines.append(
            "3. Each entry normally has one `word` clip followed by one `sentence` clip."
        )
        lines.append(
            "4. Every non-silence piece in this run must appear in exactly one `piece_ids` list. Do not reuse a piece id across clips."
        )
        lines.append(
            "5. Prefer assigning whole pieces to one item. Do not leave trailing closures like った or って unassigned."
        )
        lines.append(
            "6. If a sentence spans multiple pieces, combine them into one sentence clip."
        )
        lines.append(
            "7. Prefer real silence edges for cut boundaries when they reasonably fit the intended item."
        )
        lines.append(
            "8. Final clip spans must not overlap. If silence detection failed and you must split inside a piece, preserve one exact split boundary and keep the adjacent clips non-overlapping."
        )
        lines.append(
            "9. Whisper often misrecognizes Japanese characters or drops leading sounds. Match by reading, sentence context, and sequence position, not exact text."
        )
        lines.append(
            "10. If a very short piece is ambiguous, attach it to the nearest adjacent item and explain that choice in `note`."
        )

    lines.append("")
    lines.append("Output a JSON array with this structure:")
    lines.append(
        '[{"index": N, "word": {"start": X, "end": Y, "piece_ids": [P0], "flags": []}, "sentence": {"start": X, "end": Y, "piece_ids": [P1, P2], "flags": []}, "flags": [], "note": ""}, ...]'
    )
    lines.append("")
    lines.append(
        "If an exact intra-piece boundary is required, include `bridge_split` in the affected clip flags and preserve the exact timestamp for the split boundary."
    )
    lines.append(
        "Only omit a field as a last resort, and even then do not leave any speech piece unaccounted for."
    )
    lines.append("Return JSON only. Do not add prose outside the JSON array.")
    return "\n".join(lines)
