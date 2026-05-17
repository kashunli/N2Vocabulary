#!/usr/bin/env python3
"""
marks_server.py — Tiny local server that persists per-word "known" / "flagged"
marks for the N2 vocabulary card-grid pages. Now backed by SQLite.

Endpoints (CORS-open so HTML opened via file:// can reach it):
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
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
from db import DB_PATH, connect  # type: ignore[import-not-found]

HOST = "127.0.0.1"
PORT = 8766

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
        with connect() as conn:
            conn.execute("SELECT 1 FROM word_marks LIMIT 1")
    except sqlite3.OperationalError as e:
        print(f"ERROR: DB present but schema is missing: {e}", file=sys.stderr)
        print("Run `python db/migrate.py` to apply migrations.", file=sys.stderr)
        sys.exit(1)


def _fetch_all_marks() -> dict:
    with connect() as conn:
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
    with connect() as conn:
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
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        if self.path.rstrip("/") == "/marks":
            with _lock:
                data = _fetch_all_marks()
            self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"))
            return
        self._send(404, b'{"error":"not found"}')

    def do_PUT(self):
        path = self.path.rstrip("/")
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
