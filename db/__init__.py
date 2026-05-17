"""db — SQLite access for N2 vocabulary project."""
from .connect import DB_PATH, connect, load_entries

__all__ = ["DB_PATH", "connect", "load_entries"]
