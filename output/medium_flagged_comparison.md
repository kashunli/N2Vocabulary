# Flagged-entry base vs medium comparison

This report covers the 21 suspicious entries from the 7-track medium rerun.

Scenario labels:
- `A`: medium recovered a usable word/sentence split directly.
- `B`: medium still merged word+sentence, so the final mapping was rebuilt from ffmpeg silence edges inside the region.

## 75 日程 (06 1-06.mp3, word)

- Scenario: `A`
- Old base-derived mapping: word `30.260-32.060` | sentence `32.060-35.480`
- Medium segments in window: 31.260-32.060 日程; 32.060-36.000 急な用事で旅行の日程を変えた
- Final recut span: `31.000-31.415`
- Snap fallback after update: `False`

## 78 時期 (06 1-06.mp3, sentence)

- Scenario: `A`
- Old base-derived mapping: word `50.020-50.640` | sentence `51.280-56.560`
- Medium segments in window: 44.560-49.900 子供たちが教室に順序よく並んで入っていく; 49.900-51.440 時期; 51.440-57.460 3月から4月はうちの会社にとって忙しい時期だ
- Final recut span: `51.524-55.875`
- Snap fallback after update: `False`

## 84 おまけ (06 1-06.mp3, sentence)

- Scenario: `A`
- Old base-derived mapping: word `92.040-92.600` | sentence `93.300-98.160`
- Medium segments in window: 86.440-91.340 まとめて買うから少し割引してください; 91.840-93.480 おまけ; 93.480-99.600 4個550円のリンゴをおまけしてもらって500円で買った
- Final recut span: `93.470-98.210`
- Snap fallback after update: `False`

## 89 支出 (07 1-07.mp3, sentence)

- Scenario: `A`
- Old base-derived mapping: word `7.680-8.680` | sentence `9.280-14.960`
- Medium segments in window: 2.400-7.420 彼は喫茶店を経営して収入を得ている; 7.420-9.340 支出; 9.340-15.080 今年は支出が収入を上回って赤字になった; 15.080-16.800 予算
- Final recut span: `9.544-13.778`
- Snap fallback after update: `False`

## 95 弁償(ヲ)スル (07 1-07.mp3, sentence)

- Scenario: `A`
- Old base-derived mapping: word `44.360-45.160` | sentence `46.100-51.380`
- Medium segments in window: 41.040-43.820 金を勘定する; 44.800-45.760 弁償; 45.760-52.120 隣の家の窓ガラスを割ってしまったので修理代を弁償した
- Final recut span: `46.272-50.944`
- Snap fallback after update: `False`

## 109 悲しむ (08 1-08.mp3, sentence)

- Scenario: `B`
- Old base-derived mapping: word `52.340-53.560` | sentence `53.920-59.160`
- Medium segments in window: 52.520-60.600 悲しむ 娘はペットの死を悲しんで一日中泣いていた
- Final recut span: `54.175-59.191`
- Snap fallback after update: `False`

## 113 張り切る (08 1-08.mp3, sentence)

- Scenario: `B`
- Old base-derived mapping: word `77.920-79.000` | sentence `79.000-85.880`
- Medium segments in window: 73.320-78.720 うなずく 祖父は何も言わずにうなずいた; 79.680-87.220 張り切る 入社第1日目娘は張り切って出勤した
- Final recut span: `81.276-85.927`
- Snap fallback after update: `False`

## 116 暴れる (08 1-08.mp3, sentence)

- Scenario: `B`
- Old base-derived mapping: word `101.500-102.380` | sentence `102.960-109.820`
- Medium segments in window: 95.300-100.940 怒鳴る そんなに大声で怒鳴らなくても聞こえますよ; 101.820-109.960 暴れる 弟は気が短く子供の頃はすぐに暴れてよくものを壊したものだ
- Final recut span: `103.263-109.852`
- Snap fallback after update: `False`

## 137 近寄る (10 1-10.mp3, sentence)

- Scenario: `B`
- Old base-derived mapping: word `25.060-25.640` | sentence `25.640-30.940`
- Medium segments in window: 24.960-31.360 近寄る。物音がしたので窓に近寄って外を見た。
- Final recut span: `26.541-30.096`
- Snap fallback after update: `False`

## 143 痛む (10 1-10.mp3, sentence)

- Scenario: `B`
- Old base-derived mapping: word `60.720-61.680` | sentence `62.100-65.640`
- Medium segments in window: 55.260-59.980 溺れる。川に落ちて溺れている子供を助けた。; 61.280-64.580 痛む。歯が痛む。; 65.300-69.800 かかる。インフルエンザにかかって学校を休んだ。
- Final recut span: `62.397-63.289`
- Snap fallback after update: `False`

## 147 診る (10 1-10.mp3, sentence)

- Scenario: `B`
- Old base-derived mapping: word `79.320-80.040` | sentence `80.640-85.480`
- Medium segments in window: 75.340-79.060 吐く。息を吸って吐く。; 79.920-85.240 見る。体の調子が悪いので医者に見てもらおう。; 86.280-91.000 見舞う。入院中の友達をみんなで見舞った。
- Final recut span: `80.878-84.233`
- Snap fallback after update: `False`

## 154 払い戻す (11 1-11.mp3, sentence)

- Scenario: `B`
- Old base-derived mapping: word `25.780-27.500` | sentence `27.500-32.780`
- Medium segments in window: 19.200-25.340 払い込む 今季の授業料を銀行に払い込んだ; 25.900-34.240 払い戻す 電話会社は課題請求額を利用者の講座に払い戻した
- Final recut span: `27.777-32.762`
- Snap fallback after update: `False`

## 154 払い戻す (11 1-11.mp3, word)

- Scenario: `B`
- Old base-derived mapping: word `25.780-27.500` | sentence `27.500-32.780`
- Medium segments in window: 19.200-25.340 払い込む 今季の授業料を銀行に払い込んだ; 25.900-34.240 払い戻す 電話会社は課題請求額を利用者の講座に払い戻した
- Final recut span: `26.106-26.964`
- Snap fallback after update: `False`

## 158 落ち込む (11 1-11.mp3, word)

- Scenario: `B`
- Old base-derived mapping: word `50.860-52.500` | sentence `52.500-55.980`
- Medium segments in window: 45.460-50.960 儲ける 彼は株で100万円儲けた; 50.960-56.340 落ち込む 景気が落ち込んで失業率が上がった
- Final recut span: `51.251-51.976`
- Snap fallback after update: `False`

## 160 売り切れる (11 1-11.mp3, word)

- Scenario: `B`
- Old base-derived mapping: word `63.480-65.500` | sentence `65.500-69.100`
- Medium segments in window: 57.660-62.660 売れる この cd は100万枚売れたそうだ; 63.740-69.180 売り切れる そのコンサートのチケットは1時間で売り切れたそうだ
- Final recut span: `63.873-64.635`
- Snap fallback after update: `False`

## 163 固まる (12 1-12.mp3, word)

- Scenario: `B`
- Old base-derived mapping: word `11.760-13.500` | sentence `13.500-17.060`
- Medium segments in window: 6.000-11.720 くっつける 机と机をくっつけて並べた; 11.720-18.420 固まる 液体にゼラチンを入れると固まってゼリーになる
- Final recut span: `12.014-12.656`
- Snap fallback after update: `False`

## 165 縮む (12 1-12.mp3, word)

- Scenario: `B`
- Old base-derived mapping: word `24.340-26.000` | sentence `26.000-29.140`
- Medium segments in window: 18.420-23.920 固める ジュースを固めてゼリーを作った; 24.460-30.520 ちじむ 洗濯したらセーターが縮んでしまった
- Final recut span: `24.649-25.249`
- Snap fallback after update: `False`

## 187 ほどく (14 1-14.mp3, word)

- Scenario: `B`
- Old base-derived mapping: word `5.200-6.800` | sentence `6.800-10.200`
- Medium segments in window: 0.620-5.220 ほどける くつのひもがほどけた; 5.220-11.300 ほどく にもつのひもをほどいて中のものを出す
- Final recut span: `5.459-5.937`
- Snap fallback after update: `False`

## 188 枯れる (14 1-14.mp3, word)

- Scenario: `B`
- Old base-derived mapping: word `11.280-13.000` | sentence `13.000-15.580`
- Medium segments in window: 5.220-11.300 ほどく にもつのひもをほどいて中のものを出す; 11.300-16.780 かれる 害虫のせいで木が枯れてしまった
- Final recut span: `11.586-12.135`
- Snap fallback after update: `False`

## 191 湿る (14 1-14.mp3, word)

- Scenario: `B`
- Old base-derived mapping: word `29.900-31.500` | sentence `31.500-34.240`
- Medium segments in window: 23.320-29.920 痛む 生魚は痛みやすいから早く食べた方がいい; 29.920-35.740 しめる 朝干した洗濯物がまだしめっている
- Final recut span: `30.193-30.740`
- Snap fallback after update: `False`

## 195 あふれる (14 1-14.mp3, word)

- Scenario: `B`
- Old base-derived mapping: word `50.860-52.500` | sentence `52.500-54.780`
- Medium segments in window: 45.520-50.580 輝く 空に太陽が輝いている; 50.580-55.660 あふれる 大雨で川の水があふれた
- Final recut span: `51.185-51.822`
- Snap fallback after update: `False`

