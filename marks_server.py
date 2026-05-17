#!/usr/bin/env python3
"""
marks_server.py — Local runtime server for N2 vocabulary word pages and marks.

Word pages are rendered from output/n2vocab.sqlite at request time. The existing
static generators remain available as snapshot builders, but this is now the
normal entrypoint for studying words.

Endpoints:
    GET  /, /words/index.html
    GET  /words/by_unit/unit_XX.html
    GET  /words/cards/index.html
    GET  /words/cards/unit_XX.html
    GET  /clips/...              → project-root word/sentence audio
    GET  /exercises/...          → existing static exercise pages
    GET  /marks                 → {"version":2,"marks":{ "<entry_id>": {...} }}
    PUT  /marks/<entry_id>      → body {"known":bool,"flagged":bool}
                                  upserts; removes the row if both are false
    OPTIONS *                   → CORS preflight

Storage:  output/n2vocab.sqlite, table `word_marks`
Bind:     127.0.0.1:8766

Run:
    python marks_server.py
"""

import json
import mimetypes
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "wordsAndExerciseInHtml"))
from db import DB_PATH, connect, load_entries  # type: ignore[import-not-found]
import runtime_word_pages  # type: ignore[import-not-found]

HOST = "127.0.0.1"
PORT = 8766
HTML_ROOT = PROJECT_ROOT / "wordsAndExerciseInHtml"
EXERCISES_ROOT = HTML_ROOT / "exercises"
UNIT_RE = re.compile(r"^/words/(cards|by_unit)/unit_(\d{2})\.html$")

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _ensure_db_ready() -> None:
    if not DB_PATH.exists():
        print(
            f"ERROR: {DB_PATH} not found. Run `python db/import_vocabulary.py` first.",
            file=sys.stderr,
        )
        sys.exit(1)
    # Sanity: tables exist
    try:
        with connect(read_only=True, immutable=True) as conn:
            conn.execute("SELECT 1 FROM word_marks LIMIT 1")
    except sqlite3.OperationalError as e:
        print(f"ERROR: DB present but schema is missing: {e}", file=sys.stderr)
        print("Run `python db/migrate.py` to apply migrations.", file=sys.stderr)
        sys.exit(1)


def _fetch_all_marks() -> dict:
    with connect(read_only=True, immutable=True) as conn:
        rows = conn.execute(
            "SELECT entry_id, known, flagged, updated_at FROM word_marks"
        ).fetchall()
        latest = conn.execute(
            "SELECT MAX(updated_at) AS m FROM word_marks"
        ).fetchone()["m"]
    marks = {
        str(r["entry_id"]): {
            "known": bool(r["known"]),
            "flagged": bool(r["flagged"]),
            "updated_at": r["updated_at"],
        }
        for r in rows
    }
    return {"version": 2, "updated_at": latest or _now(), "marks": marks}


def _upsert_mark(entry_id: int, known: bool, flagged: bool) -> None:
    # Normal SQLite writes on this Windows-mounted drive can fail when WAL
    # sidecars are present. Mutating a short-lived local copy and copying the
    # compact DB back keeps mark persistence reliable and easy to reason about.
    with tempfile.TemporaryDirectory(prefix="n2vocab_mark_") as tmp_dir:
        tmp_db = Path(tmp_dir) / DB_PATH.name
        shutil.copy2(DB_PATH, tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = DELETE")
            # Make sure the entry exists so we don't accept orphan marks.
            row = conn.execute("SELECT 1 FROM entries WHERE entry_id = ?", (entry_id,)).fetchone()
            if not row:
                raise KeyError(entry_id)
            if not known and not flagged:
                conn.execute("DELETE FROM word_marks WHERE entry_id = ?", (entry_id,))
            else:
                conn.execute(
                    """
                    INSERT INTO word_marks (entry_id, known, flagged, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(entry_id) DO UPDATE SET
                      known      = excluded.known,
                      flagged    = excluded.flagged,
                      updated_at = excluded.updated_at
                    """,
                    (entry_id, int(known), int(flagged), _now()),
                )
            conn.commit()
        finally:
            conn.close()
        shutil.copy2(tmp_db, DB_PATH)


def _load_entries() -> list[dict]:
    return load_entries(book_code="N2")


def _safe_child(base: Path, rel_path: str) -> Path | None:
    rel = rel_path.lstrip("/")
    candidate = (base / rel).resolve()
    base_resolved = base.resolve()
    if candidate == base_resolved or base_resolved in candidate.parents:
        return candidate
    return None


def _render_word_route(path: str) -> str | None:
    entries = _load_entries()
    if path in {"", "/", "/index.html"}:
        return runtime_word_pages.render_landing(entries)
    if path in {"/words", "/words/", "/words/index.html"}:
        return runtime_word_pages.render_words_index(entries)
    if path in {"/words/cards", "/words/cards/", "/words/cards/index.html"}:
        return runtime_word_pages.render_card_index(entries)

    match = UNIT_RE.match(path)
    if not match:
        return None
    view, unit_s = match.groups()
    unit_num = int(unit_s)
    if view == "cards":
        return runtime_word_pages.render_card_unit(entries, unit_num)
    return runtime_word_pages.render_long_unit(entries, unit_num)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

    def _send(self, code: int, body: bytes = b"", ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        if body:
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body and not getattr(self, "_head_only", False):
            self.wfile.write(body)

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _send_html(self, html: str):
        self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")

    def _send_json(self, data: dict):
        self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_static_file(self, file_path: Path) -> bool:
        if not file_path.exists() or not file_path.is_file():
            return False
        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self._send(200, file_path.read_bytes(), ctype)
        return True

    def do_OPTIONS(self):
        self._send(204)

    def do_HEAD(self):
        self._head_only = True
        try:
            self.do_GET()
        finally:
            self._head_only = False

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path.rstrip("/") == "/marks":
            with _lock:
                data = _fetch_all_marks()
            self._send_json(data)
            return

        if path in {"/words/cards"}:
            self._redirect(path.rstrip("/") + "/index.html")
            return

        if path.startswith("/clips/"):
            file_path = _safe_child(PROJECT_ROOT, path)
            if file_path and self._send_static_file(file_path):
                return

        if path.startswith("/exercises/"):
            rel = path[len("/exercises/"):] or "index.html"
            file_path = _safe_child(EXERCISES_ROOT, rel)
            if file_path and self._send_static_file(file_path):
                return

        try:
            with _lock:
                html = _render_word_route(path)
        except sqlite3.Error as e:
            self._send(500, json.dumps({"error": str(e)}).encode("utf-8"))
            return
        if html is not None:
            self._send_html(html)
            return

        self._send(404, b'{"error":"not found"}')

    def do_PUT(self):
        path = unquote(urlparse(self.path).path).rstrip("/")
        prefix = "/marks/"
        if not path.startswith(prefix):
            self._send(404, b'{"error":"not found"}')
            return
        entry_id_s = path[len(prefix):]
        if not entry_id_s.isdigit():
            self._send(400, b'{"error":"entry id must be integer"}')
            return
        entry_id = int(entry_id_s)

        length = int(self.headers.get("Content-Length", "0") or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, b'{"error":"invalid JSON"}')
            return

        known = bool(payload.get("known", False))
        flagged = bool(payload.get("flagged", False))

        try:
            with _lock:
                _upsert_mark(entry_id, known, flagged)
        except KeyError:
            self._send(404, b'{"error":"unknown entry_id"}')
            return
        self._send(204)


def main():
    _ensure_db_ready()
    print(f"marks_server.py — listening on http://{HOST}:{PORT}")
    print(f"  db: {DB_PATH}")
    print("  Ctrl-C to stop.")
    with ThreadingHTTPServer((HOST, PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nbye.")


if __name__ == "__main__":
    main()
