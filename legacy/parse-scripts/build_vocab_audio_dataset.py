#!/usr/bin/env python3
"""Thin launcher — delegates to the pipeline package.

Run from the project root:
    python -u parse/scripts/build_vocab_audio_dataset.py [options]

Equivalent package invocation:
    python -u -m pipeline [options]

See parse/scripts/pipeline/__main__.py for the full option reference,
or run with --help.

The original monolithic script is preserved at:
    parse/scripts/build_vocab_audio_dataset.py.bak
"""
import sys
from pathlib import Path

# Ensure the scripts directory is on the path so 'pipeline' is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
