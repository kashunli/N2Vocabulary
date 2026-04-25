"""align — public API for the N2 vocabulary audio alignment pipeline.

Import from here rather than from individual submodules so internal
reorganisation never breaks calling scripts.

    from align import ROOT, load_backend, detect_silence_boundaries, cut_clip
"""
from align._constants import ROOT, DB_PATH, REVIEW_PATH

from align.artifacts import (
    normalize_cache_token,
    whisper_cache_model_label,
    default_wcpp_cache_prefix,
    default_prompt_support_prefix,
    display_path,
    write_wcpp_cache_artifacts,
    write_silence_boundary_artifact,
    piece_transcript_cache_path,
    load_piece_transcript_cache,
)

from align.backend import (
    _read_json_text,
    load_backend,
    transcribe_full_track,
)

from align.silence import (
    detect_silence_boundaries,
    speech_regions,
    enumerate_speech_pieces,
)

from align.pieces import transcribe_speech_pieces

from align.text import to_kana, kana_similarity

from align.boundaries import (
    SNAP_TOLERANCE_SECONDS,
    normalize_flag_list,
    resolve_cut_span,
    summarize_piece_coverage,
    log_boundary_decision,
)

from align.cut import cut_clip, rescore_clip, cut_clips_from_mapping

from align.prompt import build_prompt

__all__ = [
    # constants
    "ROOT", "DB_PATH", "REVIEW_PATH",
    # artifacts
    "normalize_cache_token", "whisper_cache_model_label",
    "default_wcpp_cache_prefix", "default_prompt_support_prefix",
    "display_path", "write_wcpp_cache_artifacts", "write_silence_boundary_artifact",
    "piece_transcript_cache_path", "load_piece_transcript_cache",
    # backend
    "_read_json_text", "load_backend", "transcribe_full_track",
    # silence
    "detect_silence_boundaries", "speech_regions", "enumerate_speech_pieces",
    # pieces
    "transcribe_speech_pieces",
    # text
    "to_kana", "kana_similarity",
    # boundaries
    "SNAP_TOLERANCE_SECONDS", "normalize_flag_list", "resolve_cut_span",
    "summarize_piece_coverage", "log_boundary_decision",
    # cut
    "cut_clip", "rescore_clip", "cut_clips_from_mapping",
    # prompt
    "build_prompt",
]
