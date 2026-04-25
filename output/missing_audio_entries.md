# N2 Vocabulary — Entries Without Audio Clips
Generated: 2026-04-19  |  Missing: 16 / 1142 entries

## Summary

| Category | Entries | Runs |
|----------|---------|------|
| Same-track gap — run assign_track_clips.py as-is | 0 | 0 |
| Track boundary — at tail of prev track OR head of next track | 16 | 6 |
| **Total** | **16** | **6** |

---

## Part 1: Same-Track Gaps

Entries sandwiched between two matched entries on the same track.

---

## Part 2: Track Boundary Entries

A word and its sentence are never split across tracks, so each missing entry is at the **tail of the prev track** or the **head of the next track**.
Two ready-to-run commands are given per run — try the more likely one first.

### idx 580–580  (1 entries)  Unit 6

| idx | headword | reading | sentence |
|-----|----------|---------|----------|
| 580 | ただ | ただ | あのレストランは味もいいし、値段も安い。ただ、場所がちょっと不便だ。 |

**Option A — tail of `38 1-38.mp3`** (extends known range 509–510 → adds 580–580)
```bash
python -u parse/scripts/assign_track_clips.py --track "audio\Unit5 カタカナA\38 1-38.mp3" --start 509 --end 580
```
*(no next track — entry may be last on its track)*

### idx 653–655  (3 entries)  Unit 7

| idx | headword | reading | sentence |
|-----|----------|---------|----------|
| 653 | 都会 | とかい | 田舎の高校生だった私は、都会にあこがれていた。 |
| 654 | 世論 | よろん | 現代の政治家は世論を無視することはできない。 |
| 655 | 民族 | みんぞく | 世界にはさまざまな民族が存在する。 |

**Option A — tail of `38 1-38.mp3`** (extends known range 509–510 → adds 653–655)
```bash
python -u parse/scripts/assign_track_clips.py --track "audio\Unit5 カタカナA\38 1-38.mp3" --start 509 --end 655
```
*(no next track — entry may be last on its track)*

### idx 661–662  (2 entries)  Unit 7

| idx | headword | reading | sentence |
|-----|----------|---------|----------|
| 661 | 減退 | げんたい | 暑さのせいで食欲が減退した。 |
| 662 | 減量 | げんりょう | 洗剤の中身が減量された。これでは値上げと同じだ。 |

**Option A — tail of `38 1-38.mp3`** (extends known range 509–510 → adds 661–662)
```bash
python -u parse/scripts/assign_track_clips.py --track "audio\Unit5 カタカナA\38 1-38.mp3" --start 509 --end 662
```
*(no next track — entry may be last on its track)*

### idx 788–790  (3 entries)  Unit 8

| idx | headword | reading | sentence |
|-----|----------|---------|----------|
| 788 | 恐れる | おそれる | 動物（どうぶつ）は火（ひ）を恐（おそ）れる。 |
| 789 | 恨む | うらむ | 私（わたし）は今（いま）でも、私（わたし）をいじめた同級生（どうきゅうせい）を恨（うら）んでいる。 |
| 790 | 慰める | なぐさめる | 失恋（しつれん）した友（とも）だちをみんなでなぐさめた。 |

**Option A — tail of `38 1-38.mp3`** (extends known range 509–510 → adds 788–790)
```bash
python -u parse/scripts/assign_track_clips.py --track "audio\Unit5 カタカナA\38 1-38.mp3" --start 509 --end 790
```
*(no next track — entry may be last on its track)*

### idx 989–990  (2 entries)  Unit 11

| idx | headword | reading | sentence |
|-----|----------|---------|----------|
| 989 | 矛盾 | むじゅん | 田中(たなか)さんは言(い)っていることとしていることが矛盾(むじゅん)している。 |
| 990 | 存在 | そんざい | 世界(せかい)にはUFOの存在(そんざい)を信(しん)じる人(ひと)が多(おお)くいる。 |

**Option A — tail of `38 1-38.mp3`** (extends known range 509–510 → adds 989–990)
```bash
python -u parse/scripts/assign_track_clips.py --track "audio\Unit5 カタカナA\38 1-38.mp3" --start 509 --end 990
```
*(no next track — entry may be last on its track)*

### idx 1086–1090  (5 entries)  Unit 12

| idx | headword | reading | sentence |
|-----|----------|---------|----------|
| 1086 | ガほほえむ | ほほえむ | 彼女は私ににっこりとほほえんだ。 |
| 1087 | ガふざける | ふざける | 弟はふざけて人を笑わせるのが得意だ。 |
| 1088 | ラ悔やむ | くやむ | 過ぎたことを今さら悔やんでも遅い。 |
| 1089 | ラためらう | ためらう | 申し込みをためらっているうちに、締め切りが過ぎてしまった。 |
| 1090 | ラ敬う | うやまう | 神仏を敬う。 |

**Option A — tail of `38 1-38.mp3`** (extends known range 509–510 → adds 1086–1090)
```bash
python -u parse/scripts/assign_track_clips.py --track "audio\Unit5 カタカナA\38 1-38.mp3" --start 509 --end 1090
```
*(no next track — entry may be last on its track)*

