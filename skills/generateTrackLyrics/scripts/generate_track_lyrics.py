#!/usr/bin/env python3
"""Generate synchronized CD-track lyrics for N1, N2, or N3."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from audio_match import AudioMatcher, padded_speech_bounds
from formats import write_book_outputs
from model import Cue, EntryRequest
from sources import load_n1_manifest, load_n2_entries, load_n3_entries


DIRECT_THRESHOLD = 0.75
REVIEW_THRESHOLD = 0.90


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def track_key(path: str) -> str:
    source = Path(path)
    return f"{source.parent.name}__{source.stem}"


def generate_n1(root: Path, n1_root: Path, output_root: Path) -> dict:
    rows, source_manifest = load_n1_manifest(n1_root)
    cues: list[Cue] = []
    for row in rows:
        source = str((n1_root / row["source_audio"]).resolve())
        text = row["expected_text"]
        if row["kind"] == "word" and row.get("headword") and row["headword"] != text:
            text = f"{row['headword']}【{text}】"
        cues.append(
            Cue(
                book="n1",
                track=row["track"],
                entry_id=int(row["index"]),
                kind=row["kind"],
                text=text,
                start=float(row["start"]),
                end=float(row["end"]),
                source_audio=source,
                source_clip=str((n1_root / "data" / "processed" / "audio_clips" / row["file"]).resolve()),
                alignment_method="accepted_source_manifest",
                confidence=1.0,
                example_position=0 if row["kind"] == "sentence" else None,
            )
        )
    return write_book_outputs(
        output_root / "n1",
        book="n1",
        cues=cues,
        expected_counts={"cue_count": 2340, "word_count": 1170, "sentence_count": 1170, "track_count": 93},
        provenance={
            "source_repository": str(n1_root.resolve()),
            "method": "direct conversion from accepted N1 clip manifest",
            "source_manifest_status": source_manifest["status"],
        },
        direct_threshold=DIRECT_THRESHOLD,
    )


def direct_cue(
    matcher: AudioMatcher,
    request,
    source: str,
    book: str,
) -> Cue:
    offset, score, duration = matcher.match(source, request.clip_path)
    review = [] if score >= REVIEW_THRESHOLD else ["correlation_below_review_threshold"]
    return Cue(
        book=book,
        track=track_key(source),
        entry_id=request.entry_id,
        kind=request.kind,
        text=request.text,
        start=offset,
        end=offset + duration,
        source_audio=source,
        source_clip=request.clip_path,
        alignment_method="waveform_correlation",
        confidence=score,
        example_position=request.example_position,
        review_reasons=review,
    )


def generate_n2(root: Path, output_root: Path, pilot_limit: int | None = None) -> dict:
    entries = load_n2_entries(root)
    if pilot_limit:
        entries = entries[:pilot_limit]
    matcher = AudioMatcher()
    cues: list[Cue] = []
    candidate_evidence: list[dict] = []
    resolved_entries: list[EntryRequest] = []
    missing_words: list[EntryRequest] = []
    unmatched_sentences: list[tuple[EntryRequest, object, float]] = []
    current_source_group = None
    preferred_source = None
    for number, entry in enumerate(entries, 1):
        source_group = tuple(entry.source_candidates)
        if current_source_group != source_group:
            matcher.clear_sources()
            current_source_group = source_group
            preferred_source = None
        sentence = entry.sentences[0]
        candidates = None
        selection_method = "chapter_search"
        if preferred_source is not None:
            offset, score, duration = matcher.match(preferred_source, sentence.clip_path)
            if score >= REVIEW_THRESHOLD:
                source = preferred_source
                selection_method = "previous_verified_track"
        if selection_method == "chapter_search":
            source, offset, score, duration, candidates = matcher.match_candidates(
                entry.source_candidates, sentence.clip_path
            )
        preferred_source = source
        candidate_evidence.append(
            {
                "entry_id": entry.entry_id,
                "winner": source,
                "winner_score": score,
                "runner_up_score": candidates[1]["score"] if candidates and len(candidates) > 1 else None,
                "selection_method": selection_method,
            }
        )
        resolved_entry = replace(entry, source_candidates=[source])
        resolved_entries.append(resolved_entry)
        if score >= DIRECT_THRESHOLD:
            review = [] if score >= REVIEW_THRESHOLD else ["sentence_track_match_below_review_threshold"]
            cues.append(Cue(
                book="n2",
                track=track_key(source),
                entry_id=entry.entry_id,
                kind="sentence",
                text=sentence.text,
                start=offset,
                end=offset + duration,
                source_audio=source,
                source_clip=sentence.clip_path,
                alignment_method="waveform_correlation",
                confidence=score,
                example_position=0,
                review_reasons=review,
            ))
        else:
            unmatched_sentences.append((resolved_entry, sentence, score))

        word_candidate = direct_cue(matcher, entry.word, source, "n2")
        if word_candidate.confidence >= DIRECT_THRESHOLD:
            cues.append(word_candidate)
        else:
            missing_words.append(resolved_entry)
        if number % 50 == 0 or number == len(entries):
            print(f"N2 matched {number}/{len(entries)} entries", flush=True)

    infer_missing_words(matcher, cues, missing_words, book="n2")
    infer_unmatched_sentences(matcher, cues, unmatched_sentences, resolved_entries, book="n2")

    output_dir = output_root / ("n2_pilot" if pilot_limit else "n2")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "track_candidate_evidence.json").write_text(
        json.dumps(candidate_evidence, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    expected_entries = len(entries)
    return write_book_outputs(
        output_dir,
        book="n2",
        cues=cues,
        expected_counts={"cue_count": expected_entries * 2, "word_count": expected_entries, "sentence_count": expected_entries},
        provenance={
            "source_repository": str(root.resolve()),
            "database": str((root / "wordService/data/n2vocab.sqlite").resolve()),
            "method": "sentence-first unit track selection plus waveform correlation",
            "pilot_limit": pilot_limit,
        },
        direct_threshold=DIRECT_THRESHOLD,
    )


def generate_n3(root: Path, n3_root: Path, output_root: Path, pilot_limit: int | None = None) -> dict:
    entries = load_n3_entries(root, n3_root)
    if pilot_limit:
        entries = entries[:pilot_limit]
    output_dir = output_root / ("n3_pilot" if pilot_limit else "n3")
    cache_dir = output_dir / "cache"
    cache_path = cache_dir / "direct_alignments.json"
    signature = input_signature(entries)
    matcher = AudioMatcher()
    entry_by_id = {entry.entry_id: entry for entry in entries}
    cached = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else None
    if cached and cached.get("input_signature") == signature:
        cues = [Cue(**row) for row in cached["cues"]]
        missing_words = [entry_by_id[entry_id] for entry_id in cached["missing_word_ids"]]
        unmatched_sentences = [
            (entry_by_id[row["entry_id"]], entry_by_id[row["entry_id"]].sentences[0], row["score"])
            for row in cached["unmatched_sentences"]
        ]
        # Older cache rows may contain a decoded clip that failed the direct
        # threshold. Normalize them into the inference path on every resume.
        low_word_ids = {
            cue.entry_id
            for cue in cues
            if cue.kind == "word"
            and cue.alignment_method == "waveform_correlation"
            and cue.confidence < DIRECT_THRESHOLD
        }
        cues = [
            cue
            for cue in cues
            if not (cue.kind == "word" and cue.entry_id in low_word_ids)
        ]
        missing_words.extend(
            entry_by_id[entry_id]
            for entry_id in sorted(low_word_ids)
            if entry_id not in {entry.entry_id for entry in missing_words}
        )
        print(f"N3 resumed {len(entries)}/{len(entries)} direct alignments from signed cache", flush=True)
    else:
        cues = []
        missing_words = []
        unmatched_sentences = []
        current_source = None
        for number, entry in enumerate(entries, 1):
            source = entry.source_candidates[0]
            if source != current_source:
                matcher.clear_sources()
                current_source = source
            if entry.word.clip_path:
                word_candidate = direct_cue(matcher, entry.word, source, "n3")
                if word_candidate.confidence >= DIRECT_THRESHOLD:
                    cues.append(word_candidate)
                else:
                    missing_words.append(entry)
            else:
                missing_words.append(entry)
            for sentence in entry.sentences:
                candidate = direct_cue(matcher, sentence, source, "n3")
                if candidate.confidence >= DIRECT_THRESHOLD:
                    cues.append(candidate)
                else:
                    unmatched_sentences.append((entry, sentence, candidate.confidence))
            if number % 50 == 0 or number == len(entries):
                print(f"N3 matched {number}/{len(entries)} entries", flush=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "input_signature": signature,
                    "cues": [cue.to_dict() for cue in cues],
                    "missing_word_ids": [entry.entry_id for entry in missing_words],
                    "unmatched_sentences": [
                        {"entry_id": entry.entry_id, "score": score}
                        for entry, _sentence, score in unmatched_sentences
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    unresolved = infer_missing_words(matcher, cues, missing_words, book="n3")
    unresolved.extend(infer_unmatched_sentences(
        matcher, cues, unmatched_sentences, entries, book="n3"
    ))
    unresolved.extend(reconcile_inferred_overlaps(cues))
    expected_words = len(entries) - sum(item["kind"] == "word" for item in unresolved)
    # A source track can end immediately after its final headword; a later
    # replacement study clip does not prove that sentence existed on the CD.
    expected_sentences = sum(len(entry.sentences) for entry in entries) - sum(
        item["kind"] == "sentence" for item in unresolved
    )
    return write_book_outputs(
        output_dir,
        book="n3",
        cues=cues,
        expected_counts={"cue_count": expected_words + expected_sentences, "word_count": expected_words, "sentence_count": expected_sentences},
        provenance={
            "source_repository": str(n3_root.resolve()),
            "database": str((root / "wordService/data/n2vocab.sqlite").resolve()),
            "method": "known source range plus waveform correlation; silence inference for missing CD word clips",
            "pilot_limit": pilot_limit,
        },
        direct_threshold=DIRECT_THRESHOLD,
        unresolved_items=unresolved,
    )


def input_signature(entries: list[EntryRequest]) -> str:
    """Fingerprint N3 mapping inputs so cached offsets cannot outlive them."""
    rows = []
    for entry in entries:
        paths = [entry.source_candidates[0], entry.word.clip_path]
        paths.extend(sentence.clip_path for sentence in entry.sentences)
        files = []
        for value in paths:
            if value is None:
                files.append(None)
                continue
            path = Path(value)
            stat = path.stat()
            files.append([str(path.resolve()), stat.st_size, stat.st_mtime_ns])
        rows.append(
            [
                entry.entry_id,
                entry.word.text,
                [sentence.text for sentence in entry.sentences],
                files,
            ]
        )
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def infer_missing_words(
    matcher: AudioMatcher,
    cues: list[Cue],
    missing_entries: list[EntryRequest],
    *,
    book: str,
) -> list[dict]:
    """Recover visibly unresolved words without pretending they were matched.

    Most missing word clips still have a matched first sentence. The closest
    non-silent region immediately before that sentence is the spoken headword.
    A word-only entry is bracketed by already matched neighboring entries.
    Every inferred result stays in the review queue.
    """
    segments_by_source: dict[str, list[tuple[float, float]]] = {}
    unresolved: list[dict] = []
    for entry in missing_entries:
        source = entry.source_candidates[0]
        if source not in segments_by_source:
            segments_by_source[source] = matcher.speech_segments(source)
        segments = segments_by_source[source]
        same_entry_sentences = sorted(
            [cue for cue in cues if cue.source_audio == source and cue.entry_id == entry.entry_id and cue.kind == "sentence"],
            key=lambda cue: cue.start,
        )
        reason = "missing_or_non_cd_word_clip_inferred_before_sentence"
        candidate = None
        if same_entry_sentences:
            anchor = same_entry_sentences[0].start
            eligible = [segment for segment in segments if segment[1] <= anchor - 0.03 and anchor - segment[1] <= 3.0]
            if eligible:
                candidate = eligible[-1]
                next_start = anchor
        else:
            lower = [cue.end for cue in cues if cue.source_audio == source and cue.entry_id < entry.entry_id]
            upper = [cue.start for cue in cues if cue.source_audio == source and cue.entry_id > entry.entry_id]
            low = max(lower, default=0.0)
            high = min(upper, default=float("inf"))
            eligible = [segment for segment in segments if segment[0] >= low - 0.05 and segment[1] <= high + 0.05]
            if eligible:
                candidate = eligible[0]
                next_start = high if high != float("inf") else None
            reason = "missing_or_non_cd_word_clip_inferred_between_neighbors"
        if candidate is None:
            # A zero-length placeholder would corrupt the timed-text contract,
            # so fail loudly and let the run remain incomplete.
            raise RuntimeError(f"Could not infer {book.upper()} word boundary for entry {entry.entry_id}")
        start, end = padded_speech_bounds(candidate, next_start)
        cues.append(
            Cue(
                book=book,
                track=track_key(source),
                entry_id=entry.entry_id,
                kind="word",
                text=entry.word.text,
                start=start,
                end=end,
                source_audio=source,
                source_clip=None,
                alignment_method="silence_inference",
                confidence=0.70,
                review_reasons=[reason],
            )
        )
    return unresolved


def reconcile_inferred_overlaps(cues: list[Cue]) -> list[dict]:
    """Remove inferred aliases/absences that reuse verified neighboring audio."""
    unresolved: list[dict] = []
    remove_ids: set[int] = set()
    by_track: dict[str, list[Cue]] = defaultdict(list)
    for cue in cues:
        by_track[cue.track].append(cue)

    for track_cues in by_track.values():
        ordered = sorted(track_cues, key=lambda cue: (cue.start, cue.end))
        for previous, current in zip(ordered, ordered[1:]):
            overlap = previous.end - current.start
            if overlap <= 0.025:
                continue
            previous_direct = previous.alignment_method == "waveform_correlation"
            current_direct = current.alignment_method == "waveform_correlation"
            if previous_direct and current_direct:
                if (
                    previous.kind == current.kind == "sentence"
                    and previous.text == current.text
                    and abs(previous.start - current.start) < 0.01
                    and abs(previous.end - current.end) < 0.01
                ):
                    remove_ids.add(id(current))
                    unresolved.append(unresolved_from_cue(current, "shared_sentence_alias_of_verified_neighbor"))
                continue
            if previous_direct != current_direct:
                inferred = current if previous_direct else previous
                remove_ids.add(id(inferred))
                unresolved.append(unresolved_from_cue(inferred, "inferred_region_duplicates_verified_neighbor"))
                continue
            if previous.entry_id == current.entry_id and previous.kind == "word" and current.kind == "sentence":
                previous.end = current.start
                previous.review_reasons.append("inferred_padding_trimmed_at_sentence_boundary")

    cues[:] = [cue for cue in cues if id(cue) not in remove_ids]
    return unresolved


def unresolved_from_cue(cue: Cue, reason: str) -> dict:
    return {
        "book": cue.book,
        "entry_id": cue.entry_id,
        "kind": cue.kind,
        "text": cue.text,
        "source_audio": cue.source_audio,
        "source_clip": cue.source_clip,
        "alignment_method": "confirmed_not_distinct_on_source_track",
        "confidence": 0.0,
        "review_reasons": [reason],
    }


def infer_unmatched_sentences(
    matcher: AudioMatcher,
    cues: list[Cue],
    unmatched: list[tuple[EntryRequest, object, float]],
    all_entries: list[EntryRequest],
    *,
    book: str,
) -> list[dict]:
    """Time a main CD sentence between its verified word and the next word.

    A handful of live `sentenceN.mp3` files are later replacement/study audio,
    not excerpts of the original track. Their canonical position-0 text still
    identifies the CD's main example. Verified word anchors plus FFmpeg speech
    regions recover the CD boundary without treating the replacement clip as
    timing evidence.
    """
    segments_by_source: dict[str, list[tuple[float, float]]] = {}
    duration_by_source: dict[str, float] = {}
    entries_by_source: dict[str, list[EntryRequest]] = defaultdict(list)
    unresolved: list[dict] = []
    for item in all_entries:
        entries_by_source[item.source_candidates[0]].append(item)
    for entry, sentence, failed_score in unmatched:
        source = entry.source_candidates[0]
        if source not in segments_by_source:
            segments_by_source[source] = matcher.speech_segments(source)
            duration_by_source[source] = len(matcher.decode(source, source=True)) / matcher.sample_rate
        ordered_entries = entries_by_source[source]
        local_index = next(index for index, item in enumerate(ordered_entries) if item.entry_id == entry.entry_id)
        group_end = entry
        # Some N3 CD examples are shared by adjacent words. The JSON stores the
        # sentence on the first word, while the recording speaks all linked
        # headwords and then the shared sentence. Extend through following
        # word-only entries before selecting the sentence region.
        scan = local_index + 1
        while scan < len(ordered_entries) and not ordered_entries[scan].sentences:
            group_end = ordered_entries[scan]
            scan += 1
        word = next(
            cue
            for cue in cues
            if cue.source_audio == source and cue.entry_id == group_end.entry_id and cue.kind == "word"
        )
        next_words = sorted(
            [
                cue
                for cue in cues
                if cue.source_audio == source and cue.entry_id > group_end.entry_id and cue.kind == "word"
            ],
            key=lambda cue: cue.start,
        )
        upper = next_words[0].start if next_words else duration_by_source[source]
        eligible = [
            segment
            for segment in segments_by_source[source]
            if segment[0] >= word.end - 0.05 and segment[1] <= upper + 0.05
        ]
        if not eligible:
            # Confirm absence from the CD only when silence analysis finds no
            # speech after the verified word and before the next verified word
            # (or physical track end). This covers both an omitted sentence in
            # the middle of a track and a track that ends after its last word.
            speech_after_word = [
                segment
                for segment in segments_by_source[source]
                if segment[1] > word.end + 0.15 and segment[0] < upper - 0.05
            ]
            if not speech_after_word:
                absence_reason = (
                    "source_advances_to_next_word_without_sentence"
                    if next_words
                    else "source_track_ends_after_final_word_without_sentence"
                )
                unresolved.append(
                    {
                        "book": book,
                        "entry_id": entry.entry_id,
                        "kind": "sentence",
                        "text": sentence.text,
                        "source_audio": source,
                        "source_clip": sentence.clip_path,
                        "alignment_method": "confirmed_absent_from_source_track",
                        "confidence": 0.0,
                        "review_reasons": [
                            absence_reason,
                            f"replacement_clip_correlation={failed_score:.6f}",
                        ],
                    }
                )
                continue
            raise RuntimeError(
                f"Could not infer {book.upper()} main sentence boundary for entry {entry.entry_id}"
            )
        start, _ = padded_speech_bounds(eligible[0], None)
        _, end = padded_speech_bounds(eligible[-1], upper)
        cues.append(
            Cue(
                book=book,
                track=track_key(source),
                entry_id=entry.entry_id,
                kind="sentence",
                text=sentence.text,
                start=start,
                end=end,
                source_audio=source,
                source_clip=None,
                alignment_method="word_anchor_and_silence_inference",
                confidence=0.70,
                example_position=0,
                review_reasons=[
                    "main_sentence_clip_did_not_match_cd_track",
                    f"replacement_clip_correlation={failed_score:.6f}",
                ],
            )
        )
    return unresolved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", choices=("n1", "n2", "n3", "all"), required=True)
    parser.add_argument("--pilot-limit", type=int, default=None, help="Generate only the first N entries (N2/N3).")
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--n1-root", type=Path, default=Path(r"D:\n2Prepare\minikaraWordN1"))
    parser.add_argument("--n3-root", type=Path, default=Path(r"D:\n2Prepare\N3Words"))
    args = parser.parse_args()
    root = repo_root()
    output_root = args.output_root or root / "output" / "track_lyrics"

    books = ("n1", "n2", "n3") if args.book == "all" else (args.book,)
    reports = {}
    for book in books:
        if book == "n1":
            reports[book] = generate_n1(root, args.n1_root, output_root)
        elif book == "n2":
            reports[book] = generate_n2(root, output_root, args.pilot_limit)
        else:
            reports[book] = generate_n3(root, args.n3_root, output_root, args.pilot_limit)
        print(f"{book.upper()}: {reports[book]['status']} ({reports[book]['error_count']} errors)")


if __name__ == "__main__":
    main()
