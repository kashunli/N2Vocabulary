# Unit 1 structural repair report

This report covers the repair pass on tracks 03, 04, and 05 using whisper.cpp large-v3-turbo plus local short-gap silence inspection.

## 21 遺伝スル (03 1-03.mp3)

- Root cause: `shared_boundary_neighbor`
- Resolution: `fixed_with_word_asr_noise`
- Old word: `20.702-21.393`
- Old sentence: `22.242-27.791`
- New word: `20.702-21.393`
- New sentence: `22.242-27.065`
- Base audit status: `asr_noise`
- Base audit word: `イテン`
- Base audit sentence: `私の左聞きは親からの移転だ`
- Base audit word reasons: `word_orthography_or_reading_drift`
- Note: ASR: 移転→遺伝 (word); Whisper detected 動作 in this region but audio is for 遺伝

## 22 動作 (03 1-03.mp3)

- Root cause: `word_sentence_merge`
- Resolution: `fixed`
- Old word: `28.653-29.704`
- Old sentence: `30.160-33.647`
- New word: `27.065-27.791`
- New sentence: `28.653-31.326`
- Base audit status: `ok`
- Base audit word: `どうさ`
- Base audit sentence: `彼女の動作は 夕画で美しい`
- Note: whisper.cpp large-v3-turbo + 0.12s local silence windows separated the true headword and sentence

## 25 食欲 (03 1-03.mp3)

- Root cause: `shared_boundary_neighbor`
- Resolution: `fixed`
- Old word: `49.096-50.093`
- Old sentence: `50.964-56.677`
- New word: `49.096-50.093`
- New sentence: `50.964-53.924`
- Base audit status: `ok`
- Base audit word: `食欲`
- Base audit sentence: `今、風を引いて食欲がない。`

## 26 外食スル (03 1-03.mp3)

- Root cause: `word_sentence_merge`
- Resolution: `fixed_large_backend_confirms`
- Old word: `57.422-58.589`
- Old sentence: `59.007-62.147`
- New word: `55.797-56.371`
- New sentence: `57.422-59.946`
- Base audit status: `suspect`
- Base audit word: `会社`
- Base audit sentence: `一人グラシになって、外食が増えた。`
- Base audit word reasons: `word_matches_neighbor_29`
- whisper.cpp large word: `外食` (score `1.0`)
- whisper.cpp large sentence: `一人暮らしになって外食が増えた。` (score `1.0`)
- Note: whisper.cpp large-v3-turbo + 0.12s local silence windows removed the merged word/sentence split

## 27 家事 (03 1-03.mp3)

- Root cause: `word_sentence_merge`
- Resolution: `fixed`
- Old word: `63.024-63.682`
- Old sentence: `64.371-66.402`
- New word: `61.707-62.147`
- New sentence: `63.024-66.402`
- Base audit status: `ok`
- Base audit word: `カジ`
- Base audit sentence: `最近はカジやイクジもする男性が増えた`
- Note: whisper.cpp large-v3-turbo + 0.12s local silence windows removed the merged word/sentence split

## 31 出勤 (03 1-03.mp3)

- Root cause: `empty_sentence_window`
- Resolution: `fixed`
- Old word: `86.909-87.174`
- Old sentence: `87.478-87.899`
- New word: `86.909-87.899`
- New sentence: `88.639-90.636`
- Base audit status: `ok`
- Base audit word: `主金`
- Base audit sentence: `毎朝8時に出勤している`
- Note: whisper.cpp large-v3-turbo recovered the spoken word+sentence pair after the empty sentence window

## 49 意志 / 意思 (04 1-04.mp3)

- Root cause: `shared_boundary_neighbor`
- Resolution: `fixed_large_backend_confirms`
- Old word: `73.143-73.603`
- Old sentence: `74.400-78.192`
- New word: `73.143-73.603`
- New sentence: `74.400-78.192`
- Base audit status: `suspect`
- Base audit word: `1 c`
- Base audit sentence: `彼女は一晴が硬いからきっと目的を達成するだろう`
- Base audit word reasons: `word_asr_mismatch`
- whisper.cpp large word: `一喜` (score `0.4`)
- whisper.cpp large sentence: `彼女は意思が固いからきっと目的を達成するだろう。` (score `0.954`)
- Note: whisper.cpp large-v3-turbo confirms the full 意志 sentence occupies this window

## 50 感情 (04 1-04.mp3)

- Root cause: `neighbor_sentence_leak`
- Resolution: `fixed_large_backend_confirms`
- Old word: `74.400-75.997`
- Old sentence: `76.541-78.192`
- New word: `80.005-80.912`
- New sentence: `81.723-84.068`
- Base audit status: `suspect`
- Base audit word: `館内を`
- Base audit sentence: `花火さんはすぐに感情が顔に出る`
- Base audit word reasons: `word_matches_neighbor_45`
- whisper.cpp large word: `感情` (score `0.889`)
- whisper.cpp large sentence: `田中さんはすぐに感情が顔に出る。` (score `1.0`)
- Note: whisper.cpp large-v3-turbo + 0.12s local silence windows removed the neighbor sentence leak from entry 49

## 54 券 (05 1-05.mp3)

- Root cause: `shared_boundary_neighbor`
- Resolution: `fixed_with_word_asr_noise`
- Old word: `17.215-17.644`
- Old sentence: `18.347-21.175`
- New word: `17.215-17.644`
- New sentence: `18.347-22.715`
- Base audit status: `asr_noise`
- Base audit word: `ピン`
- Base audit sentence: `あの店はいつも混んでいて、ハイルのに整理権が必要だ。`
- Base audit word reasons: `word_orthography_or_reading_drift`

## 55 名簿 (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed_large_backend_confirms`
- Old word: `21.435-22.715`
- Old sentence: `24.509-25.160`
- New word: `24.509-25.160`
- New sentence: `25.961-27.471`
- Base audit status: `suspect`
- Base audit word: `Nable`
- Base audit sentence: `クラスの目望を作る`
- Base audit word reasons: `word_asr_mismatch`
- whisper.cpp large word: `名簿` (score `1.0`)
- whisper.cpp large sentence: `クラスの名簿を作る。` (score `1.0`)

## 56 表 (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed_with_word_asr_noise`
- Old word: `25.961-27.471`
- Old sentence: `29.274-29.852`
- New word: `29.274-29.852`
- New sentence: `30.669-32.202`
- Base audit status: `asr_noise`
- Base audit word: `今日`
- Base audit sentence: `性責を表にする`
- Base audit word reasons: `word_orthography_or_reading_drift`

## 57 針 (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed_large_backend_confirms`
- Old word: `30.669-32.202`
- Old sentence: `34.028-34.423`
- New word: `34.028-34.423`
- New sentence: `35.247-36.660`
- Base audit status: `suspect`
- Base audit word: `ハーディ`
- Base audit sentence: `針に糸を通す。`
- Base audit word reasons: `word_asr_mismatch`
- whisper.cpp large word: `ハディ` (score `0.4`)
- whisper.cpp large sentence: `針に糸を通す。` (score `1.0`)

## 58 栓 (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `sentence_fixed_word_still_short_asr`
- Old word: `35.247-36.660`
- Old sentence: `38.490-39.161`
- New word: `38.490-39.161`
- New sentence: `39.887-41.308`
- Base audit status: `suspect`
- Base audit word: `SIN!`
- Base audit sentence: `ビールの線を抜く`
- Base audit word reasons: `word_asr_mismatch`
- whisper.cpp large word: `1000` (score `0.0`)
- whisper.cpp large sentence: `ビールの線を抜く。` (score `1.0`)

## 59 湯気 (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `sentence_fixed_word_still_short_asr`
- Old word: `39.887-41.308`
- Old sentence: `43.115-43.568`
- New word: `43.115-43.568`
- New sentence: `44.322-46.876`
- Base audit status: `suspect`
- Base audit word: `右の方向を押して、`
- Base audit sentence: `うどんのゆげで、根が根がくもってしまう。`
- Base audit word reasons: `word_clip_contains_sentence_audio, word_matches_neighbor_52, word_clip_too_long_or_merged`
- whisper.cpp large word: `ユングエ` (score `0.333`)
- whisper.cpp large sentence: `うどんの湯気で眼鏡が曇ってしまった。` (score `1.0`)

## 60 日当たり (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed`
- Old word: `44.322-45.267`
- Old sentence: `45.603-47.157`
- New word: `49.013-49.805`
- New sentence: `50.611-53.716`
- Base audit status: `ok`
- Base audit word: `ピアタリ`
- Base audit sentence: `私の部屋は南向きで、火当たりがいい。`

## 61 空 (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed_with_word_asr_noise`
- Old word: `49.013-49.805`
- Old sentence: `50.611-52.434`
- New word: `55.521-55.904`
- New sentence: `56.816-59.935`
- Base audit status: `asr_noise`
- Base audit word: `カラ`
- Base audit sentence: `作業は一人でワイン一輪を空にした`
- Base audit word reasons: `word_orthography_or_reading_drift`

## 62 斜め (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed`
- Old word: `52.762-53.716`
- Old sentence: `55.521-55.904`
- New word: `61.672-62.295`
- New sentence: `63.106-65.820`
- Base audit status: `ok`
- Base audit word: `斜め`
- Base audit sentence: `自信で家が斜めに固むいた`

## 63 履歴 (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed`
- Old word: `56.816-59.935`
- Old sentence: `61.672-62.295`
- New word: `67.640-68.370`
- New sentence: `69.187-72.332`
- Base audit status: `ok`
- Base audit word: `リレッキ`
- Base audit sentence: `会社に応募するにあたり、リレキシュを書いた。`

## 64 娯楽 (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed_with_word_asr_noise`
- Old word: `63.106-63.761`
- Old sentence: `64.177-65.820`
- New word: `74.131-74.907`
- New sentence: `75.690-79.110`
- Base audit status: `asr_noise`
- Base audit word: `ご覧`
- Base audit sentence: `うちの父は、すりをご覧として楽しんでいる。`
- Base audit word reasons: `word_orthography_or_reading_drift`

## 65 司会 (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed`
- Old word: `67.640-68.370`
- Old sentence: `69.187-70.718`
- New word: `80.953-81.664`
- New sentence: `82.389-85.026`
- Base audit status: `ok`
- Base audit word: `しっかい`
- Base audit sentence: `友人に結婚式の司会を頼んだ`

## 66 歓迎スル (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed_large_backend_confirms`
- Old word: `71.306-72.332`
- Old sentence: `74.131-74.907`
- New word: `86.807-87.706`
- New sentence: `88.529-91.169`
- Base audit status: `suspect`
- Base audit word: `行け`
- Base audit sentence: `新入社員を関係する会が開かれた`
- Base audit word reasons: `word_asr_mismatch`
- whisper.cpp large word: `反映` (score `0.571`)
- whisper.cpp large sentence: `新入社員を歓迎する会が開かれた` (score `0.98`)

## 67 窓口 (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed`
- Old word: `75.690-76.478`
- Old sentence: `77.051-79.110`
- New word: `92.964-93.844`
- New sentence: `94.551-97.946`
- Base audit status: `ok`
- Base audit word: `窓口`
- Base audit sentence: `銀行の窓口には、王勢の人が並んでいた`

## 68 手続き(ヲ)スル (05 1-05.mp3)

- Root cause: `cascade_anchor_drift`
- Resolution: `fixed_large_backend_confirms`
- Old word: `80.953-81.664`
- Old sentence: `82.389-85.026`
- New word: `99.706-100.214`
- New sentence: `101.305-103.135`
- Base audit status: `suspect`
- Base audit word: `ベッツス`
- Base audit sentence: `入学の手続きをする`
- Base audit word reasons: `word_asr_mismatch`
- whisper.cpp large word: `手続き` (score `1.0`)
- whisper.cpp large sentence: `入学の手続きをする` (score `0.963`)
