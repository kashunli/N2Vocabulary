# N2 高频词汇550 Example Audio

Generated missing example/sentence audio for the new `N2_HF_550` book through
the Rust wordService API.

## What ran

- Dry run:
  `python wordService/tools/generate_all_audio.py --book N2_HF_550 --kind example --base-url http://127.0.0.1:8797 --dry-run`
- Batch run:
  `python wordService/tools/generate_all_audio.py --book N2_HF_550 --kind example --base-url http://127.0.0.1:8797 --progress-every 25 --timeout 240 --sleep 0.05`
- One follow-up endpoint call filled the final missing row:
  `POST /api/entries/8707/examples/3/audio?book=N2_HF_550`

## Results

- Initial missing example-audio tasks: 594
- Batch result: 594 ok, 0 failed
- Final coverage for `N2_HF_550` visible example rows:
  - `total_examples = 1663`
  - `missing_audio_paths = 0`
  - `missing_audio_files = 0`
- SQLite checks after generation:
  - `integrity_check = ok`
  - `foreign_key_check_rows = 0`

## Artifacts

- Run manifest/events/summary:
  `wordService/audio_generation_runs/20260630_213520/`
