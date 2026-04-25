"""Silence-snapping boundary resolution and clip flag utilities.

Design principle: always prefer a real silence edge over a raw LLM timestamp.
The LLM gives us the right mapping (which pieces → which entry) but its
timestamps are only as precise as Whisper's segment boundaries. A real silence
edge (where the waveform is actually quiet) is a much cleaner cut point —
there's no risk of chopping mid-phoneme.

The policy labels written into result JSON ("silence_snap", "near_silence_snap",
"bridge_split", "hard_fallback") let reviewers see exactly how each boundary
was resolved without digging into the code.
"""
from __future__ import annotations

import sys

# How close an LLM-suggested timestamp must be to a real silence edge before
# we snap to it. Symmetric on both sides: if the nearest silence edge is within
# 0.15 s of the LLM's time, we use the silence edge; otherwise we still prefer
# the silence edge (labeled near_silence_snap) over the raw LLM timestamp.
# Previously the window was asymmetric (+0.5s start / -0.1s end), which let the
# snapped start creep past the word onset and silently chop the first syllable.
SNAP_TOLERANCE_SECONDS = 0.15


def normalize_flag_list(value) -> list[str]:
    """Coerce a flags value from the LLM JSON into a clean list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _resolve_boundary(
    target: float,
    boundaries: list[tuple],
    boundary_type: str,
    tolerance: float,
    preserve_exact: bool = False,
    fallback_direction: str = "start",
) -> tuple[float, str, float | None]:
    """Resolve a single clip boundary to the nearest real silence edge.

    boundary_type="end" means we look for silence_end events (speech restarts)
    for the clip's start boundary. boundary_type="start" means silence_start
    events (speech stops) for the clip's end boundary. This matches ffmpeg's
    silencedetect output naming.

    When preserve_exact=True (bridge_split flag), two adjacent entries share a
    speech piece with no silence between them. The LLM must propose a split
    inside the piece; we honor its exact timestamp and skip silence snapping.

    Returns (resolved_time, policy_label, delta_seconds). The policy label is
    stored in the result JSON so reviewers know whether the boundary came from
    a real silence edge or a fallback.
    """
    if preserve_exact:
        return target, "bridge_split", 0.0

    candidates = [t for t, typ in boundaries if typ == boundary_type]
    if not candidates:
        if fallback_direction == "start":
            return max(0.0, target - 0.1), "hard_fallback", None
        return target + 0.1, "hard_fallback", None

    nearest = min(candidates, key=lambda t: abs(t - target))
    delta = abs(nearest - target)
    if delta <= tolerance:
        return nearest, "silence_snap", delta
    return nearest, "near_silence_snap", delta


def resolve_cut_span(
    w_start: float,
    w_end: float,
    boundaries: list[tuple],
    tolerance: float = SNAP_TOLERANCE_SECONDS,
    preserve_boundaries: set[str] | None = None,
) -> tuple[float, float, dict[str, str], dict[str, float | None]]:
    """Resolve a clip span against silence edges or explicit bridge splits.

    Returns (cut_start, cut_end, policies, deltas). `policies` maps "start"/"end"
    to policy labels; `deltas` maps to the snap distance in seconds (or None for
    fallbacks). Both are stored in the result JSON for reviewer inspection.
    """
    preserve = preserve_boundaries or set()
    cut_start, start_policy, start_delta = _resolve_boundary(
        w_start, boundaries,
        boundary_type="end", tolerance=tolerance,
        preserve_exact="start" in preserve, fallback_direction="start",
    )
    cut_end, end_policy, end_delta = _resolve_boundary(
        w_end, boundaries,
        boundary_type="start", tolerance=tolerance,
        preserve_exact="end" in preserve, fallback_direction="end",
    )

    if cut_end <= cut_start:
        cut_start = max(0.0, w_start - 0.1)
        cut_end = max(cut_start + 0.01, w_end + 0.1)
        start_policy = "hard_fallback"
        end_policy = "hard_fallback"
        start_delta = None
        end_delta = None

    return (
        cut_start, cut_end,
        {"start": start_policy, "end": end_policy},
        {"start": start_delta, "end": end_delta},
    )


def summarize_piece_coverage(
    mapping: list[dict],
    pieces: list[dict],
) -> tuple[list[int], list[int], list[int]]:
    """Return (missing_piece_ids, invalid_piece_ids, duplicate_piece_ids).

    Every non-silent speech piece must appear in exactly one clip assignment.
    Missing pieces mean the LLM left real audio unaccounted for (often a filler
    burst or a final syllable at the end of a sentence). Duplicate pieces mean
    two clips would overlap, which breaks ffmpeg cutting. Both conditions are
    logged as warnings so the user can decide whether to re-prompt the LLM.
    """
    piece_ids = {piece["piece_id"] for piece in pieces}
    assignment_counts: dict[int, int] = {}
    invalid: set[int] = set()
    saw_piece_ids = False
    for item in mapping:
        for kind in ("word", "sentence"):
            payload = item.get(kind)
            if not isinstance(payload, dict):
                continue
            payload_piece_ids = payload.get("piece_ids") or []
            if payload_piece_ids:
                saw_piece_ids = True
            for pid in payload_piece_ids:
                try:
                    pid_int = int(pid)
                except (TypeError, ValueError):
                    invalid.add(pid)
                    continue
                if pid_int in piece_ids:
                    assignment_counts[pid_int] = assignment_counts.get(pid_int, 0) + 1
                else:
                    invalid.add(pid_int)
    if not saw_piece_ids:
        return [], [], []
    assigned = set(assignment_counts)
    missing = sorted(piece_ids - assigned)
    duplicates = sorted(pid for pid, count in assignment_counts.items() if count > 1)
    return missing, sorted(invalid, key=str), duplicates


def log_boundary_decision(
    kind: str,
    idx: int,
    policies: dict[str, str],
    deltas: dict[str, float | None],
) -> None:
    """Print a warning to stderr for any non-silence_snap boundary decisions."""
    notable = [edge for edge, policy in policies.items() if policy != "silence_snap"]
    if not notable:
        return
    details = []
    for edge in notable:
        policy = policies[edge]
        delta = deltas.get(edge)
        if delta is None:
            details.append(f"{edge}={policy}")
        else:
            details.append(f"{edge}={policy}(Δ={delta:.3f}s)")
    print(f"  [WARN] {kind}{idx}: " + ", ".join(details), file=sys.stderr, flush=True)
