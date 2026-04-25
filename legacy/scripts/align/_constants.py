"""Project-wide path constants for the align package.

Centralised here so every submodule imports ROOT from one place rather than
each recomputing `Path(__file__).resolve().parents[N]` with a potentially
wrong depth.
"""
from pathlib import Path

# All files in this package live at parse/scripts/align/*, so parents[3] is
# the repository root (N2Vocabulary/).
ROOT = Path(__file__).resolve().parents[3]

DB_PATH = ROOT / "output" / "vocabulary_db.json"
REVIEW_PATH = ROOT / "output" / "review_assigned.json"
