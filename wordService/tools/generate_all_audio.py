"""Generate missing word and example audio through the Rust wordService API.

This is intentionally a small workflow script, not a second TTS implementation.
The Rust service remains the authority for TTS queueing, path generation, file
writes, and SQLite updates; this script only decides which endpoints to call and
records resumable progress.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class AudioTask:
    kind: str
    book_code: str
    entry_id: int
    position: int | None
    label: str
    existing_clip: str | None

    @property
    def key(self) -> str:
        if self.kind == "word":
            return f"word:{self.book_code}:{self.entry_id}"
        return f"example:{self.book_code}:{self.entry_id}:{self.position}"

    @property
    def endpoint(self) -> str:
        if self.kind == "word":
            return f"/api/entries/{self.entry_id}/audio?book={quote_query(self.book_code)}"
        return (
            f"/api/entries/{self.entry_id}/examples/{self.position}/audio"
            f"?book={quote_query(self.book_code)}"
        )


def quote_query(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate missing word/example audio via the local Rust wordService API."
    )
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--db", type=Path, default=root / "wordService" / "data" / "n2vocab.sqlite")
    parser.add_argument("--clips-root", type=Path, default=root / "clips")
    parser.add_argument("--base-url", default="http://127.0.0.1:8767")
    parser.add_argument("--book", action="append", help="Book code to include; repeatable. Defaults to all books.")
    parser.add_argument("--include-existing", action="store_true", help="Call endpoints even when a clip path currently resolves to a file.")
    parser.add_argument("--kind", choices=["all", "word", "example"], default="all")
    parser.add_argument("--limit", type=int, help="Maximum number of tasks to run after filtering/resume.")
    parser.add_argument("--dry-run", action="store_true", help="Print counts and write no audio.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Optional seconds to pause between requests.")
    parser.add_argument("--timeout", type=float, default=180.0, help="HTTP timeout per TTS request in seconds.")
    parser.add_argument("--progress-every", type=int, default=1, help="Print every Nth task to the terminal; JSONL still records every task.")
    parser.add_argument("--resume-log", type=Path, help="Existing JSONL event log whose ok task keys should be skipped.")
    parser.add_argument("--run-dir", type=Path, help="Directory for manifest.json and events.jsonl.")
    parser.add_argument("--stop-on-error", action="store_true", help="Stop at the first failed audio task.")
    return parser.parse_args()


def clip_exists(clips_root: Path, stored_clip: str | None) -> bool:
    if not stored_clip:
        return False
    normalized = stored_clip.replace("\\", "/").lstrip("/")
    if normalized.startswith("output/"):
        normalized = normalized[len("output/") :]
    if not normalized.startswith("clips/"):
        return False
    return (clips_root.parent / normalized).is_file()


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def list_books(conn: sqlite3.Connection, selected: list[str] | None) -> list[str]:
    if selected:
        return selected
    return [row["code"] for row in conn.execute("SELECT code FROM books ORDER BY code")]


def iter_tasks(
    conn: sqlite3.Connection,
    clips_root: Path,
    books: Iterable[str],
    kind: str,
    include_existing: bool,
) -> list[AudioTask]:
    selected_books = list(books)
    placeholders = ",".join("?" for _ in selected_books)
    tasks: list[AudioTask] = []

    if kind in {"all", "word"}:
        for row in conn.execute(
            f"""
            SELECT book_code, entry_id, source_index, kanji, reading, word_clip
            FROM entries
            WHERE book_code IN ({placeholders})
              AND (
                trim(coalesce(kanji, '')) <> ''
                OR trim(coalesce(reading, '')) <> ''
              )
            ORDER BY book_code, unit_number, position, source_index
            """,
            selected_books,
        ):
            if include_existing or not clip_exists(clips_root, row["word_clip"]):
                tasks.append(
                    AudioTask(
                        kind="word",
                        book_code=row["book_code"],
                        entry_id=int(row["entry_id"]),
                        position=None,
                        label=f"{row['book_code']} #{row['source_index']} {row['kanji'] or row['reading']}",
                        existing_clip=row["word_clip"],
                    )
                )

    if kind in {"all", "example"}:
        for row in conn.execute(
            f"""
            SELECT e.book_code, e.entry_id, ex.position, e.source_index, v.kanji,
                   ex.text, ex.audio_clip
            FROM item_examples ex
            JOIN book_entries e ON e.item_id = ex.item_id
            JOIN vocabulary_items v ON v.item_id = e.item_id
            WHERE e.book_code IN ({placeholders}) AND trim(coalesce(ex.text, '')) <> ''
            ORDER BY e.book_code, e.unit_number, e.position, e.source_index, ex.position
            """,
            selected_books,
        ):
            if include_existing or not clip_exists(clips_root, row["audio_clip"]):
                text_preview = row["text"].replace("\n", " ")[:40]
                tasks.append(
                    AudioTask(
                        kind="example",
                        book_code=row["book_code"],
                        entry_id=int(row["entry_id"]),
                        position=int(row["position"]),
                        label=(
                            f"{row['book_code']} #{row['source_index']} {row['kanji']} "
                            f"example {row['position']}: {text_preview}"
                        ),
                        existing_clip=row["audio_clip"],
                    )
                )
    return tasks


def read_completed_keys(path: Path | None) -> set[str]:
    if not path or not path.exists():
        return set()
    completed: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("status") == "ok" and event.get("key"):
                completed.add(str(event["key"]))
    return completed


def post_json(base_url: str, endpoint: str, timeout: float) -> dict:
    request = urllib.request.Request(
        base_url.rstrip("/") + endpoint,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def write_event(handle, event: dict) -> None:
    handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    handle.flush()


def main() -> int:
    args = parse_args()
    conn = connect(args.db)
    books = list_books(conn, args.book)
    tasks = iter_tasks(conn, args.clips_root, books, args.kind, args.include_existing)
    completed = read_completed_keys(args.resume_log)
    if completed:
        tasks = [task for task in tasks if task.key not in completed]
    if args.limit is not None:
        tasks = tasks[: args.limit]

    now = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.run_dir or (args.db.parent.parent / "audio_generation_runs" / now)
    manifest = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "db": str(args.db),
        "clips_root": str(args.clips_root),
        "base_url": args.base_url,
        "books": books,
        "kind": args.kind,
        "include_existing": args.include_existing,
        "resume_log": str(args.resume_log) if args.resume_log else None,
        "task_count": len(tasks),
        "dry_run": args.dry_run,
    }

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if args.dry_run:
        by_kind: dict[str, int] = {}
        by_book: dict[str, int] = {}
        for task in tasks:
            by_kind[task.kind] = by_kind.get(task.kind, 0) + 1
            by_book[task.book_code] = by_book.get(task.book_code, 0) + 1
        print("by_kind", json.dumps(by_kind, ensure_ascii=False, sort_keys=True))
        print("by_book", json.dumps(by_book, ensure_ascii=False, sort_keys=True))
        for task in tasks[:20]:
            print(task.key, task.label)
        return 0

    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    events_path = run_dir / "events.jsonl"
    ok = 0
    failed = 0
    with events_path.open("a", encoding="utf-8") as events:
        for index, task in enumerate(tasks, start=1):
            started = time.time()
            event = {
                "index": index,
                "total": len(tasks),
                "key": task.key,
                "kind": task.kind,
                "book_code": task.book_code,
                "entry_id": task.entry_id,
                "position": task.position,
                "label": task.label,
                "endpoint": task.endpoint,
                "status": "started",
                "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            if args.progress_every <= 1 or index == 1 or index == len(tasks) or index % args.progress_every == 0:
                print(f"[{index}/{len(tasks)}] {task.key} {task.label}")
            write_event(events, event)
            try:
                payload = post_json(args.base_url, task.endpoint, args.timeout)
                ok += 1
                write_event(events, {
                    **event,
                    "status": "ok",
                    "duration_s": round(time.time() - started, 3),
                    "generated": payload.get("generated"),
                    "audio_url": payload.get("audio_url"),
                })
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                failed += 1
                error_text = getattr(error, "reason", None) or str(error)
                if isinstance(error, urllib.error.HTTPError):
                    try:
                        error_text = error.read().decode("utf-8")
                    except Exception:
                        error_text = str(error)
                write_event(events, {
                    **event,
                    "status": "error",
                    "duration_s": round(time.time() - started, 3),
                    "error": str(error_text),
                })
                print(f"ERROR {task.key}: {error_text}", file=sys.stderr)
                if args.stop_on_error:
                    break
            if args.sleep > 0:
                time.sleep(args.sleep)

    summary = {"ok": ok, "failed": failed, "events": str(events_path)}
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
