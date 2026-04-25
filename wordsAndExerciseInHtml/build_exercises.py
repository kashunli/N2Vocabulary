#!/usr/bin/env python3
"""
build_exercises.py — Rebuild exercise HTML pages for N2 vocabulary.

All scripts are self-contained under wordsAndExerciseInHtml/scripts/.
Only external dependency: N2Vocabulary/json/ (OCR source pages).

Two-step pipeline:
  Step 1 (Python)  — scripts/convert_n2_exercises.py
                     Reads N2Vocabulary/json/page_*.json
                     Writes enriched JSON → wordsAndExerciseInHtml/exercise_json/n2/

  Step 2 (Node.js) — scripts/json_to_test.js generate-folder
                     Reads exercise_json/n2/
                     Writes HTML → wordsAndExerciseInHtml/exercises/n2/

Run from project root OR from wordsAndExerciseInHtml/:
    python wordsAndExerciseInHtml/build_exercises.py

Options:
    --json-only     Run only Step 1 (skip HTML generation)
    --html-only     Run only Step 2 (use existing JSON)
    --debug-ak      Pass --debug-ak to convert_n2_exercises.py (prints answer key sections)
"""

import subprocess
import sys
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent.resolve()   # wordsAndExerciseInHtml/
SCRIPTS     = SCRIPT_DIR / "scripts"            # local scripts/
JSON_DATA   = SCRIPT_DIR / "exercise_json" / "n2"
HTML_OUT    = SCRIPT_DIR / "exercises" / "n2"
CONVERT_PY  = SCRIPTS / "convert_n2_exercises.py"
JS_SCRIPT   = SCRIPTS / "json_to_test.js"


def run(cmd, cwd=None):
    cmd = [str(c) for c in cmd]
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if result.returncode != 0:
        print(f"\nERROR: command exited with code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)


def step1_json(extra_args=()):
    print("=== Step 1: Generate enriched JSON from OCR pages ===")
    if not CONVERT_PY.exists():
        print(f"ERROR: {CONVERT_PY} not found", file=sys.stderr)
        sys.exit(1)
    run([sys.executable, "-u", CONVERT_PY, *extra_args])


def step2_html():
    print("=== Step 2: Generate exercise HTML from JSON ===")
    if not JS_SCRIPT.exists():
        print(f"ERROR: {JS_SCRIPT} not found", file=sys.stderr)
        sys.exit(1)
    if not JSON_DATA.exists():
        print(f"ERROR: JSON data folder missing: {JSON_DATA}", file=sys.stderr)
        print("Run Step 1 first (or omit --html-only).", file=sys.stderr)
        sys.exit(1)
    HTML_OUT.mkdir(parents=True, exist_ok=True)
    run(
        ["node", JS_SCRIPT,
         "generate-folder", str(JSON_DATA),
         "--out-root", str(HTML_OUT),
         "--build-index"],
    )
    print(f"\nHTML written to {HTML_OUT}")


def main():
    args = sys.argv[1:]
    json_only  = "--json-only"  in args
    html_only  = "--html-only"  in args
    debug_ak   = "--debug-ak"   in args

    if json_only and html_only:
        print("ERROR: --json-only and --html-only are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    extra_py = ["--debug-ak"] if debug_ak else []

    if not html_only:
        step1_json(extra_py)
    if not json_only:
        step2_html()


if __name__ == "__main__":
    main()
