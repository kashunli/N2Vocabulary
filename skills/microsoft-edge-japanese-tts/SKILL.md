---
name: microsoft-edge-japanese-tts
description: Generate Japanese sentence MP3 audio with Microsoft Edge TTS / edge-tts, especially for JLPT example sentences, Anki sentence audio, vocabulary listening clips, or batch voice generation that should use the free Microsoft neural voices without an API key.
---

# Microsoft Edge Japanese TTS

Use this skill when Japanese example sentences need generated MP3 audio and the user wants the free Microsoft/Edge TTS route rather than recorded source audio or a paid API.

## Default Choice

Prefer the bundled script:

```powershell
python .\skills\microsoft-edge-japanese-tts\scripts\generate_edge_tts.py --text "これはテストです。" --out output\tts_test.mp3
```

Default synthesis settings are chosen for language-learning sentence audio:

- voice: `ja-JP-NanamiNeural`
- rate: `-10%`
- output format: `.mp3`
- dependency: Python package `edge-tts`
- API key: none

If `edge-tts` is missing, install it in the active Python environment:

```powershell
python -m pip install edge-tts
```

## Batch Inputs

For one sentence:

```powershell
python .\skills\microsoft-edge-japanese-tts\scripts\generate_edge_tts.py --text "日本語の例文です。" --out output\sentences\sample.mp3
```

For a `.txt` file, put one sentence per line. Optional tab-separated IDs are supported:

```text
u02_101_0	一般に、年を取った人はあっさりした味を好む。
u02_101_1	油っぽい料理は胃にもたれる。
```

Run:

```powershell
python .\skills\microsoft-edge-japanese-tts\scripts\generate_edge_tts.py --input work\sentences.txt --output-dir output\sentence_tts --prefix ex_
```

For `.json` or `.jsonl`, the script accepts strings or objects. For objects, it looks for sentence text in `sentence`, `text`, `ja`, or `japanese` unless `--text-field` is provided. It uses `id`, `entry_id`, `index`, or `source_index` for stable filenames when present.

## Output Contract

The script writes:

- one `.mp3` per input sentence
- a manifest JSON file, defaulting to `_edge_tts_manifest.json` in the output folder

The manifest records `id`, `text`, `voice`, `rate`, output path, and status. Keep this manifest with generated batches so future agents can see what was generated, skipped, or failed.

By default, existing MP3 files are skipped. Use `--force` only when intentionally replacing audio.

## Recommended Workflow

1. Create a small input file first, especially when generating audio for a new data shape.
2. Run with `--dry-run` to inspect filenames and manifest shape.
3. Generate a small sample batch.
4. Listen to a few files before running a large batch.
5. Run the full batch and keep the manifest.

## Notes

- Microsoft Edge TTS requires internet access and may fail when the service throttles or network access is blocked.
- Keep generated review/work audio outside source data until it has been listened to or otherwise approved.
- For N2Vocabulary repo work, prefer output folders under `output/`, `work/`, or a workflow-specific review folder instead of overwriting `clips/` directly.
