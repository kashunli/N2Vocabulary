#!/usr/bin/env python3
"""Audit vocabulary text against human audio with resumable local ASR.

The canonical database is read-only. Generated transcripts are deliberately
kept outside it because ASR is noisy evidence, not source-of-truth text.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata
from contextlib import closing
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WCPP_BINARY = ROOT / "tools" / "whispercpp-windows" / "whisper-cli.exe"
DEFAULT_WCPP_MODEL = ROOT / "tools" / "whispercpp-windows" / "ggml-large-v3-turbo.bin"

DEFAULT_DB = ROOT / "wordService" / "data" / "n2vocab.sqlite"
PUNCTUATION_RE = re.compile(r"[\s「」『』（）()［］\[\]{}<>【】・…。.，、／/'!！?？:：;；~〜]")


@dataclass(frozen=True)
class AuditItem:
    entry_id: int
    item_id: int
    source_index: int
    unit_number: int
    position: int
    headword: str
    reading: str
    word_clip: str
    sentence: str
    sentence_clip: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit vocabulary headwords and main sentences against human audio."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--book", default="N2")
    parser.add_argument("--unit", type=int)
    parser.add_argument("--start-index", type=int)
    parser.add_argument(
        "--backend",
        choices=("faster-whisper", "whisper-cpp"),
        default="faster-whisper",
    )
    parser.add_argument("--whisper-cpp-binary", type=Path, default=DEFAULT_WCPP_BINARY)
    parser.add_argument("--whisper-cpp-model", type=Path, default=DEFAULT_WCPP_MODEL)
    parser.add_argument("--whisper-cpp-batch-size", type=int, default=100)
    parser.add_argument(
        "--whisper-cpp-threads",
        type=int,
        default=8,
        help="CPU helper threads; audio inference still uses the configured Vulkan GPU.",
    )
    parser.add_argument("--end-index", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only", choices=("both", "words", "sentences"), default="both")
    parser.add_argument("--model", default="small", help="Cached faster-whisper model name or path")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--sentence-pass-threshold", type=float, default=0.96)
    parser.add_argument("--word-pass-threshold", type=float, default=0.88)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "cache" / "vocabulary_audio_audit")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "work" / "vocabulary_audio_audit")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="Permit faster-whisper to download a missing model; offline loading is the default.",
    )
    return parser


def normalize_surface(text: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", html.unescape(str(text or "")))
    return PUNCTUATION_RE.sub("", normalized).lower()


def phonetic_hiragana(text: str | None) -> str:
    """Convert Japanese surface forms to comparable hiragana when possible."""
    if not text:
        return ""
    try:
        import jaconv
        from fugashi import Tagger
    except ImportError:
        # The fallback remains useful for kana-only text and makes preflight/tests
        # independent of optional linguistic packages.
        return normalize_surface(text)

    tagger = phonetic_hiragana.__dict__.setdefault("_tagger", Tagger())
    pieces: list[str] = []
    for token in tagger(str(text)):
        feature = token.feature
        kana = getattr(feature, "kana", None) or getattr(feature, "pron", None) or ""
        pieces.append(jaconv.kata2hira(kana if kana and kana != "*" else token.surface))
    return normalize_surface("".join(pieces))


def similarity(expected: str, actual: str) -> float:
    if not expected or not actual:
        return 0.0
    if expected == actual:
        return 1.0
    return SequenceMatcher(None, expected, actual).ratio()


def diff_summary(expected: str, actual: str) -> str:
    """Return compact changed spans; these make long-sentence errors visible."""
    if not expected or not actual:
        return "empty transcript" if not actual else "empty expected text"
    changes: list[str] = []
    for operation, i1, i2, j1, j2 in SequenceMatcher(None, expected, actual).get_opcodes():
        if operation == "equal":
            continue
        changes.append(f"{operation}:{expected[i1:i2] or '∅'}→{actual[j1:j2] or '∅'}")
    return "; ".join(changes[:8])


def connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"database not found: {path}")
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def load_items(
    db_path: Path,
    book: str,
    unit: int | None = None,
    start_index: int | None = None,
    end_index: int | None = None,
    limit: int | None = None,
) -> list[AuditItem]:
    conditions = ["be.book_code = ?", "ie.kind = 'main_sentence'"]
    params: list[Any] = [book]
    if unit is not None:
        conditions.append("be.unit_number = ?")
        params.append(unit)
    if start_index is not None:
        conditions.append("be.source_index >= ?")
        params.append(start_index)
    if end_index is not None:
        conditions.append("be.source_index <= ?")
        params.append(end_index)

    sql = f"""
        SELECT
            be.entry_id,
            be.item_id,
            be.source_index,
            be.unit_number,
            be.position,
            vi.kanji AS headword,
            COALESCE(vi.reading, '') AS reading,
            COALESCE(vi.word_clip, be.word_clip, '') AS word_clip,
            ie.text AS sentence,
            COALESCE(ie.audio_clip, be.sentence_clip, '') AS sentence_clip
        FROM book_entries AS be
        JOIN vocabulary_items AS vi ON vi.item_id = be.item_id
        JOIN item_examples AS ie ON ie.item_id = be.item_id
        JOIN item_example_sources AS ies
          ON ies.item_id = ie.item_id
         AND ies.position = ie.position
         AND ies.source_book_code = be.book_code
         AND ies.source_index = be.source_index

        WHERE {' AND '.join(conditions)}
        ORDER BY be.source_index
    """
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    with closing(connect_read_only(db_path)) as connection:
        rows = connection.execute(sql, params).fetchall()
    return [AuditItem(**dict(row)) for row in rows]


def resolve_audio_path(stored_path: str) -> Path | None:
    if not stored_path:
        return None
    path = Path(stored_path.replace("/", str(Path("/")).replace("/", "\\") if sys.platform == "win32" else "/"))
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def file_identity(path: Path | None) -> str:
    if path is None or not path.is_file():
        return "missing"
    stat = path.stat()
    return f"{path.as_posix()}:{stat.st_size}:{stat.st_mtime_ns}"


def run_label(args: argparse.Namespace) -> str:
    scope = f"unit{args.unit:02d}" if args.unit is not None else "all"
    if args.start_index is not None or args.end_index is not None:
        scope += f"_{args.start_index or 'first'}-{args.end_index or 'last'}"
    if args.limit is not None:
        scope += f"_limit{args.limit}"
    return f"{args.book.lower()}_{scope}_{args.only}"


def asr_settings(args: argparse.Namespace) -> str:
    if args.backend == "whisper-cpp":
        model = args.whisper_cpp_model.resolve()
        return f"whisper-cpp:{model}:{args.whisper_cpp_threads}:ja"
    return (
        f"faster-whisper:{args.model}:{args.device}:"
        f"{args.compute_type}:beam{args.beam_size}:ja"
    )


def asr_cache_label(args: argparse.Namespace) -> str:
    """Keep transcript reuse independent from the selected unit/range."""
    model_name = args.whisper_cpp_model.name if args.backend == "whisper-cpp" else Path(args.model).name
    raw = f"{args.backend}_{model_name}_{args.device}_{args.compute_type}_beam{args.beam_size}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw)


def cache_key(path: Path | None, args: argparse.Namespace) -> str:
    return hashlib.sha256(f"{asr_settings(args)}:{file_identity(path)}".encode("utf-8")).hexdigest()


def read_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class FasterWhisperTranscriber:
    def __init__(self, args: argparse.Namespace) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Install faster-whisper before running the audio audit") from exc
        self.model = WhisperModel(
            args.model,
            device=args.device,
            compute_type=args.compute_type,
            local_files_only=not args.allow_download,
        )
        self.beam_size = args.beam_size

    def transcribe(self, path: Path) -> dict[str, Any]:
        started = time.perf_counter()
        segments, info = self.model.transcribe(
            str(path),
            language="ja",
            beam_size=self.beam_size,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        materialized = list(segments)
        text = "".join(segment.text for segment in materialized).strip()
        avg_logprob = (
            sum(segment.avg_logprob for segment in materialized) / len(materialized)
            if materialized
            else None
        )
        return {
            "text": text,
            "language": info.language,
            "language_probability": round(float(info.language_probability), 4),
            "avg_logprob": round(float(avg_logprob), 4) if avg_logprob is not None else None,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }


class WhisperCppBatchTranscriber:
    """Transcribe many short clips per model load with the local Vulkan CLI."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.binary = args.whisper_cpp_binary.resolve()
        self.model = args.whisper_cpp_model.resolve()
        self.batch_size = args.whisper_cpp_batch_size
        self.threads = args.whisper_cpp_threads
        if not self.binary.is_file():
            raise FileNotFoundError(f"whisper.cpp binary not found: {self.binary}")
        if not self.model.is_file():
            raise FileNotFoundError(f"whisper.cpp model not found: {self.model}")
        if self.batch_size < 1:
            raise ValueError("--whisper-cpp-batch-size must be positive")

    def _run(self, paths: list[Path]) -> dict[Path, dict[str, Any]]:
        started = time.perf_counter()
        command = [
            str(self.binary),
            "-m",
            str(self.model),
            "-l",
            "ja",
            "-t",
            str(self.threads),
            "-nt",
            "-np",
            *[str(path) for path in paths],
        ]
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"whisper.cpp failed with exit code {process.returncode}: {process.stderr[-2000:]}"
            )
        lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
        if len(lines) != len(paths):
            if len(paths) == 1:
                lines = [" ".join(lines)]
            else:
                # A rare multi-segment clip makes stdout line counts ambiguous.
                # Retry those files separately so transcripts cannot shift rows.
                merged: dict[Path, dict[str, Any]] = {}
                for path in paths:
                    merged.update(self._run([path]))
                return merged
        elapsed_each = (time.perf_counter() - started) / max(1, len(paths))
        return {
            path: {
                "text": transcript,
                "language": "ja",
                "language_probability": None,
                "avg_logprob": None,
                "elapsed_seconds": round(elapsed_each, 3),
            }
            for path, transcript in zip(paths, lines)
        }

    def transcribe_batches(self, paths: list[Path]) -> Iterable[dict[Path, dict[str, Any]]]:
        for start in range(0, len(paths), self.batch_size):
            yield self._run(paths[start : start + self.batch_size])



def compare(expected: str, transcript: str, threshold: float) -> dict[str, Any]:
    expected_surface = normalize_surface(expected)
    actual_surface = normalize_surface(transcript)
    expected_phonetic = phonetic_hiragana(expected)
    actual_phonetic = phonetic_hiragana(transcript)
    surface_score = similarity(expected_surface, actual_surface)
    phonetic_score = similarity(expected_phonetic, actual_phonetic)
    score = max(surface_score, phonetic_score)
    if not transcript:
        status = "asr_empty"
    elif score >= threshold:
        status = "pass"
    else:
        status = "review"
    return {
        "status": status,
        "score": round(score, 4),
        "surface_score": round(surface_score, 4),
        "phonetic_score": round(phonetic_score, 4),
        "expected_phonetic": expected_phonetic,
        "transcript_phonetic": actual_phonetic,
        "phonetic_diff": diff_summary(expected_phonetic, actual_phonetic),
    }


def selected_kinds(only: str) -> tuple[str, ...]:
    if only == "words":
        return ("word",)
    if only == "sentences":
        return ("sentence",)
    return ("word", "sentence")


def audit_items(args: argparse.Namespace, items: list[AuditItem]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cache_path = args.cache_dir / asr_cache_label(args) / "transcripts.json"
    cache = read_cache(cache_path)
    # Merge caches written by the earlier scope-specific layout. Cache keys
    # include the complete ASR configuration and audio identity, so unrelated
    # entries are harmless and matching Unit runs seed the full-book run.
    for legacy_path in args.cache_dir.glob("*/transcripts.json"):
        if legacy_path.resolve() != cache_path.resolve():
            cache.update(read_cache(legacy_path))
    results: list[dict[str, Any]] = []
    counters = {"transcribed": 0, "cache_hits": 0, "missing_audio": 0}
    new_keys: set[str] = set()

    if args.backend == "whisper-cpp":
        transcriber: Any = WhisperCppBatchTranscriber(args)
        pending: dict[str, Path] = {}
        for item in items:
            for kind in selected_kinds(args.only):
                stored_path = item.word_clip if kind == "word" else item.sentence_clip
                audio_path = resolve_audio_path(stored_path)
                if audio_path is None or not audio_path.is_file():
                    continue
                key = cache_key(audio_path, args)
                if args.force or key not in cache:
                    pending[key] = audio_path

        completed = 0
        for batch in transcriber.transcribe_batches(list(pending.values())):
            for audio_path, transcript_data in batch.items():
                key = cache_key(audio_path, args)
                cache[key] = transcript_data
                new_keys.add(key)
            completed += len(batch)
            counters["transcribed"] += len(batch)
            write_json_atomic(cache_path, cache)
            print(
                f"[ASR {completed:04d}/{len(pending):04d}] "
                f"whisper.cpp batch cached",
                flush=True,
            )
    else:
        transcriber = FasterWhisperTranscriber(args)

    for ordinal, item in enumerate(items, start=1):
        row = asdict(item)
        row["comparisons"] = {}
        for kind in selected_kinds(args.only):
            expected = item.reading or item.headword if kind == "word" else item.sentence
            stored_path = item.word_clip if kind == "word" else item.sentence_clip
            audio_path = resolve_audio_path(stored_path)
            if audio_path is None or not audio_path.is_file():
                row["comparisons"][kind] = {
                    "status": "missing_audio",
                    "expected": expected,
                    "audio_clip": stored_path,
                    "transcript": "",
                    "score": 0.0,
                }
                counters["missing_audio"] += 1
                continue

            key = cache_key(audio_path, args)
            transcript_data = (
                cache.get(key) if args.backend == "whisper-cpp" else (None if args.force else cache.get(key))
            )
            if transcript_data is None:
                if args.backend == "whisper-cpp":
                    raise RuntimeError(f"missing batch transcript for {audio_path}")
                transcript_data = transcriber.transcribe(audio_path)
                cache[key] = transcript_data
                new_keys.add(key)
                counters["transcribed"] += 1
                # Checkpoint each result so interruption never loses an expensive pass.
                write_json_atomic(cache_path, cache)
            elif key not in new_keys:
                counters["cache_hits"] += 1

            threshold = args.word_pass_threshold if kind == "word" else args.sentence_pass_threshold
            comparison = compare(expected, transcript_data["text"], threshold)
            comparison.update(
                {
                    "expected": expected,
                    "audio_clip": stored_path,
                    "transcript": transcript_data["text"],
                    "asr": {k: v for k, v in transcript_data.items() if k != "text"},
                }
            )
            row["comparisons"][kind] = comparison

        statuses = [value["status"] for value in row["comparisons"].values()]
        row["status"] = "review" if any(status != "pass" for status in statuses) else "pass"
        scores = [float(value.get("score", 0.0)) for value in row["comparisons"].values()]
        row["priority_score"] = round(min(scores, default=0.0), 4)
        results.append(row)
        print(
            f"[{ordinal:04d}/{len(items):04d}] N2 #{item.source_index} "
            f"{item.headword}: {row['status']} ({row['priority_score']:.3f})",
            flush=True,
        )

    return results, {"cache_path": str(cache_path), **counters}


def review_rows(results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in results:
        for kind, comparison in item["comparisons"].items():
            if comparison["status"] == "pass":
                continue
            rows.append(
                {
                    "source_index": item["source_index"],
                    "unit": item["unit_number"],
                    "headword": item["headword"],
                    "kind": kind,
                    "status": comparison["status"],
                    "score": comparison.get("score", 0.0),
                    "expected": comparison.get("expected", ""),
                    "transcript": comparison.get("transcript", ""),
                    "phonetic_diff": comparison.get("phonetic_diff", ""),
                    "audio_clip": comparison.get("audio_clip", ""),
                }
            )
    return sorted(rows, key=lambda row: (float(row["score"]), int(row["source_index"]), row["kind"]))


def write_outputs(args: argparse.Namespace, items: list[AuditItem], results: list[dict[str, Any]], run: dict[str, Any]) -> None:
    output_dir = args.output_dir / run_label(args)
    output_dir.mkdir(parents=True, exist_ok=True)
    queue = review_rows(results)
    write_json_atomic(output_dir / "audit.json", {"run": run, "items": results})

    fields = [
        "source_index", "unit", "headword", "kind", "status", "score",
        "expected", "transcript", "phonetic_diff", "audio_clip",
    ]
    with (output_dir / "review_queue.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(queue)

    pass_count = sum(item["status"] == "pass" for item in results)
    lines = [
        f"# {args.book} vocabulary audio audit",
        "",
        f"- Scope: `{run_label(args)}`",
        f"- Entries: `{len(items)}`",
        f"- Fully passed: `{pass_count}`",
        f"- Entries needing review: `{len(results) - pass_count}`",
        f"- Individual word/sentence comparisons needing review: `{len(queue)}`",
        f"- Newly transcribed clips: `{run['transcribed']}`",
        f"- Reused cached transcripts: `{run['cache_hits']}`",
        f"- Missing audio clips: `{run['missing_audio']}`",
        f"- ASR settings: `{asr_settings(args)}`",
        f"- Thresholds: word `{args.word_pass_threshold}`, sentence `{args.sentence_pass_threshold}`",
        "",
        "ASR differences are review candidates, not automatic corrections.",
        "",
        "## Highest-priority comparisons",
        "",
    ]
    for row in queue[:100]:
        lines.extend(
            [
                f"### #{row['source_index']} · Unit {row['unit']} · {row['headword']} · {row['kind']}",
                "",
                f"- Score/status: `{row['score']}` / `{row['status']}`",
                f"- Expected: {row['expected']}",
                f"- ASR: {row['transcript'] or '(empty)' }",
                f"- Phonetic diff: `{row['phonetic_diff']}`",
                f"- Audio: `{row['audio_clip']}`",
                "",
            ]
        )
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def preflight(args: argparse.Namespace, items: list[AuditItem]) -> int:
    missing: list[dict[str, Any]] = []
    for item in items:
        for kind in selected_kinds(args.only):
            stored = item.word_clip if kind == "word" else item.sentence_clip
            path = resolve_audio_path(stored)
            if path is None or not path.is_file():
                missing.append({"source_index": item.source_index, "kind": kind, "audio_clip": stored})
    print(
        json.dumps(
            {
                "book": args.book,
                "entries": len(items),
                "comparisons": len(items) * len(selected_kinds(args.only)),
                "missing_audio": len(missing),
                "missing_examples": missing[:20],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if missing else 0


def main() -> int:
    args = build_parser().parse_args()
    items = load_items(args.db, args.book, args.unit, args.start_index, args.end_index, args.limit)
    if not items:
        print("No matching canonical main-sentence rows found.", file=sys.stderr)
        return 2
    if args.preflight:
        return preflight(args, items)

    started = time.perf_counter()
    results, counters = audit_items(args, items)
    run = {
        "book": args.book,
        "scope": run_label(args),
        "entries": len(items),
        "only": args.only,
        "backend": args.backend,
        "asr_settings": asr_settings(args),
        "model": args.model,
        "device": args.device,
        "compute_type": args.compute_type,
        "beam_size": args.beam_size,
        "word_pass_threshold": args.word_pass_threshold,
        "sentence_pass_threshold": args.sentence_pass_threshold,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        **counters,
    }
    write_outputs(args, items, results, run)
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
