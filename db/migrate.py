"""
db/migrate.py — Apply pending SQL migrations in db/migrations/.

Each .sql file is named ``NNN_name.sql`` where NNN is a zero-padded integer
version. Files are applied in version order in a single transaction each;
applied versions are recorded in schema_migrations.

Usage:
    python db/migrate.py            # apply all pending
    python db/migrate.py --status   # show applied vs pending
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from connect import DB_PATH, connect  # type: ignore[import-not-found]

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
FILENAME_RE = re.compile(r"^(\d+)_([A-Za-z0-9_\-]+)\.sql$")


def discover() -> list[tuple[int, str, Path]]:
    out = []
    for p in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = FILENAME_RE.match(p.name)
        if not m:
            print(f"WARN: ignoring {p.name} (does not match NNN_name.sql)", file=sys.stderr)
            continue
        out.append((int(m.group(1)), m.group(2), p))
    return out


def ensure_meta_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version    INTEGER PRIMARY KEY,
          name       TEXT NOT NULL,
          applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """
    )


def applied_versions(conn) -> set[int]:
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}


def apply_all(db_path: Path | str | None = None) -> int:
    conn = connect(db_path)
    try:
        ensure_meta_table(conn)
        done = applied_versions(conn)
        migrations = discover()
        applied = 0
        for version, name, path in migrations:
            if version in done:
                continue
            sql = path.read_text(encoding="utf-8")
            print(f"applying {version:03d} {name} … ", end="", flush=True)
            try:
                conn.execute("BEGIN")
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
                    (version, name),
                )
                conn.execute("COMMIT")
                print("ok")
                applied += 1
            except Exception:
                conn.execute("ROLLBACK")
                print("FAILED")
                raise
        if applied == 0:
            print("nothing to apply.")
        return applied
    finally:
        conn.close()


def status(db_path: Path | str | None = None) -> None:
    conn = connect(db_path)
    try:
        ensure_meta_table(conn)
        done = applied_versions(conn)
        for version, name, _path in discover():
            tag = "✓" if version in done else "·"
            print(f"  {tag} {version:03d}  {name}")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="show migration status only")
    ap.add_argument(
        "--db",
        default=None,
        help="override DB path (default: wordService/data/n2vocab.sqlite)",
    )
    args = ap.parse_args()
    print(f"db: {Path(args.db).resolve() if args.db else DB_PATH}")
    if args.status:
        status(args.db)
    else:
        apply_all(args.db)


if __name__ == "__main__":
    main()
