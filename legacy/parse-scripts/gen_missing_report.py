#!/usr/bin/env python3
"""Generate output/missing_audio_entries.md — full record of entries with no clips."""
import json
from pathlib import Path
from datetime import date

combined = json.loads(open('output/vocabulary_combined.json', encoding='utf-8').read())
ROOT  = Path('.')
CLIPS = ROOT / 'output' / 'clips'

# Load alignment data from the canonical single file if it exists, otherwise
# aggregate from per-unit review files (dedup by index; alphabetical order
# means _all/_combined/_resolved files overwrite per-track entries).
_manifest_path = ROOT / 'output' / 'review_assigned.json'
if _manifest_path.exists():
    manifest = json.loads(_manifest_path.read_text(encoding='utf-8'))
else:
    _by_idx: dict[int, dict] = {}
    for _f in sorted((ROOT / 'output').glob('review_unit*.json')):
        for _row in json.loads(_f.read_text(encoding='utf-8')):
            _by_idx[_row['index']] = _row
    manifest = list(_by_idx.values())
    if not manifest:
        raise FileNotFoundError(
            "No alignment data found: create output/review_assigned.json "
            "or run align_track_by_llm.py to generate per-unit review files."
        )

by_entry    = {e['index']: e for e in combined}
by_manifest = {m['index']: m for m in manifest}
all_idxs    = sorted(by_entry.keys())

# Index all manifest entries by track_path → sorted list of entry indexes.
track_entries: dict[str, list[int]] = {}
for m in manifest:
    tp = m.get('track_path')
    if tp:
        track_entries.setdefault(tp, []).append(m['index'])
for tp in track_entries:
    track_entries[tp].sort()


def has_clip(idx, unit):
    d = CLIPS / f'unit{unit:02d}'
    return (
        (d / f'sentence{idx}.mp3').exists() or
        (d / f'word{idx}.mp3').exists() or
        (d / f'sentence{idx}-deduced.mp3').exists() or
        (d / f'word{idx}-deduced.mp3').exists() or
        any(d.glob(f'region*{idx}*.mp3'))
    )


def find_neighbors(idx):
    prev_m = next(
        (by_manifest[i] for i in range(idx - 1, 0, -1)
         if by_manifest.get(i) and by_manifest[i].get('track_path')),
        None,
    )
    next_m = next(
        (by_manifest[i] for i in range(idx + 1, max(all_idxs) + 2)
         if by_manifest.get(i) and by_manifest[i].get('track_path')),
        None,
    )
    return prev_m, next_m


def track_cmd(track_path: str, start: int, end: int) -> str:
    """Build assign_track_clips.py command for a track path and index range."""
    # track_path is relative like "audio/Unit7 .../47 1-47.mp3"
    return (
        f"python -u parse/scripts/assign_track_clips.py"
        f" --track \"{track_path}\""
        f" --start {start} --end {end}"
    )


missing = [e for e in combined if not has_clip(e['index'], e['unit']['number'])]

# Group into contiguous index runs.
runs: list[list[dict]] = []
run = [missing[0]]
for e in missing[1:]:
    if e['index'] == run[-1]['index'] + 1:
        run.append(e)
    else:
        runs.append(run)
        run = [e]
runs.append(run)

same_track_runs = []
boundary_runs   = []
for run in runs:
    prev_m, next_m = find_neighbors(run[0]['index'])
    if (prev_m and next_m
            and prev_m.get('track_path') == next_m.get('track_path')):
        same_track_runs.append(run)
    else:
        boundary_runs.append(run)

st_entries  = sum(len(r) for r in same_track_runs)
bnd_entries = sum(len(r) for r in boundary_runs)

L = []

L.append("# N2 Vocabulary — Entries Without Audio Clips")
L.append(f"Generated: {date.today()}  |  "
         f"Missing: {len(missing)} / {len(combined)} entries\n")

L.append("## Summary\n")
L.append("| Category | Entries | Runs |")
L.append("|----------|---------|------|")
L.append(f"| Same-track gap — run assign_track_clips.py as-is "
         f"| {st_entries} | {len(same_track_runs)} |")
L.append(f"| Track boundary — at tail of prev track OR head of next track "
         f"| {bnd_entries} | {len(boundary_runs)} |")
L.append(f"| **Total** | **{len(missing)}** | **{len(runs)}** |")
L.append("")

# ── Part 1: Same-track recoverable ───────────────────────────────────────────
L.append("---\n")
L.append("## Part 1: Same-Track Gaps\n")
L.append("Entries sandwiched between two matched entries on the same track.\n")

for run in same_track_runs:
    prev_m, next_m = find_neighbors(run[0]['index'])
    track = prev_m['track_name']
    rs    = prev_m.get('sentence_end') or prev_m.get('word_end') or 0.0
    re_   = next_m.get('word_start') or 0.0
    dur   = re_ - rs
    idxs  = [e['index'] for e in run]
    tp    = prev_m['track_path']

    L.append(f"### idx {idxs[0]}–{idxs[-1]}  ({len(run)})  `{track}`  "
             f"region {rs:.1f}s–{re_:.1f}s ({dur:.1f}s)\n")
    L.append("| idx | headword | reading | sentence |")
    L.append("|-----|----------|---------|----------|")
    for e in run:
        L.append(f"| {e['index']} | {e.get('headword_text','')} "
                 f"| {e.get('reading','')} | {e.get('sentence_text','')[:80]} |")
    L.append(f"\n```bash\n{track_cmd(tp, idxs[0], idxs[-1])}\n```\n")

# ── Part 2: Track boundary — two candidate commands each ─────────────────────
L.append("---\n")
L.append("## Part 2: Track Boundary Entries\n")
L.append(
    "A word and its sentence are never split across tracks, so each missing entry "
    "is at the **tail of the prev track** or the **head of the next track**.\n"
    "Two ready-to-run commands are given per run — try the more likely one first.\n"
)

for run in boundary_runs:
    prev_m, next_m = find_neighbors(run[0]['index'])
    unit  = run[0]['unit']['number']
    idxs  = [e['index'] for e in run]

    L.append(f"### idx {idxs[0]}–{idxs[-1]}  ({len(run)} entries)  Unit {unit}\n")
    L.append("| idx | headword | reading | sentence |")
    L.append("|-----|----------|---------|----------|")
    for e in run:
        L.append(f"| {e['index']} | {e.get('headword_text','')} "
                 f"| {e.get('reading','')} | {e.get('sentence_text','')[:80]} |")
    L.append("")

    # Option A: tail of prev track — extend prev track range to include missing.
    if prev_m:
        tp_prev  = prev_m['track_path']
        prev_all = track_entries.get(tp_prev, [])
        prev_min = min(prev_all) if prev_all else prev_m['index']
        # range: all entries known on prev track + the missing run
        a_start, a_end = prev_min, idxs[-1]
        L.append(f"**Option A — tail of `{prev_m['track_name']}`** "
                 f"(extends known range {prev_min}–{prev_m['index']} → adds {idxs[0]}–{idxs[-1]})")
        L.append(f"```bash\n{track_cmd(tp_prev, a_start, a_end)}\n```")
    else:
        L.append("*(no prev track — entry may be first on its track)*")

    # Option B: head of next track — prepend missing to next track range.
    if next_m:
        tp_next  = next_m['track_path']
        next_all = track_entries.get(tp_next, [])
        next_max = max(next_all) if next_all else next_m['index']
        b_start, b_end = idxs[0], next_max
        L.append(f"\n**Option B — head of `{next_m['track_name']}`** "
                 f"(prepends {idxs[0]}–{idxs[-1]} to known range {next_m['index']}–{next_max})")
        L.append(f"```bash\n{track_cmd(tp_next, b_start, b_end)}\n```")
    else:
        L.append("*(no next track — entry may be last on its track)*")

    L.append("")

out = '\n'.join(L) + '\n'
Path('output/missing_audio_entries.md').write_text(out, encoding='utf-8')
print(f"Written: output/missing_audio_entries.md")
print(f"  Same-track (Part 1)    : {st_entries} entries in {len(same_track_runs)} runs")
print(f"  Track boundary (Part 2): {bnd_entries} entries in {len(boundary_runs)} runs")
print(f"  Total missing          : {len(missing)}")
