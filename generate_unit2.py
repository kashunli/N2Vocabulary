#!/usr/bin/env python3
"""Generate sentence explanations for JLPT N2 Unit 2 (動詞 A), entries 101-220."""
import json

explanations = {}

# Entry 101
explanations[101] = """「お年寄りは、一般的に淡泊な味を好む傾向がある。」

---

- **好む（このむ）** — to prefer, to like (trans. verb). Expresses a settled preference or taste rather than a momentary liking. [JLPT N2]
- **～におよぶ** is not used here; this is a plain factual statement with 一般的に as a generalization marker. [JLPT N4]
"""

# Entry 102
explanations[102] = """「彼女は彼に嫌悪感を抱いているようだ。」

---

- **嫌う（きらう）** — to dislike, to hate, to avoid (trans. verb). Stronger than 嫌い; implies active aversion. ↔ 好む. [JLPT N2]
- **～ているようだ** — appearance/conjecture based on indirect evidence. "It seems that..." [JLPT N3]
"""

# Entry 103
explanations[103] = """「世界平和を祈り求める。」

---

- **願う（ねがう）** — to wish for, to hope for, to pray (trans. verb). Formal, often used for earnest or idealistic wishes. Wago (和語). [JLPT N2]
"""

# Entry 104
explanations[104] = """「子供が母親に依存して甘えている。」

---

- **甘える（あまえる）** — to depend on another's kindness, to behave coquettishly, to take advantage of someone's goodwill (intrans. verb). A uniquely Japanese concept describing the act of relying on another's indulgence. [JLPT N2]
"""

# Entry 105
explanations[105] = """「息子は妹をとても可愛がっている。」

---

- **可愛がる（かわいがる）** — to show affection to, to treat fondly, to dote on (trans. verb). Derived from 可愛い (cute/dear) + がる (to feel/show). [JLPT N2]
"""

# Entry 106
explanations[106] = """「犯人は刑事に気付かれて逃げた。」

---

- **気付く（きづく）／気が付く** — to notice, to become aware of (intrans. verb). ↔ 気付かせる (to make someone notice). [JLPT N3]
- **～てしまう** — completion with regret or negative consequence. The criminal's discovery led to his flight. [JLPT N3]
- Note: The criminal is the subject of 気付く, and the detective is marked with に — the criminal noticed the detective (not vice versa), then fled. This is an active perception construction.
"""

# Entry 107
explanations[107] = """「警察は私を犯人ではないかと疑っているようだ。」

---

- **疑う（うたがう）** — to suspect, to doubt (trans. verb). Wago. ↔ 信じる. Chinese false friend: 疑う means "to suspect/doubt," but the Chinese 疑 can also mean "to doubt" — similar but the Japanese usage is broader. [JLPT N2]
- **～ではないかと** — indirect quotation expressing uncertainty. "whether I might not be..." [JLPT N3]
- **～ているらしい** — conjecture based on some evidence. "It seems that..." [JLPT N3]
"""

# Entry 108
explanations[108] = """「学校でいじめられて苦しんでいる子供がたくさんいる。」

---

- **苦しむ（くるしむ）** — to suffer, to be in agony (intrans. verb). Can refer to physical or mental suffering. [JLPT N2]
- **～てしまう** (contracted to ている) — ongoing state. The children are currently in a state of suffering. [JLPT N3]
- **いじめる** — to bully (trans. verb). Here in passive form いじめられて, showing the children as victims. [JLPT N4]
"""

# Entry 109
explanations[109] = """「娘はペットの死を悲しみ、一日中泣いていた。」

---

- **悲しむ（なさむ）** — to grieve, to feel sorrow (trans./intrans. verb). Wago. The object of grief is marked with を or で. [JLPT N2]
- **～ていた** — past continuous state. She was in the state of crying all day. [JLPT N3]
"""

# Entry 110
explanations[110] = """「試験に落ちてがっかりした。」

---

- **がっかりする** — to be disappointed, to feel let down (suru-verb). Onomatopoeic origin (がっかり = feeling of sudden disappointment). [JLPT N3]
- **～に落ちる** — to fail (an exam). Standard collocation with 試験. [JLPT N4]
"""

# Entry 111
explanations[111] = """「受験に失敗した友達を励ました。」

---

- **励ます（はげます）** — to encourage, to cheer up (trans. verb). [JLPT N2]
"""

# Entry 112
explanations[112] = """「祖父は何も言わずにうなずいた。」

---

- **うなずく（頷く）** — to nod (intrans. verb). Expresses agreement or acknowledgment through a nodding gesture. Wago. [JLPT N2]
- **～ずに** — without doing (classical negative form of ないで). "Without saying anything." [JLPT N2]
"""

# Entry 113
explanations[113] = """「入社初日、娘は意気揚々と出勤した。」

---

- **張り切る（はりきる）** — to be full of enthusiasm, to be eager, to go all out (intrans. verb). 張る (to stretch/tighten) + 切る (to complete) → to be fully pumped up. [JLPT N2]
"""

# Entry 114
explanations[114] = """「自分ができるからといって、すぐに威張るような人は嫌われるものだ。」

---

- **威張る（いばる）** — to be bossy, to swagger, to act arrogantly (intrans. verb). Wago. Implies an unpleasant, overbearing attitude. [JLPT N2]
- **～からといって** — "just because... doesn't mean." Concessive reasoning. [JLPT N2]
- **嫌われる** — passive of 嫌う. "to be disliked." Here a general statement about what kind of people tend to be disliked. [JLPT N3]
"""

# Entry 115
explanations[115] = """「そんなに大声で怒鳴らなくても聞こえますよ。」

---

- **怒鳴る（どなる）** — to shout, to yell, to bellow (intrans. verb). Implies a loud, often angry voice. Wago. [JLPT N2]
- **～なくても** — "even if you don't need to." Polite suggestion that the action is unnecessary. [JLPT N4]
"""

# Entry 116
explanations[116] = """「弟は短気で、子供の頃はすぐに暴れて、よく物を壊したものだ。」

---

- **暴れる（あばれる）** — to rampage, to act violently, to lose control (intrans. verb). Describes wild, unrestrained behavior. [JLPT N2]
- **～ものだ** — nostalgic reminiscence about past habits. "Used to..." [JLPT N3]
"""

# Entry 117
explanations[117] = """「子供が道の途中でしゃがんで地面の虫を見ている。」

---

- **しゃがむ** — to squat, to crouch down (intrans. verb). Wago. Lowering the body with bent knees. [JLPT N2]
"""

# Entry 118
explanations[118] = """「少しそこをどいてください。」

---

- **どく（退く）** — to step aside, to move out of the way (intrans. verb). Wago. ↔ どける (trans.). Casual/colloquial; in formal contexts 退く（のく）is used. [JLPT N2]
"""

# Entry 119
explanations[119] = """「通行の邪魔になるので、自転車を歩道からどけてください。」

---

- **どける（退ける）** — to move (something) aside, to remove from the way (trans. verb). ↔ どく (intrans.). Wago. [JLPT N2]
- **じゃま（邪魔）** — obstruction, nuisance. Kango (漢語). [JLPT N4]
"""

# Entry 120
explanations[120] = """「帽子を頭に乗せる。」

---

- **かぶる（被る）** — to wear (on the head), to cover (trans. verb). Used exclusively for headwear. ↔ かぶせる (trans., to put something over something else). Wago. [JLPT N2]
"""

# Entry 121
explanations[121] = """「濡れないように、自転車にシートを掛けておいた。」

---

- **かぶせる（被せる）** — to put something over something else, to cover with (trans. verb). ↔ かぶる. The transitive counterpart: you かぶる a hat (on your own head), but かぶせる a cover (onto something). [JLPT N2]
- **～ておく** — to do something in advance/preparation. "Put it on as a precaution." [JLPT N3]
"""

# Entry 122
explanations[122] = """「丸ごと一個のリンゴを噛み切る。」

---

- **かじる（齧る）** — to bite into, to nibble at, to take a bite (trans. verb). Also figuratively: to have a superficial knowledge of something (e.g. 英語を齧った). Wago. [JLPT N2]
"""

# Entry 123
explanations[123] = """「警察官が犯人を拳銃で射殺した。」

---

- **撃つ（うつ）** — to shoot, to fire (a gun) (trans. verb). Wago. Note homophones: 打つ (to hit/strike), 討つ (to attack/defeat), 射つ (to shoot an arrow/light). Kanji distinguishes meaning. [JLPT N2]
"""

# Entry 124
explanations[124] = """「自転車のペダルを回す。」

---

- **漕ぐ（こぐ）** — to row, to pedal, to paddle (trans. verb). Used for operating a vehicle by physical effort (boat, bicycle). Wago. [JLPT N2]
"""

# Entry 125
explanations[125] = """「床に布団を広げる。」

---

- **敷く（しく）** — to lay out, to spread (a mat, bedding, road, etc.) (trans. verb). Wago. Used for spreading flat objects on a surface. [JLPT N2]
"""

# Entry 126
explanations[126] = """「水や酒をグラスに注ぐ。」

---

- **つぐ（注ぐ）** — to pour (a liquid), to serve a drink (trans. verb). Wago. Commonly written in kana. [JLPT N2]
"""

# Entry 127
explanations[127] = """「先生が生徒にプリントを配布した。」

---

- **配る（くばる）** — to distribute, to hand out (trans. verb). [JLPT N3]
"""

# Entry 128
explanations[128] = """「ボールを投げる。」

---

- **放る（ほうる）** — to throw, to toss (trans. verb). More casual/rough than 投げる（なげる）. Implies a careless or forceful toss. [JLPT N2]
- Note: 放る can also mean "to abandon" (放り出す).
"""

# Entry 129
explanations[129] = """「地面に穴を掘る。」

---

- **掘る（ほる）** — to dig (trans. verb). Used for digging holes, wells, excavating. Wago. [JLPT N3]
"""

# Entry 130
explanations[130] = """「畑に野菜の種を撒く。」

---

- **まく（撒く／蒔く）** — to sow, to scatter, to spread (trans. verb). Used for seeds, powder, salt, etc. Wago. [JLPT N2]
"""

# Entry 131
explanations[131] = """（この項目には例文がありません。）

---

- **計る／測る／量る（はかる）** — three homophonous kanji with different nuances: 計る (to measure time/plan), 測る (to measure dimensions/survey), 量る (to measure quantity/volume). All trans. verbs. [JLPT N2]
"""

# Entry 132
explanations[132] = """「来年の運勢を占ってもらった。」

---

- **占う（うらなう）** — to divine, to tell fortunes, to predict (trans. verb). Wago. The subject performs the fortune-telling; here in ～てもらう form (someone did it for the speaker). [JLPT N2]
- **～てもらう** — receiving a favor. "Had someone tell my fortune." [JLPT N3]
"""

# Entry 133
explanations[133] = """「この紐を引っ張ると電気が点く。」

---

- **引っ張る（ひっぱる）** — to pull, to tug (trans. verb). 引く (to pull) + 張る (to stretch) → to pull firmly. [JLPT N2]
- **～と** — conditional "when/if." Pulling the string causes the light to turn on (natural consequence). [JLPT N4]
"""

# Entry 134
explanations[134] = """「喧嘩して相手の胸を突いた。」

---

- **突く（つく）** — to thrust, to poke, to push (trans. verb). A quick, sharp pushing motion with hand or pointed object. Wago. Distinct from 付く (to attach) and 吐く (to exhale/vomit). [JLPT N2]
"""

# Entry 135
explanations[135] = """「この道をまっすぐ進んで、突き当たったら左に曲がってください。」

---

- **突き当たる（つきあたる）** — to come to an end, to reach a dead end (intrans. verb). 突く (thrust) + 当たる (hit) → to run headlong into something at the end of a path. [JLPT N2]
- **～たら** — conditional "when/after." After reaching the end, turn left. [JLPT N4]
"""

# Entry 136
explanations[136] = """「道で声をかけられて立ち止まった。」

---

- **立ち止まる（たちどまる）** — to stop (walking), to come to a halt (intrans. verb). 立つ (stand) + 止まる (stop). [JLPT N2]
- **～てもらう** is implied in the context: being spoken to by someone, causing the speaker to stop.
"""

# Entry 137
explanations[137] = """「物音がしたので窓に近づいて外を見た。」

---

- **近寄る（ちかよる）** — to approach, to draw near (intrans. verb). 近い (near) + 寄る (approach). Closer nuance than 近づく: implies deliberate, cautious approach. [JLPT N2]
- **～ので** — causal "because/since." [JLPT N4]
"""

# Entry 138
explanations[138] = """「道を横断して反対側に渡った。」

---

- **横切る（よこぎる）** — to cross (trans./intrans. verb). 横 (side/across) + 切る (cut through). Used for crossing a road, sky, etc. [JLPT N2]
"""

# Entry 139
explanations[139] = """「雪道で滑って転んでしまった。」

---

- **転ぶ（ころぶ）** — to fall down, to trip (intrans. verb). Wago. ↔ 転がす (trans., to roll something). [JLPT N3]
- **～てしまう** — completion with regret. "Ended up falling." [JLPT N3]
"""

# Entry 140
explanations[140] = """「道で石につまずいて転んでしまった。」

---

- **つまずく** — to trip, to stumble over something (intrans. verb). Wago. Literal: foot catches on an obstacle. Figurative: to fail at a task. [JLPT N2]
- **～てしまう** — regret/completion. [JLPT N3]
"""

# Entry 141
explanations[141] = """「車に轢かれて骨折した。」

---

- **ひく（轢く）** — to run over (with a vehicle) (trans. verb). This is the "run over" sense, distinct from 引く (to pull) and 弾く (to play an instrument). Wago. Here in passive form ひかれて — adversative passive: the speaker was adversely affected. [JLPT N2]
- **Adversative passive**: The speaker was negatively affected by being run over. Classic use of Japanese indirect passive.
"""

# Entry 142
explanations[142] = """「川に落ちた子供を助けた。」

---

- **おぼれる（溺れる）** — to drown, to be immersed (intrans. verb). Also figurative: to be obsessed with (money, power). Wago. [JLPT N2]
"""

# Entry 143
explanations[143] = """「歯や頭や足などが痛む。」

---

- **痛む（いたむ）** — to ache, to hurt, to feel pain (intrans. verb). Used for physical pain felt by the subject. ↔ 痛める（trans., to damage/injure something). [JLPT N2]
- Note: This is the intransitive sense. The subject is the body part experiencing pain (歯が痛む), not the person.
"""

# Entry 144
explanations[144] = """「インフルエンザにかかって、学校を休んだ。」

---

- **かかる（罹る）** — to catch (a disease), to be affected by (intrans. verb). The kanji 罹る is specific to disease. ↔ 移す (to transmit a disease to someone). [JLPT N3]
- Note: かかる has dozens of kanji and meanings (掛かる、かかる、罹る、被る etc.); context determines which.
"""

# Entry 145
explanations[145] = """「酒に酔う。」

---

- **酔う（よう）** — to get drunk, to be intoxicated (intrans. verb). Wago. The cause of intoxication is marked with に. Also figurative: to be carried away by (atmosphere, mood). [JLPT N2]
"""

# Entry 146
explanations[146] = """「息を吸って吐く。」

---

- **吐く（はく）** — to exhale, to breathe out, to vomit (trans. verb). Wago. Multiple senses: breathing out (息を吐く), vomiting (嘔吐する). [JLPT N3]
"""

# Entry 147
explanations[147] = """「体の調子が悪いので医者に診てもらおう。」

---

- **診る（みる）** — to examine (a patient), to diagnose (trans. verb). Specifically medical examination. ↔ 診せる (to show oneself for examination, rare). [JLPT N2]
- **～てもらう** — to receive the favor of someone doing something. "Have the doctor examine me." [JLPT N3]
- **～よう** — volitional form. "Let me..." / "I'll..." [JLPT N4]
"""

# Entry 148
explanations[148] = """「入院している友達をみんなで見舞った。」

---

- **見舞う（みまう）** — to visit (someone who is ill/in trouble), to call on (trans. verb). 見舞い (noun) is a common collocation. [JLPT N2]
"""

# Entry 149
explanations[149] = """「会社で働いている。」

---

- **勤める（つとめる）** — to work for (a company/organization), to be employed (intrans. verb). ↔ 勤まる (to be able to fulfill the duties). Note homophone: 努める (to endeavor). [JLPT N3]
"""

# Entry 150
explanations[150] = """「大学時代はアルバイトで学費を稼いだ。」

---

- **稼ぐ（かせぐ）** — to earn (money), to make a living (trans. verb). Wago. Implies working hard to earn. [JLPT N2]
"""

# Entry 151
explanations[151] = """「買い物代金をクレジットカードで支払う。」

---

- **支払う（しはらう）** — to pay (money, expenses) (trans. verb). Kango-derived compound: 支 (support) + 払う (pay). Formal counterpart to 払う. [JLPT N2]
"""

# Entry 152
explanations[152] = """「着払いの荷物を代金を払って受け取った。」

---

- **受け取る（うけとる）** — to receive, to accept, to take delivery of (trans. verb). 受ける + 取る. Can also mean "to interpret/understand." [JLPT N2]
- **着払い** — collect on delivery (payment upon receipt). [JLPT N2]
"""

# Entry 153
explanations[153] = """「今学期の授業料を銀行に払い込んだ。」

---

- **払い込む（はらいこむ）** — to pay (into an account), to make a payment (trans. verb). 払う + 込む (into). Specifically used for paying money into a bank account or through a payment system. [JLPT N2]
"""

# Entry 154
explanations[154] = """「電話会社が過剰請求額を利用者の口座に払い戻した。」

---

- **払い戻す（はらいもどす）** — to refund, to reimburse (trans. verb). 払う + 戻す (return). Money is returned to the payer. [JLPT N2]
- **過大請求** — overcharging, excessive billing. Kango. [JLPT N2]
"""

# Entry 155
explanations[155] = """「銀行から生活費を引き出した。」

---

- **引き出す（ひきだす）** — to withdraw (money), to draw out (trans. verb). 引く + 出す. Used for bank withdrawals, drawing out information/potential. [JLPT N2]
"""

# Entry 156
explanations[156] = """「株取引で100万円の利益を得た。」

---

- **もうかる（儲かる）** — to make a profit, to be profitable (intrans. verb). ↔ もうける (trans.). The subject is the person who benefits, or the business that is profitable. [JLPT N2]
"""

# Entry 157
explanations[157] = """「彼は株取引で100万円を儲けた。」

---

- **もうける（儲ける）** — to make a profit, to earn (trans. verb). ↔ もうかる (intrans.). Note: can also mean "to take advantage of someone" in a negative sense. [JLPT N2]
"""

# Entry 158
explanations[158] = """「景気が悪化して、失業率が上昇した。」

---

- **落ち込む（おちこむ）** — to fall, to drop, to decline; to become depressed (intrans. verb). Literal: to fall into something. In economics: to slump, to decline. [JLPT N2]
- Note: Semantic extension from physical "fall into a depression" to economic downturn and emotional depression.
"""

# Entry 159
explanations[159] = """「このCDは100万枚が売れたそうだ。」

---

- **売れる（うれる）** — to sell (well), to be in demand (intrans. verb). Potential-adjacent form of 売る but has become lexicalized as an independent intransitive verb. ↔ 売る (trans.). [JLPT N3]
- **～そうだ** — hearsay. "I hear that..." [JLPT N3]
"""

# Entry 160
explanations[160] = """「そのコンサートのチケットは1時間で完売したそうだ。」

---

- **売り切れる（うりきれる）** — to sell out (intrans. verb). 売る + 切れる (to be completely used up/exhausted). ↔ 売り切る (trans., to sell everything). [JLPT N2]
"""

# Entry 161
explanations[161] = """「磁石同士がくっついて離れない。」

---

- **くっ付く（くっつく）** — to stick to, to adhere to (intrans. verb). 付く with emphatic くっ prefix. ↔ くっ付ける (trans.). [JLPT N2]
"""

# Entry 162
explanations[162] = """「机と机をくっ付けて並べた。」

---

- **くっ付ける（くっつける）** — to attach, to stick together (trans. verb). ↔ くっ付く (intrans.). [JLPT N2]
"""

# Entry 163
explanations[163] = """「液体にゼラチンを入れると固まってゼリーになる。」

---

- **固まる（かたまる）** — to harden, to solidify, to set (intrans. verb). ↔ 固める (trans.). Also figurative: to be finalized, to be settled (e.g. 計画が固まる). [JLPT N2]
"""

# Entry 164
explanations[164] = """「ジュースを固めてゼリーを作った。」

---

- **固める（かためる）** — to harden, to solidify (trans. verb). ↔ 固まる (intrans.). Also figurative: to strengthen, to consolidate (e.g. 意志を固める). [JLPT N2]
"""

# Entry 165
explanations[165] = """「洗濯したらセーターが縮んでしまった。」

---

- **縮む（ちぢむ）** — to shrink, to contract (intrans. verb). ↔ 縮める (trans.). [JLPT N2]
- **～てしまう** — regret. "Unfortunately shrank." [JLPT N3]
"""

# Entry 166
explanations[166] = """「マラソン世界記録は徐々に短くなっている。」

---

- **縮まる（ちぢまる）** — to be shortened, to decrease (intrans. verb). ↔ 縮める (trans.). Used for distances, time gaps, differences narrowing. Distinct from 縮む (physical shrinkage). [JLPT N2]
"""

# Entry 167
explanations[167] = """「ズボンが長すぎたので、裾を少し短くした。」

---

- **縮める（ちぢめる）** — to shorten, to shrink (trans. verb). ↔ 縮む (intrans.). Active shortening of something. [JLPT N2]
- **丈（たけ）** — length (of clothing). [JLPT N2]
"""

# Entry 168
explanations[168] = """「台風で船が海に沈んだ。」

---

- **沈む（しずむ）** — to sink, to submerge (intrans. verb). ↔ 沈める (trans.). Also figurative: to become gloomy (気分が沈む), to set (太陽が沈む). [JLPT N2]
"""

# Entry 169
explanations[169] = """「台風が船を海に沈めてしまった。」

---

- **沈める（しずめる）** — to sink (something), to submerge (trans. verb). ↔ 沈む (intrans.). [JLPT N2]
- **Adversative passive nuance**: The typhoon (natural force) is the agent causing the ship to sink. が + 沈める treats the typhoon as an active agent.
"""

# Entry 170
explanations[170] = """「電灯から紐がぶら下がっている。」

---

- **下がる（さがる）** — to hang down, to lower, to descend (intrans. verb). ↔ 下げる (trans.). Many senses: to decrease, to step back, to improve, etc. [JLPT N3]
"""

# Entry 172
explanations[172] = """「ボールが床の上を転がる。」

---

- **転がる（ころがる）** — to roll, to fall over, to tumble (intrans. verb). ↔ 転がす (trans.). Also figurative: to be readily available (お金が転がっている), to change direction (商売を転がる). [JLPT N2]
"""

# Entry 173
explanations[173] = """「ボーリングの球を転がしてピンを倒す。」

---

- **転がす（ころがす）** — to roll (something), to turn over (trans. verb). ↔ 転がる (intrans.). [JLPT N2]
"""

# Entry 174
explanations[174] = """「地震で塀が傾いてしまった。」

---

- **傾く（かたむく／たむく）** — to tilt, to lean, to slope (intrans. verb). Note: the reading here is かたむく, not たむく (the data file entry may have a typo; 傾く standard reading is かたむく). ↔ 傾ける (trans.). Also figurative: to decline (景気が傾く). [JLPT N2]
"""

# Entry 175
explanations[175] = """「その子はわからないことがあると、首をかしげる癖がある。」

---

- **傾ける（かたむける／たむける）** — to tilt, to lean, to bend (trans. verb). Note: the reading here is かたむける. 首を傾げる is a set phrase meaning "to tilt one's head (in puzzlement)." ↔ 傾く (intrans.). [JLPT N2]
- **くせ（癖）** — habit, tendency. [JLPT N3]
"""

# Entry 176
explanations[176] = """「この書類の記入が終わったら、裏返して机の上に置いてください。」

---

- **裏返す（うらがえす）** — to turn over, to flip (trans. verb). 裏 (back/reverse) + 返す (to return/turn). ↔ 裏返る (intrans.). [JLPT N2]
"""

# Entry 177
explanations[177] = """「兄の部屋はいつも散らかっている。」

---

- **散らかる（ちらかる）** — to be scattered about, to be in a mess (intrans. verb). ↔ 散らかす (trans.). Describes a state of disorder. [JLPT N2]
"""

# Entry 178
explanations[178] = """「うちの子はすぐに部屋を散らかしてしまう。」

---

- **散らかす（ちらかす）** — to scatter, to make a mess of (trans. verb). ↔ 散らかる (intrans.). [JLPT N2]
- **～てしまう** — completion, often with speaker's frustration. [JLPT N3]
"""

# Entry 179
explanations[179] = """「路上にごみが散らばっている。」

---

- **散らばる（ちらばる）** — to be scattered, to be strewn about (intrans. verb). Similar to 散らかる but focuses more on individual items being dispersed across a surface rather than a general state of messiness. [JLPT N2]
"""

# Entry 180
explanations[180] = """「キャベツを刻んで炒める。」

---

- **刻む（きざむ）** — to chop, to mince, to carve (trans. verb). Wago. Also figurative: to mark time (時を刻む), to engrave in memory (心に刻む). [JLPT N2]
- **炒める（いためる）** — to stir-fry. [JLPT N3]
"""

# Entry 181
explanations[181] = """「コートの裾が電車のドアに挟まって抜け出せない。」

---

- **挟まる（はさまる）** — to be caught/sandwiched between things (intrans. verb). ↔ 挟む (trans.). [JLPT N2]
- **抜ける** — to get free, to escape. Here negative 抜けない: cannot get free. [JLPT N3]
"""

# Entry 182
explanations[182] = """「電車のドアに挟まれないようご注意ください。」

---

- **挟む（はさむ）** — to sandwich, to place between, to catch between (trans. verb). ↔ 挟まる (intrans.). Here in passive: ～にはさまれる (to be caught in). [JLPT N3]
- **～ようご注意ください** — formal caution. "Please be careful not to..." [JLPT N3]
"""

# Entry 183
explanations[183] = """「箱が落ちて、中のケーキが潰れてしまった。」

---

- **つぶれる（潰れる）** — to be crushed, to be squashed (intrans. verb). ↔ つぶす (trans.). Also figurative: to go bankrupt (会社が潰れる). [JLPT N2]
"""

# Entry 184
explanations[184] = """「茹でたジャガイモを潰してサラダを作った。」

---

- **つぶす（潰す）** — to crush, to mash, to destroy (trans. verb). ↔ つぶれる (intrans.). [JLPT N2]
"""

# Entry 185
explanations[185] = """「木にぶつかって車が凹んだ。」

---

- **へこむ（凹む）** — to dent, to cave in (intrans. verb). ↔ へこます (trans., less common). Also figurative: to feel discouraged (気持ちがへこむ). [JLPT N2]
"""

# Entry 186
explanations[186] = """「靴の紐が解けた。」

---

- **ほどける（解ける）** — to come undone, to untie itself, to loosen (intrans. verb). ↔ ほどく (trans.). Also used for: mysteries solved (謎が解ける), contracts expired (契約が解ける). [JLPT N2]
"""

# Entry 187
explanations[187] = """「荷物の紐を解いて中身を出す。」

---

- **ほどく（解く）** — to untie, to undo, to solve (trans. verb). ↔ ほどける (intrans.). [JLPT N2]
"""

# Entry 188
explanations[188] = """「害虫のせいで木が枯れてしまった。」

---

- **枯れる（かれる）** — to wither, to dry up (intrans. verb). ↔ 枯らす (trans.). Also figurative: inspiration depleted (アイデアが枯れる). [JLPT N2]
- Note: The data shows れる as reading, which appears to be a typo. The correct reading is かれる.
"""

# Entry 189
explanations[189] = """「病気が発生して、多くの木を枯らしてしまった。」

---

- **枯らす（からす）** — to wither (something), to dry up (trans. verb). ↔ 枯れる (intrans.). [JLPT N2]
- Note: The data shows らす as reading, which appears to be a typo. The correct reading is からす.
"""

# Entry 190
explanations[190] = """「生魚は傷みやすいから、早く食べた方がいい。」

---

- **傷む（いたむ）** — to go bad, to spoil, to rot (intrans. verb). This is a different sense from 痛む (to feel pain). Same reading, different kanji and meaning. ↔ 傷める (trans., to damage/spoil something). [JLPT N2]
- **～やすい** — prone to, easily. "Spoils easily." [JLPT N3]
"""

# Entry 191
explanations[191] = """「朝に干した洗濯物がまだ湿っている。」

---

- **湿る（しめる）** — to become damp, to be moist (intrans. verb). ↔ 湿らす (trans., to moisten). Note reading: しめる not しめると. [JLPT N2]
- **干す（ほす）** — to dry in the sun, to air out. [JLPT N3]
"""

# Entry 192
explanations[192] = """「水が氷になる。」

---

- **凍る（こおる）** — to freeze (intrans. verb). ↔ 凍らす (trans., to freeze something). Also figurative: 空気が凍る (the atmosphere is tense). [JLPT N2]
"""

# Entry 193
explanations[193] = """「寒さで手足がぶるぶる震えた。」

---

- **震える（ふるえる）** — to tremble, to shiver, to shake (intrans. verb). Used for involuntary trembling due to cold, fear, excitement. ↔ 震わす (trans., to cause to tremble, rare). [JLPT N2]
- **ぶるぶる** — onomatopoeia for trembling. [JLPT N3]
"""

# Entry 194
explanations[194] = """「空に太陽が輝いている。」

---

- **輝く（かがやく）** — to shine, to sparkle, to glitter (intrans. verb). Wago. Also figurative: to excel, to stand out. [JLPT N2]
"""

# Entry 195
explanations[195] = """「大雨で川の水があふれた。」

---

- **あふれる（溢れる）** — to overflow, to flood (intrans. verb). Also figurative: to be full of (emotion, vitality). ↔ 溢れさせる (trans., rare; no direct transitive counterpart is commonly used). [JLPT N2]
"""

# Entry 196
explanations[196] = """「作り過ぎて料理が余ってしまった。」

---

- **余る（あまる）** — to remain, to be left over, to exceed (intrans. verb). Wago. Also: 余っている (is available/free). [JLPT N3]
- **～てしまう** — regret. "Unfortunately there are leftovers." [JLPT N3]
"""

# Entry 197
explanations[197] = """「彼女は背が高いので目立つ。」

---

- **目立つ（めだつ）** — to stand out, to be conspicuous (intrans. verb). 目 (eye) + 立つ (stand). Can be positive or negative depending on context. [JLPT N3]
"""

# Entry 198
explanations[198] = """「このビルの屋上から街を見下ろすことができる。」

---

- **見下ろす（みおろす）** — to look down on, to overlook (from above) (trans. verb). 見る + 下ろす. Also figurative: to look down upon someone (as superior). [JLPT N2]
- **～られる** — potential form of る-verb. "Can look down on." [JLPT N4]
"""

# Entry 199
explanations[199] = """「国同士が領土をめぐって戦う。」

---

- **戦う／闘う（たたかう）** — to fight, to battle, to war (intrans. verb). 戦う: military/large-scale conflict. 闘う: personal struggle, competition, or fighting an opponent/illness. Both read たたかう. [JLPT N2]
- **～をめぐって** — concerning, over, around (a topic of dispute). "Fighting over territory." [JLPT N2]
"""

# Entry 200
explanations[200] = """「試合に負ける。」

---

- **敗れる（やぶれる）** — to be defeated, to lose (intrans. verb). ↔ 破る (trans., to defeat/break). More formal than 負ける（まける）. [JLPT N2]
"""

# Entry 201
explanations[201] = """「犯人は海外に逃げたようだ。」

---

- **逃げる（にげる）** — to escape, to run away, to flee (intrans. verb). ↔ 逃がす (trans., to let escape). [JLPT N3]
- **～らしい** — conjecture. "It seems that..." [JLPT N3]
"""

# Entry 202
explanations[202] = """「魚を釣ったが、小さかったので逃がしてやった。」

---

- **逃がす（にがす）** — to let escape, to release (trans. verb). ↔ 逃げる (intrans.). Here 逃がしてやった: "let it go" with a nuance of doing it as a favor/kindness (～てやる = doing something for a subordinate/animal). [JLPT N2]
- **～てやる** — doing something for someone/something of lower status. With animals, shows the speaker's benevolence. [JLPT N3]
"""

# Entry 203
explanations[203] = """「忘れ物をしたのに気付いて、家に戻った。」

---

- **戻る（もどる）** — to return, to go back (intrans. verb). ↔ 戻す (trans.). Physical return to a previous location or state. [JLPT N3]
- **～のに気付いて** — "noticing that..." [JLPT N3]
"""

# Entry 204
explanations[204] = """「物は元あった場所に戻しなさい。」

---

- **戻す（もどす）** — to put back, to restore, to return (something) (trans. verb). ↔ 戻る (intrans.). [JLPT N3]
- **～なさい** — polite command. Parent/teacher to child/student. [JLPT N4]
"""

# Entry 205
explanations[205] = """「彼の薬指に指輪がはまっていた。」

---

- **はまる（嵌まる）** — to fit into, to be inset (intrans. verb). ↔ はめる (trans.). Also figurative: to get hooked on something (ギャンブルにはまる). [JLPT N2]
"""

# Entry 206
explanations[206] = """「寒いので、上着のボタンを全部留めた。」

---

- **はめる（嵌める）** — to put on (a ring), to fasten (a button), to fit into place (trans. verb). ↔ はまる (intrans.). [JLPT N2]
"""

# Entry 207
explanations[207] = """「壊れやすいものですから、丁寧な扱い方をしてください。」

---

- **扱う（あつかう）** — to handle, to deal with, to treat (trans. verb). [JLPT N2]
- **～ものですから** — explanatory/emphatic. "Because it is..." [JLPT N2]
"""

# Entry 208
explanations[208] = """「将来は子供の教育に関わる仕事がしたい。」

---

- **関わる（かかわる）** — to be involved in, to be connected with, to concern (intrans. verb). ↔ 関する (to concern, suru-verb). Also: 命に関わる (life-threatening). [JLPT N2]
"""

# Entry 209
explanations[209] = """「選手たちがゴールを目指して走り出した。」

---

- **目指す（めざす）** — to aim for, to head toward (trans. verb). 目 (target) + 指す (to point). Used for goals, destinations, aspirations. [JLPT N2]
"""

# Entry 210
explanations[210] = """「8月末に海外赴任でヨーロッパへ出発する予定だ。」

---

- **立つ／発つ（たつ）** — to depart, to leave (for a destination) (intrans. verb). This is a different sense from 立つ (to stand). The kanji 発つ specifically means departure. [JLPT N2]
- **海外赴任（かいがいふにん）** — overseas assignment/posting. Kango. [JLPT N1]
"""

# Entry 211
explanations[211] = """「その店はいつも客を笑顔で迎える。」

---

- **迎える（むかえる）** — to welcome, to receive, to greet (trans. verb). Kango. Also: a new year/season arrives (新年を迎える), to pick someone up. [JLPT N2]
"""

# Entry 212
explanations[212] = """「自分の持っている力を十分に出してください。」

---

- **持てる（もてる）** — potential form of 持つ. "To be able to have/use." Here: "all the strength/resources that one possesses." [JLPT N3]
- **発揮する（はっきする）** — to demonstrate, to exert, to display (one's ability). [JLPT N2]
"""

# Entry 213
explanations[213] = """「人生はよく旅にたとえられる。」

---

- **たとえる（喩える）** — to compare (to), to use as a metaphor (trans. verb). Here in passive: たとえられる (is compared to). "Life is often compared to a journey." [JLPT N2]
- **～によく** — "often." Life is often metaphorically described as a journey. [JLPT N3]
"""

# Entry 214
explanations[214] = """「できるだけ問題の解決に努めたい。」

---

- **努める（つとめる）** — to endeavor, to strive, to make an effort (intrans. verb). Kango. Note homophone: 勤める (to work for). [JLPT N2]
- **～たい** — desire. "I want to try my best." [JLPT N4]
"""

# Entry 215
explanations[215] = """「こんな難しい役が私に務まるだろうか。」

---

- **務まる（つとまる）** — to be capable of fulfilling (a role/duty) (intrans. verb). ↔ 務める (to serve in a role). Potential-adjacent: whether one is up to a task. [JLPT N2]
- **～だろうか** — self-questioning doubt. "I wonder if I can handle it." [JLPT N3]
"""

# Entry 216
explanations[216] = """「会議で議長を務めた。」

---

- **務める（つとめる）** — to serve in (a role/position), to act as (intrans. verb). ↔ 務まる. Note homophone: 努める (to endeavor). [JLPT N2]
- **議長（ぎちょう）** — chairperson, chairman. Kango. [JLPT N2]
"""

# Entry 217
explanations[217] = """「仕事が忙しくなって、飛行機の予約を取り消した。」

---

- **取り消す（とりけす）** — to cancel, to revoke, to annul (trans. verb). 取る + 消す. [JLPT N2]
"""

# Entry 218
explanations[218] = """「今日は6時までに仕事を終えて退社するつもりだ。」

---

- **終える（おえる）** — to finish, to complete (trans. verb). Unlike 終わる (intrans.), 終える requires an object and implies active completion. ↔ 終わる (intrans.). [JLPT N2]
- **退社する（たいしゃする）** — to leave work (for the day). Kango. [JLPT N2]
- **～つもりだ** — intention. "I intend to..." [JLPT N3]
"""

# Entry 219
explanations[219] = """「意識不明の母に声をかけて呼びかけた。」

---

- **呼びかける（よびかける）** — to call out to, to appeal to, to address (trans. verb). 呼ぶ + かける. Can mean: (1) to call out to someone to get their attention, (2) to make a public appeal/call for action. [JLPT N2]
"""

# Entry 220
explanations[220] = """「学費を未払いだったので、教務室に呼び出された。」

---

- **呼び出す（よびだす）** — to call out, to summon, to call (on the phone) (trans. verb). 呼ぶ + 出す. Here in passive: 呼び出された (was summoned). [JLPT N2]
- **学費を払っていない** — not having paid tuition fees. Reason for the summons. [JLPT N3]
- **事務局（じむきょく）** — administrative office (of a school/university). Kango. [JLPT N2]
"""

# Write to JSON
output = []
for idx in range(101, 221):
    if idx in explanations:
        output.append({
            "index": idx,
            "explanation": explanations[idx].strip()
        })

with open(r"D:\n2Prepare\materialToLearn\N2Vocabulary\output\explanations_unit02_all.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Unit 2: wrote {len(output)} explanations")
