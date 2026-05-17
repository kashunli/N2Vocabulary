from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
STATIC_DIR = PACKAGE_DIR / "static"
DEFAULT_DB_PATH = PROJECT_ROOT / "output" / "n2vocab.sqlite"
DEFAULT_CLIPS_DIR = PROJECT_ROOT / "clips"

STATE_VALUES = {"all", "known", "flagged", "unmarked"}


@dataclass(slots=True)
class AppConfig:
    """Runtime paths kept explicit so tests and future agents can override them."""

    db_path: Path = DEFAULT_DB_PATH
    static_dir: Path = STATIC_DIR
    clips_dir: Path = DEFAULT_CLIPS_DIR
    host: str = "127.0.0.1"
    port: int = 8767
    book_code: str = "N2"


def _dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {column[0]: row[index] for index, column in enumerate(cursor.description)}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _short_title(header: str) -> str:
    title = re.sub(r"^Unit\s+\d+\s+", "", header or "").strip()
    title = re.sub(r"\s*&\s*Column.*$", "", title).strip()
    return title or header or ""


def _normalize_clip_path(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.replace("\\", "/").lstrip("/")
    if normalized.startswith("output/clips/"):
        normalized = normalized[len("output/") :]
    return normalized if normalized.startswith("clips/") else None


class WordRepository:
    """Small SQLite boundary for the card service.

    The DB schema stores the main sentence as entry_examples.position = 0.
    Older entry columns are still read as fallbacks because this repository is
    mid-migration and future agents need the service to tolerate both shapes.
    """

    def __init__(self, db_path: Path, clips_dir: Path, book_code: str = "N2"):
        self.db_path = Path(db_path)
        self.clips_dir = Path(clips_dir)
        self.book_code = book_code
        self._write_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = _dict_factory
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def open(self) -> Any:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    def ensure_ready(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        with self.open() as conn:
            conn.execute("SELECT 1 FROM entries LIMIT 1")
            conn.execute("SELECT 1 FROM word_marks LIMIT 1")

    def get_marks(self) -> dict[str, Any]:
        with self.open() as conn:
            rows = conn.execute(
                "SELECT entry_id, known, flagged, updated_at FROM word_marks"
            ).fetchall()
            latest = conn.execute(
                "SELECT MAX(updated_at) AS updated_at FROM word_marks"
            ).fetchone()["updated_at"]
        return {
            "version": 2,
            "updated_at": latest or _now(),
            "marks": {
                str(row["entry_id"]): {
                    "known": bool(row["known"]),
                    "flagged": bool(row["flagged"]),
                    "updated_at": row["updated_at"],
                }
                for row in rows
            },
        }

    def get_summary(self) -> dict[str, int]:
        with self.open() as conn:
            row = conn.execute(
                """
                SELECT
                  COUNT(*) AS entries,
                  COUNT(DISTINCT unit_number) AS units,
                  SUM(CASE WHEN COALESCE(m.known, 0) = 1 THEN 1 ELSE 0 END) AS known,
                  SUM(CASE WHEN COALESCE(m.flagged, 0) = 1 THEN 1 ELSE 0 END) AS flagged
                FROM entries e
                LEFT JOIN word_marks m ON m.entry_id = e.entry_id
                WHERE e.book_code = ?
                """,
                [self.book_code],
            ).fetchone()
        entries = int(row["entries"] or 0)
        known = int(row["known"] or 0)
        flagged = int(row["flagged"] or 0)
        marked_any = self._count_marked_any()
        return {
            "entries": entries,
            "units": int(row["units"] or 0),
            "known": known,
            "flagged": flagged,
            "unmarked": max(entries - marked_any, 0),
        }

    def _count_marked_any(self) -> int:
        with self.open() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM entries e
                JOIN word_marks m ON m.entry_id = e.entry_id
                WHERE e.book_code = ? AND (m.known = 1 OR m.flagged = 1)
                """,
                [self.book_code],
            ).fetchone()
        return int(row["count"] or 0)

    def list_units(self) -> list[dict[str, Any]]:
        with self.open() as conn:
            rows = conn.execute(
                """
                SELECT
                  u.number,
                  u.header,
                  u.title,
                  COUNT(e.entry_id) AS entry_count,
                  SUM(CASE WHEN COALESCE(m.known, 0) = 1 THEN 1 ELSE 0 END) AS known,
                  SUM(CASE WHEN COALESCE(m.flagged, 0) = 1 THEN 1 ELSE 0 END) AS flagged,
                  SUM(CASE WHEN m.entry_id IS NULL THEN 1 ELSE 0 END) AS unmarked
                FROM units u
                JOIN entries e
                  ON e.book_code = u.book_code AND e.unit_number = u.number
                LEFT JOIN word_marks m ON m.entry_id = e.entry_id
                WHERE u.book_code = ?
                GROUP BY u.number, u.header, u.title
                ORDER BY u.number
                """,
                [self.book_code],
            ).fetchall()
        return [
            {
                "number": int(row["number"]),
                "header": row["header"],
                "title": _short_title(row["header"]) or row["title"],
                "entry_count": int(row["entry_count"] or 0),
                "known": int(row["known"] or 0),
                "flagged": int(row["flagged"] or 0),
                "unmarked": int(row["unmarked"] or 0),
            }
            for row in rows
        ]

    def list_entries(
        self,
        *,
        unit: int | None = None,
        state: str = "all",
        search: str = "",
    ) -> dict[str, Any]:
        if state not in STATE_VALUES:
            raise ValueError(f"state must be one of: {', '.join(sorted(STATE_VALUES))}")

        clauses = ["e.book_code = ?"]
        params: list[Any] = [self.book_code]
        if unit is not None:
            clauses.append("e.unit_number = ?")
            params.append(unit)
        if state == "known":
            clauses.append("COALESCE(m.known, 0) = 1")
        elif state == "flagged":
            clauses.append("COALESCE(m.flagged, 0) = 1")
        elif state == "unmarked":
            clauses.append("m.entry_id IS NULL")
        if search:
            like_term = f"%{search.strip()}%"
            clauses.append(
                """
                (
                  COALESCE(e.kanji, '') LIKE ?
                  OR COALESCE(e.reading, '') LIKE ?
                  OR COALESCE(e.headword_text, '') LIKE ?
                  OR COALESCE(e.meaning_en, '') LIKE ?
                  OR COALESCE(e.meaning_zh, '') LIKE ?
                  OR COALESCE(ex.text, '') LIKE ?
                  OR COALESCE(ex.translation_en, '') LIKE ?
                  OR COALESCE(ex.translation_zh, '') LIKE ?
                )
                """
            )
            params.extend([like_term] * 8)

        where = " AND ".join(clauses)
        with self.open() as conn:
            rows = conn.execute(
                f"""
                SELECT DISTINCT
                  e.entry_id, e.uuid, e.book_code, e.source_index, e.unit_number,
                  u.header AS unit_header, e.kanji, e.reading, e.headword_text,
                  e.verb_pattern, e.meaning_en, e.meaning_zh, e.sentence,
                  e.explanation_md, e.word_clip, e.sentence_clip,
                  m.known, m.flagged, m.updated_at AS mark_updated_at
                FROM entries e
                JOIN units u
                  ON u.book_code = e.book_code AND u.number = e.unit_number
                LEFT JOIN word_marks m ON m.entry_id = e.entry_id
                LEFT JOIN entry_examples ex ON ex.entry_id = e.entry_id
                WHERE {where}
                ORDER BY e.unit_number, e.position, e.source_index
                """,
                params,
            ).fetchall()
            entry_ids = [int(row["entry_id"]) for row in rows]
            examples = self._load_examples(conn, entry_ids)

        items = [self._serialize_entry(row, examples.get(int(row["entry_id"]), [])) for row in rows]
        return {"items": items, "total": len(items)}

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        with self.open() as conn:
            row = conn.execute(
                """
                SELECT
                  e.entry_id, e.uuid, e.book_code, e.source_index, e.unit_number,
                  u.header AS unit_header, e.kanji, e.reading, e.headword_text,
                  e.verb_pattern, e.meaning_en, e.meaning_zh, e.sentence,
                  e.explanation_md, e.word_clip, e.sentence_clip,
                  m.known, m.flagged, m.updated_at AS mark_updated_at
                FROM entries e
                JOIN units u
                  ON u.book_code = e.book_code AND u.number = e.unit_number
                LEFT JOIN word_marks m ON m.entry_id = e.entry_id
                WHERE e.book_code = ? AND e.entry_id = ?
                """,
                [self.book_code, entry_id],
            ).fetchone()
            if not row:
                return None
            examples = self._load_examples(conn, [entry_id])
        return self._serialize_entry(row, examples.get(entry_id, []), detail=True)

    def _load_examples(
        self, conn: sqlite3.Connection, entry_ids: list[int]
    ) -> dict[int, list[dict[str, Any]]]:
        if not entry_ids:
            return {}
        placeholders = ",".join("?" for _ in entry_ids)
        rows = conn.execute(
            f"""
            SELECT entry_id, position, text, translation_en, translation_zh,
                   explanation_md, audio_clip
            FROM entry_examples
            WHERE entry_id IN ({placeholders})
            ORDER BY entry_id, position
            """,
            entry_ids,
        ).fetchall()
        by_entry: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            by_entry.setdefault(int(row["entry_id"]), []).append(
                {
                    "position": int(row["position"]),
                    "text": row["text"] or "",
                    "translation_en": row["translation_en"] or "",
                    "translation_zh": row["translation_zh"] or "",
                    "explanation_md": row["explanation_md"] or "",
                    "audio_url": self.audio_url(row["audio_clip"]),
                }
            )
        return by_entry

    def _serialize_entry(
        self,
        row: dict[str, Any],
        examples: list[dict[str, Any]],
        *,
        detail: bool = False,
    ) -> dict[str, Any]:
        main_example = next((item for item in examples if item["position"] == 0), None)
        sentence = (main_example or {}).get("text") or row["sentence"] or ""
        sentence_audio = (main_example or {}).get("audio_url") or self.audio_url(row["sentence_clip"])
        payload = {
            "entry_id": int(row["entry_id"]),
            "source_index": int(row["source_index"]),
            "uuid": row["uuid"],
            "book_code": row["book_code"],
            "unit": {
                "number": int(row["unit_number"]),
                "header": row["unit_header"],
                "title": _short_title(row["unit_header"]),
            },
            "kanji": row["headword_text"] or row["kanji"] or "",
            "reading": row["reading"] or "",
            "verb_pattern": row["verb_pattern"] or "",
            "meaning_en": row["meaning_en"] or "",
            "meaning_zh": row["meaning_zh"] or "",
            "sentence": sentence,
            "sentence_translation_en": (main_example or {}).get("translation_en", ""),
            "sentence_translation_zh": (main_example or {}).get("translation_zh", ""),
            "word_audio_url": self.audio_url(row["word_clip"]),
            "sentence_audio_url": sentence_audio,
            "mark": {
                "known": bool(row["known"]),
                "flagged": bool(row["flagged"]),
                "updated_at": row["mark_updated_at"],
            },
        }
        if detail:
            payload["examples"] = examples
            payload["explanation_md"] = (
                (main_example or {}).get("explanation_md")
                or row["explanation_md"]
                or ""
            )
        return payload

    def audio_url(self, clip_path: str | None) -> str | None:
        normalized = _normalize_clip_path(clip_path)
        if not normalized:
            return None
        path = (self.clips_dir.parent / normalized).resolve()
        clips_root = self.clips_dir.resolve()
        if path == clips_root or clips_root not in path.parents:
            return None
        return f"/audio/{normalized}"

    def resolve_audio_path(self, request_path: str) -> Path | None:
        rel = unquote(request_path).replace("\\", "/").lstrip("/")
        if not rel.startswith("clips/"):
            return None
        candidate = (self.clips_dir.parent / rel).resolve()
        clips_root = self.clips_dir.resolve()
        if candidate == clips_root or clips_root not in candidate.parents:
            return None
        return candidate

    def set_mark(self, entry_id: int, known: bool, flagged: bool) -> None:
        # The project lives on a Windows-mounted drive where stale WAL sidecars
        # have caused direct writes to be fragile. Copying the compact DB, then
        # copying it back after commit, matches the proven marks_server.py path.
        with self._write_lock:
            with tempfile.TemporaryDirectory(prefix="n2_word_mark_") as tmp_dir:
                tmp_db = Path(tmp_dir) / self.db_path.name
                shutil.copy2(self.db_path, tmp_db)
                conn = sqlite3.connect(str(tmp_db))
                conn.row_factory = _dict_factory
                try:
                    conn.execute("PRAGMA foreign_keys = ON")
                    conn.execute("PRAGMA journal_mode = DELETE")
                    row = conn.execute(
                        "SELECT 1 FROM entries WHERE book_code = ? AND entry_id = ?",
                        [self.book_code, entry_id],
                    ).fetchone()
                    if not row:
                        raise KeyError(entry_id)
                    if not known and not flagged:
                        conn.execute("DELETE FROM word_marks WHERE entry_id = ?", [entry_id])
                    else:
                        conn.execute(
                            """
                            INSERT INTO word_marks(entry_id, known, flagged, updated_at)
                            VALUES(?, ?, ?, ?)
                            ON CONFLICT(entry_id) DO UPDATE SET
                              known = excluded.known,
                              flagged = excluded.flagged,
                              updated_at = excluded.updated_at
                            """,
                            [entry_id, int(known), int(flagged), _now()],
                        )
                    conn.commit()
                finally:
                    conn.close()
                shutil.copy2(tmp_db, self.db_path)


def _json_response(handler: BaseHTTPRequestHandler, payload: Any, status: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    if handler.command != "HEAD":
        handler.wfile.write(data)


def _send_file(handler: BaseHTTPRequestHandler, path: Path, content_type: str | None = None) -> None:
    if not path.exists() or not path.is_file():
        handler.send_error(HTTPStatus.NOT_FOUND, "Not found")
        return
    ctype = content_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(path.stat().st_size))
    handler.end_headers()
    if handler.command != "HEAD":
        with path.open("rb") as source:
            shutil.copyfileobj(source, handler.wfile)


def _parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


def make_handler(config: AppConfig) -> type[BaseHTTPRequestHandler]:
    repository = WordRepository(config.db_path, config.clips_dir, config.book_code)

    class WordServiceHandler(BaseHTTPRequestHandler):
        server_version = "N2WordService/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_HEAD(self) -> None:  # noqa: N802
            self.do_GET()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            params = {key: values[-1] for key, values in parse_qs(parsed.query).items()}

            try:
                if path in {"/", "/index.html"}:
                    _send_file(self, config.static_dir / "index.html", "text/html; charset=utf-8")
                    return
                if path in {"/styles.css", "/app.js"}:
                    _send_file(self, config.static_dir / path.lstrip("/"))
                    return

                if path == "/api/summary":
                    _json_response(self, repository.get_summary())
                    return
                if path == "/api/units":
                    _json_response(self, {"items": repository.list_units()})
                    return
                if path == "/api/marks":
                    _json_response(self, repository.get_marks())
                    return
                if path == "/api/entries":
                    unit = int(params["unit"]) if params.get("unit") else None
                    _json_response(
                        self,
                        repository.list_entries(
                            unit=unit,
                            state=params.get("state", "all"),
                            search=params.get("search", ""),
                        ),
                    )
                    return
                if path.startswith("/api/entries/"):
                    try:
                        entry_id = int(path.rsplit("/", 1)[-1])
                    except ValueError:
                        self.send_error(HTTPStatus.BAD_REQUEST, "Invalid entry id")
                        return
                    entry = repository.get_entry(entry_id)
                    if entry is None:
                        self.send_error(HTTPStatus.NOT_FOUND, "Entry not found")
                        return
                    _json_response(self, entry)
                    return
                if path.startswith("/audio/"):
                    file_path = repository.resolve_audio_path(path[len("/audio/") :])
                    if file_path is None:
                        self.send_error(HTTPStatus.NOT_FOUND, "Audio not found")
                        return
                    _send_file(self, file_path, "audio/mpeg")
                    return
            except ValueError as error:
                _json_response(self, {"error": str(error)}, status=400)
                return
            except sqlite3.Error as error:
                _json_response(self, {"error": str(error)}, status=500)
                return

            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_PUT(self) -> None:  # noqa: N802
            path = unquote(urlparse(self.path).path).rstrip("/")
            if not path.startswith("/api/marks/"):
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            try:
                entry_id = int(path.rsplit("/", 1)[-1])
            except ValueError:
                _json_response(self, {"error": "entry id must be integer"}, status=400)
                return
            try:
                body = _parse_json_body(self)
            except json.JSONDecodeError:
                _json_response(self, {"error": "invalid JSON"}, status=400)
                return
            try:
                repository.set_mark(
                    entry_id,
                    known=bool(body.get("known", False)),
                    flagged=bool(body.get("flagged", False)),
                )
            except KeyError:
                _json_response(self, {"error": "unknown entry_id"}, status=404)
                return
            _json_response(self, {"ok": True})

    return WordServiceHandler


def run_server(config: AppConfig | None = None) -> None:
    config = config or AppConfig()
    repository = WordRepository(config.db_path, config.clips_dir, config.book_code)
    repository.ensure_ready()
    handler = make_handler(config)
    with ThreadingHTTPServer((config.host, config.port), handler) as server:
        print(f"N2 wordService running at http://{config.host}:{config.port}")
        print(f"  db: {config.db_path}")
        print(f"  clips: {config.clips_dir}")
        server.serve_forever()


def main() -> None:
    config = AppConfig(
        db_path=Path(os.environ.get("N2_WORD_SERVICE_DB", DEFAULT_DB_PATH)),
        static_dir=Path(os.environ.get("N2_WORD_SERVICE_STATIC", STATIC_DIR)),
        clips_dir=Path(os.environ.get("N2_WORD_SERVICE_CLIPS", DEFAULT_CLIPS_DIR)),
        host=os.environ.get("N2_WORD_SERVICE_HOST", "127.0.0.1"),
        port=int(os.environ.get("N2_WORD_SERVICE_PORT", "8767")),
        book_code=os.environ.get("N2_WORD_SERVICE_BOOK", "N2"),
    )
    run_server(config)


if __name__ == "__main__":
    main()
