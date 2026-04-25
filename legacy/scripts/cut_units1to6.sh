#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

WCPP_BIN="tools/whispercpp-windows/whisper-cli.exe"
WCPP_MODEL="tools/whispercpp-windows/ggml-large-v3-turbo.bin"

run_track() {
    local file="$1"
    local out_dir="$2"
    echo "=== Cutting: $out_dir ==="
    python3 cutTwice/cut_by_silence.py --track "$file" --just-cut --output-dir "$out_dir"
    python3 cutTwice/transcribe_pairs.py --pairs-json "$out_dir/pairs.json" --wcpp-binary "$WCPP_BIN" --wcpp-model "$WCPP_MODEL" --language ja
    python3 cutTwice/cut_word.py --pairs-json "$out_dir/pairs.json" --wcpp-binary "$WCPP_BIN" --wcpp-model "$WCPP_MODEL" --language ja
    echo "=== DONE: $out_dir ==="
}

run_unit() {
    local unit_prefix="$1"   # e.g. "unit1"
    local audio_dir="$2"     # e.g. "audio/Unit1 名詞A"
    local skip_first="$3"    # "yes" to skip first file (intro track)

    local first=true
    for file in "$audio_dir"/*.mp3; do
        [ -f "$file" ] || continue
        filename="$(basename "$file")"
        track_num="${filename%% *}"   # leading number before first space
        track_num_padded=$(printf "%02d" "$((10#$track_num))")

        if [ "$first" = true ] && [ "$skip_first" = "yes" ]; then
            echo "--- Skipping intro: $filename ---"
            first=false
            continue
        fi
        first=false

        run_track "$file" "clips/${unit_prefix}_track${track_num_padded}"
    done
}

# Unit1 名詞A — words 1-100 — tracks 02-07 (skip 01=intro)
run_unit "unit1" "audio/Unit1 名詞A" "yes"

# Unit2 動詞A — words 101-220 — tracks 08-16
run_unit "unit2" "audio/Unit2 動詞A" "no"

# Unit3 形容詞A — words 221-270 — tracks 17-21
run_unit "unit3" "audio/Unit3 形容詞A" "no"

# Unit4 名詞B — words 271-370 — tracks 22-28
run_unit "unit4" "audio/Unit4 名詞B" "no"

# Unit4.5 まとめ1複合動詞 — words 371-460 — tracks 29-33
run_unit "unit4_5" "audio/Unit4.5 まとめ1複合動詞" "no"

# Unit5 カタカナA — words 461-510 — tracks 34-38
run_unit "unit5" "audio/Unit5 カタカナA" "no"

# Unit6 副詞A＋接続詞 — words 511-580 — tracks 39-43
run_unit "unit6" "audio/Unit6 副詞A＋接続詞" "no"

echo "ALL DONE units 1-6"
