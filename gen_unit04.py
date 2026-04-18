import json

entries = [
  {
    "index": 271,
    "explanation": "**\"I heard Nakamura won the lottery three times in a row. What a lucky person.\"**\n\n---\n\n- **運（うん）** — noun, \"luck, fortune.\" Kango (from 運ぶ, originally \"to carry\" — fate is \"carried\" to you). Semantic drift: from physical transport to abstract destiny. [JLPT N2]\n- **3回（さんかい）続（つづ）けて** — 続ける (他動詞, \"to continue\"). Counterpart 自動詞: 続く. \"Three times consecutively.\" [JLPT N4]\n- **宝（たから）くじ** — noun, \"lottery.\" 宝 = treasure + くじ = draw. Wago+kango blend. [JLPT N2]\n- **当た（あた）った** — 当たる (自動詞, \"to hit, to win\"). Counterpart 他動詞: 当てる. 「宝くじに当たる」= win the lottery. [JLPT N2]\n- **〜そうだ** — hearsay: \"I heard that...\" [JLPT N4]\n- **なんて〜だろう** — exclamatory: \"What a lucky person!\" [JLPT N3]"
  },
  {
    "index": 272,
    "explanation": "**My mother has good intuition — even if I lie, she sees through it right away.**\n\n---\n\n- **勘（かん）** — noun, \"intuition, hunch, sixth sense.\" Kango. Relies on instinctive judgment rather than logic. [JLPT N2]\n- **〜がいい** — 「勘がいい」= \"to have good intuition.\" Opposite: 勘が悪い. [JLPT N2]\n- **うそをつく** — set phrase (他動詞), \"to tell a lie.\" Counterpart 自動詞: none. [JLPT N4]\n- **ばれてしまう** — ばれる (自動詞, \"to be exposed, found out\") + てしまう (completion). [JLPT N2]\n- **すぐ** — adverb, \"immediately.\" [JLPT N4]"
  },
  {
    "index": 273,
    "explanation": "**My hands and feet went numb from the cold, and I lost all feeling in them.**\n\n---\n\n- **感覚（かんかく）** — kango noun, \"sense, feeling, sensation.\" Physical sensation or abstract \"sense.\" [JLPT N2]\n- **冷（ひ）えて** — 冷える (自動詞, \"to grow cold, to chill\"). Counterpart 他動詞: 冷ます. [JLPT N3]\n- **手足（てあし）** — noun, \"hands and feet / limbs.\" Wago. [JLPT N3]\n- **なくなってしまった** — なくなる (自動詞, \"to disappear, be lost\") + てしまった (completion). [JLPT N4]"
  },
  {
    "index": 274,
    "explanation": "**I had a nerve pulled (root canal) because of a toothache.**\n\n---\n\n- **神経（しんけい）** — kango noun, \"nerve; sensitivity.\" Here: dental nerve. Extended: mental sensitivity (神経質 = oversensitive). [JLPT N2]\n- **神経を抜（ぬ）く** — set phrase (他動詞), \"to extract a nerve.\" 抜く = pull out. Counterpart 自動詞: 抜ける. [JLPT N2]\n- **虫歯（むしば）** — noun, \"cavity.\" 虫 = insect (folk belief) + 歯 = tooth. Wago. [JLPT N2]\n- **〜ので** — reason/cause particle, more objective than から. [JLPT N5]"
  },
  {
    "index": 275,
    "explanation": "**I have absolutely no memory of that time. / The girl had no memory of anything before the accident.**\n\n---\n\n- **記憶（きおく）** — kango noun, \"memory, recollection.\" 記 = record + 憶 = recall. Can be suru-verb. [JLPT N2]\n- **記憶にない** — set pattern, \"to have no memory of.\" に marks location of existence. [JLPT N2]\n- **全く（まったく）...ない** — 「全く」= \"not at all.\" Negative polarity item. [JLPT N4]\n- **記憶していなかった** — 記憶する (suru-verb, 他動詞, \"to remember\") + ていなかった (past negative progressive). [JLPT N2]"
  },
  {
    "index": 276,
    "explanation": "**I was worried about my mother who had surgery, so I went to check on her many times.**\n\n---\n\n- **様子（ようす）** — noun, \"state, condition, situation, appearance.\" [JLPT N2]\n- **様子を見（み）に行く** — set phrase, \"to go check on.\" 様子を見る + に + 行く (purpose). [JLPT N2]\n- **手術（しゅじゅつ）を受（う）けた** — 手術 = surgery + 受ける (他動詞, \"to receive, undergo\"). Counterpart 自動詞: 受けられる (potential/passive). [JLPT N3]\n- **心配（しんぱい）で** — な-adj, \"worried\" + で (reason). [JLPT N4]\n- **何度（なんど）も** — adverb, \"many times, repeatedly.\" [JLPT N4]"
  },
  {
    "index": 277,
    "explanation": "**This shop has a nice atmosphere. / An {intellectual / artistic / religious} atmosphere.**\n\n---\n\n- **雰囲気（ふんいき）** — kango noun, \"atmosphere, mood, ambience.\" 雰 + 囲 + 気 = \"surrounding air/spirit.\" Note: commonly misread as ふいんき (metathesis); correct is ふんいき. [JLPT N2]\n- **知的（ちてきな）** — な-adj, \"intellectual.\" [JLPT N2]\n- **芸術的（げいじゅつてきな）** — な-adj, \"artistic.\" [JLPT N2]\n- **宗教的（しゅうきょうてきな）** — な-adj, \"religious.\" [JLPT N2]"
  },
  {
    "index": 278,
    "explanation": "**I watched kabuki for the first time and was drawn to its appeal. / She is an attractive actress.**\n\n---\n\n- **魅力（みりょく）** — kango noun, \"charm, appeal.\" 魅 = enchant + 力 = power. \"The power to enchant.\" [JLPT N2]\n- **魅力に引（ひ）かれた** — 引かれる (自動詞, passive of 引く, \"to be drawn to\"). Counterpart 他動詞: 引く. [JLPT N2]\n- **初めて（はじめて）** — adverb, \"for the first time.\" [JLPT N4]\n- **歌舞伎（かぶき）** — noun, \"kabuki.\" [JLPT N1]\n- **魅力的（みりょくてきな）** — な-adj, \"attractive, charming.\" [JLPT N2]\n- **女優（じょゆう）** — kango noun, \"actress.\" 女 = female + 優 = actor. [JLPT N3]"
  },
  {
    "index": 279,
    "explanation": "**My father seems to be in a bad mood — he does not even answer no matter what I ask.**\n\n---\n\n- **機嫌（きげん）** — noun, \"mood, temper.\" Wago. 機嫌がいい/悪い. [JLPT N2]\n- **〜らしく** — らしい (\"seems like\") + く (adverbial reason). [JLPT N3]\n- **何（なに）を聞いても** — 聞く (他動詞, \"to ask\") + ても (concessive) + も (emphasis). \"No matter what I ask.\" Counterpart 自動詞: 聞こえる. [JLPT N5]\n- **返事（へんじ）もしない** — 返事 = reply + も (negative emphasis) + しない. Not even a reply. [JLPT N4]"
  },
  {
    "index": 280,
    "explanation": "**I am not very interested in sports. / The public interest in politics is growing.**\n\n---\n\n- **関心（かんしん）** — kango noun, \"interest, concern.\" 関 = connect + 心 = mind. Deeper than 興味 (きょうみ). Takes に for the topic. [JLPT N2]\n- **関心が高（たか）まっている** — 高まる (自動詞, \"to rise, intensify\"). Counterpart 他動詞: 高める. [JLPT N2]\n- **国民（こくみん）** — kango noun, \"citizens, the people.\" [JLPT N2]\n- **政治（せいじ）** — kango noun, \"politics.\" [JLPT N3]"
  },
  {
    "index": 281,
    "explanation": "**I have the motivation to work, but I cannot find a job. / He does not seem to have any motivation to study.**\n\n---\n\n- **意欲（いよく）** — kango noun, \"motivation, willingness, drive.\" 意 = intention + 欲 = desire. [JLPT N2]\n- **〜のだが** — の (explanatory) + だ (copula) + が (adversative). Softens while implying a problem. [JLPT N3]\n- **仕事（しごと）が見（み）つからない** — 見つかる (自動詞, \"to be found\"). Counterpart 他動詞: 見つける. [JLPT N3]\n- **意欲が感（かん）じられない** — 感じる (他動詞, \"to feel, sense\") + られない (negative potential). [JLPT N3]"
  },
  {
    "index": 282,
    "explanation": "**I threw the ball with all my strength. / The ruling party made every effort to pass the bill.**\n\n---\n\n- **全力（ぜんりょく）** — kango noun, \"full strength, all one's power.\" 全 = all + 力 = power. [JLPT N2]\n- **全力で投（な）げた** — 投げる (他動詞, \"to throw\"). Counterpart 自動詞: 投げられる. [JLPT N3]\n- **与党（よとう）** — kango noun, \"ruling party.\" Opposite: 野党（やとう, opposition). [JLPT N2]\n- **法案（ほうあん）の成立（せいりつ）** — 法案 = bill + 成立 = enactment. [JLPT N2]\n- **全力を尽（つく）した** — 尽くす (他動詞, \"to exhaust, devote fully\"). Counterpart 自動詞: 尽くされる. 「全力を尽くす」= do one's utmost. [JLPT N2]"
  },
  {
    "index": 283,
    "explanation": "**That student finally got serious and started studying. / My father is scary when he gets truly angry.**\n\n---\n\n- **本気（ほんき）** — noun, \"seriousness, earnestness.\" 本 = real + 気 = spirit. Opposite: 冗談（じょうだん, joke). [JLPT N2]\n- **本気になる** — set phrase, \"to get serious.\" なる (自動詞) marks transition. [JLPT N2]\n- **やっと** — adverb, \"finally, at last\" (implies difficulty). [JLPT N3]\n- **勉強（べんきょう）し始（はじ）めた** — 勉強する + 始める (他動詞, \"to start\"). Counterpart 自動詞: 始まる. [JLPT N4]\n- **本気で怒（おこ）る** — 本気で (adverbial, \"in earnest\") + 怒る (自動詞, \"to get angry\"). Counterpart 他動詞: 怒らせる. [JLPT N3]"
  },
  {
    "index": 284,
    "explanation": "**I hit my head and lost consciousness. / I was fully conscious, but my body would not move.**\n\n---\n\n- **意識（いしき）** — kango noun, \"consciousness, awareness.\" Medical or general awareness. [JLPT N2]\n- **意識を失（うしな）った** — 失う (他動詞, \"to lose\"). Counterpart 自動詞: 失われる. [JLPT N2]\n- **頭（あたま）を打（う）って** — 打つ (他動詞, \"to hit, strike\"). Counterpart 自動詞: 打たれる. [JLPT N4]\n- **意識ははっきりしていた** — はっきり (adverb, \"clearly\") + していた. Consciousness was clear. [JLPT N3]\n- **体（からだ）が動（うご）かなかった** — 動く (自動詞, \"to move\"). Counterpart 他動詞: 動かす. [JLPT N4]"
  },
  {
    "index": 285,
    "explanation": "**I was deeply moved when the professor, who rarely praises people, praised me.**\n\n---\n\n- **感激（かんげき）する** — kango suru-verb, 自動詞, \"to be deeply moved, thrilled.\" 感 = feeling + 激 = intense. Stronger than 感動. [JLPT N2]\n- **めったに...ない** — めったに + negative = \"rarely, hardly ever.\" [JLPT N4]\n- **教授（きょうじゅ）** — kango noun, \"professor.\" [JLPT N3]\n- **ほめられて** — ほめる (他動詞, \"to praise\") + られる (passive) + て (reason). Counterpart 自動詞: ほめられる. [JLPT N4]"
  },
  {
    "index": 286,
    "explanation": "**I sympathize with those who are suffering. / To sympathize with the victim {○sympathize / ×is sympathy}.**\n\n---\n\n- **同情（どうじょう）する** — kango suru-verb, 他動詞, \"to sympathize with.\" 同 = same + 情 = emotion. Takes に for target. Note: suru-verb (する), NOT copula (×同情だ). [JLPT N2]\n- **苦（くる）しんでいる人々（ひとびと）** — 苦しむ (自動詞, \"to suffer\") + ている. Counterpart 他動詞: 苦しめる. [JLPT N3]\n- **被害者（ひがいしゃ）** — kango noun, \"victim.\" Opposite: 加害者（かがいしゃ, perpetrator). [JLPT N2]"
  },
  {
    "index": 287,
    "explanation": "**Many people agreed with my opinion. / To agree with the proposal {○agree / ×is agreement}.**\n\n---\n\n- **同意（どうい）する** — kango suru-verb, 他動詞, \"to agree with, consent to.\" 同 = same + 意 = opinion. Takes に. Note: suru-verb (する), NOT copula (×同意だ). [JLPT N2]\n- **大勢（おおぜい）の人（ひと）** — 大勢 = many people. [JLPT N3]\n- **意見（いけん）** — kango noun, \"opinion.\" [JLPT N3]\n- **提案（ていあん）** — kango noun, \"proposal.\" 提 = present + 案 = plan. [JLPT N2]"
  },
  {
    "index": 288,
    "explanation": "**I also felt the same way about what Nakayama said.**\n\n---\n\n- **同感（どうかん）する** — kango suru-verb, 自動詞, \"to feel the same way, share the same sentiment.\" 同 = same + 感 = feeling. Unlike 同意 (agreeing with a proposal), 同感 is about sharing emotional response/sentiment. Takes に. [JLPT N2]\n- **中山（なかやま）さんの話（はなし）** — \"what Nakayama said / Nakayama's story.\" [JLPT N5]"
  },
  {
    "index": 289,
    "explanation": "**The confrontation between the ruling party and the opposition in the Diet has intensified.**\n\n---\n\n- **対立（たいりつ）する** — kango suru-verb/noun, 自動詞, \"to be in opposition, to conflict.\" 対 = facing + 立 = stand. Standing on opposite sides. [JLPT N2]\n- **国会（こっかい）** — kango noun, \"the Diet.\" [JLPT N2]\n- **与党（よとう）と野党（やとう）** — 与党 = ruling party vs. 野党 = opposition. 野 = field/wild (outside of power). [JLPT N2]\n- **激（はげ）しくなった** — 激しい (い-adj, \"intense, fierce\") + く + なった (became). [JLPT N3]"
  },
  {
    "index": 290,
    "explanation": "**I assert workers' rights against the company side. / I boldly stated my claim at the meeting.**\n\n---\n\n- **主張（しゅちょう）する** — kango suru-verb, 他動詞, \"to assert, to claim.\" 主 = main + 張 = stretch/assert. [JLPT N2]\n- **会社側（かいしゃがわ）** — 会社 + 側 = side. \"The company side.\" [JLPT N3]\n- **労働者（ろうどうしゃ）の権利（けんり）** — 労働者 = worker + 権利 = rights. [JLPT N2]\n- **主張（しゅちょう）** — noun: \"claim, assertion, position.\" [JLPT N2]\n- **堂々（どうどう）と述（の）べた** — 堂々と (adverb, \"boldly, with dignity\") + 述べる (他動詞, \"to state, express\"). Counterpart 自動詞: 述べられる. [JLPT N2]"
  },
  {
    "index": 291,
    "explanation": "**The labor union demanded a wage increase from the company. But the company side does not seem likely to accept the demand.**\n\n---\n\n- **要求（ようきゅう）する** — kango suru-verb, 他動詞, \"to demand, request.\" 要 = need + 求 = seek. Stronger than 依頼. Takes に for target, を for thing demanded. [JLPT N2]\n- **労働組合（ろうどうくみあい）** — kango noun, \"labor union.\" [JLPT N2]\n- **賃金（ちんぎん）の値上（ねあ）げ** — 賃金 = wages (kango) + 値上げ = price increase (wago). [JLPT N2]\n- **要求（ようきゅう）を受（う）け入（い）れそうもない** — 受け入れる (他動詞, \"to accept\") + そうもない (negative conjecture). Counterpart 自動詞: 受け入れられる. [JLPT N2]"
  },
  {
    "index": 292,
    "explanation": "**I bought stocks and they went up right away — I made a profit.**\n\n---\n\n- **得（とく）** — noun/な-adj, \"profit, gain, benefit.\" Kango. Opposite: 損（そん, loss). [JLPT N2]\n- **得をする** — set phrase, \"to profit, benefit.\" [JLPT N2]\n- **株（かぶ）を買（か）ったら** — 株 = stocks + 買う (他動詞, \"to buy\"). Counterpart 自動詞: 買われる. たら = conditional. [JLPT N4]\n- **値上（ねあ）がり** — noun, \"price increase.\" Wago (値 + 上がり). [JLPT N2]\n- **すぐに** — adverb, \"immediately.\" [JLPT N4]"
  },
  {
    "index": 293,
    "explanation": "**I lost money because stocks went down. / You will not regret buying this product (buying it is no loss).**\n\n---\n\n- **損（そん）** — noun, \"loss, disadvantage.\" Kango. Opposite: 得（とく, profit). [JLPT N2]\n- **損をする** — set phrase, \"to suffer a loss.\" [JLPT N2]\n- **株（かぶ）が下（さ）がって** — 下がる (自動詞, \"to fall, go down\"). Counterpart 他動詞: 下げる. [JLPT N4]\n- **買（か）って損（そん）はない** — set pattern, 「〜て損はない」= \"you will not lose by doing ~ / worth doing.\" [JLPT N2]\n- **商品（しょうひん）** — kango noun, \"product, merchandise.\" [JLPT N3]"
  },
  {
    "index": 294,
    "explanation": "**I competed with my friend to see who could get a better score on the test.**\n\n---\n\n- **勝負（しょうぶ）する** — kango suru-verb/noun, 自動詞, \"to compete, contest.\" 勝 = win + 負 = lose. The duality of winning/losing in one word. Takes と for opponent. [JLPT N2]\n- **どちらが** — \"which one (of two).\" Comparison of two options. [JLPT N5]\n- **いい点（てん）を取（と）るか** — いい点 = good score + 取る (他動詞, \"to get\"). Counterpart 自動詞: 取られる. [JLPT N4]\n- **友だちとした** — 友達 + と (with) + した (past of する, from 勝負する). [JLPT N5]"
  },
  {
    "index": 295,
    "explanation": "**The athletes ran past me at incredible speed.**\n\n---\n\n- **勢い（いきおい）** — noun, \"momentum, force, vigor, speed.\" Wago (from 勢う = to be in full swing). [JLPT N2]\n- **すごい勢いで** — すごい + 勢い + で (manner). \"At incredible speed.\" [JLPT N2]\n- **選手（せんしゅ）たち** — 選手 = athlete + たち (plural). [JLPT N3]\n- **走（はし）り過（す）ぎていった** — 走り過ぎる (自動詞, \"to run past\") + ていく (directional, away from speaker). 過ぎる (自動詞). Counterpart 他動詞: 過ぎさせる. [JLPT N3]"
  },
  {
    "index": 296,
    "explanation": "**A gas tank exploded, causing major damage. / To detonate dynamite.**\n\n---\n\n- **爆発（ばくはつ）する** — kango suru-verb, 自動詞/他動詞, \"to explode.\" 爆 = explode + 発 = emit. 自動詞: ガスタンクが爆発する. 他動詞: ダイナマイトを爆発させる (causative). [JLPT N2]\n- **ガスタンク** — loanword, \"gas tank.\" [JLPT N3]\n- **大（おお）きな被害（ひがい）が出（で）た** — 大きな + 被害 = damage + 出る (自動詞, \"to emerge, result in\"). Counterpart 他動詞: 出す. [JLPT N3]\n- **ダイナマイト** — loanword, \"dynamite.\" [JLPT N2]\n- **爆発（ばくはつ）させる** — causative form. 他動詞: \"to cause to explode.\" [JLPT N2]"
  },
  {
    "index": 297,
    "explanation": "**Let us get insurance in case we suffer from disasters like earthquakes or fires.**\n\n---\n\n- **災害（さいがい）** — kango noun, \"disaster, calamity.\" Natural and human-caused. [JLPT N2]\n- **地震（じしん）や火事（かじ）など** — 地震 + や...など (\"things like\") + 火事. Non-exhaustive list. [JLPT N4]\n- **〜にあったときのために** — あった (past of あう, 自動詞, \"to encounter, suffer\") + とき + のために (\"in preparation for\"). [JLPT N4]\n- **保険（ほけん）に入（はい）っておこう** — 保険に入る (set phrase, 自動詞, \"to sign up for insurance\") + ておこう (preparative volitional). Counterpart 他動詞: 入れる. [JLPT N2]"
  },
  {
    "index": 298,
    "explanation": "**Today's sports day was a great success, blessed with good weather too.**\n\n---\n\n- **天候（てんこう）** — kango noun, \"weather, climate.\" More formal than 天気. [JLPT N2]\n- **天候にも恵（めぐ）まれて** — 恵まれる (自動詞, \"to be blessed with\"). Counterpart 他動詞: 恵む. に marks source of blessing. て-form = reason. [JLPT N2]\n- **運動会（うんどうかい）** — noun, \"sports day, athletic meet.\" [JLPT N2]\n- **とてもいいものだった** — とてもいい + ものだった (\"turned out well\"). [JLPT N4]"
  },
  {
    "index": 299,
    "explanation": "**We dry the grass to use it as livestock feed. / Dry {air / skin}.**\n\n---\n\n- **乾燥（かんそう）する** — kango suru-verb, 他動詞/自動詞, \"to dry, to become dry.\" 乾 = dry + 燥 = parch. 他動詞: 草を乾燥させる. 自動詞: 空気が乾燥する. [JLPT N2]\n- **草（くさ）を乾燥（かんそう）させて** — causative 乾燥させる (他動詞, \"to dry something\"). て-form = purpose. [JLPT N2]\n- **家畜（かちく）のえさ** — 家畜 = livestock + えさ (kana for 餌, \"feed\"). Written in kana to avoid kanji confusion. [JLPT N2]\n- **乾燥した空気（くうき）/肌（はだ）** — 乾燥した (modifier, \"dry\") + 空気 / 肌 = skin. [JLPT N3]"
  },
  {
    "index": 300,
    "explanation": "**Fifteen minutes after the earthquake, a 30-centimeter tsunami was detected.**\n\n---\n\n- **観測（かんそく）する** — kango suru-verb, 他動詞, \"to observe, measure, detect (scientifically).\" 観 = observe + 測 = measure. [JLPT N2]\n- **観測された** — passive: \"was detected/observed.\" Scientific reporting avoids specifying observer. [JLPT N2]\n- **地震（じしん）の15分後（じゅうごふんご）** — 15 minutes after earthquake. [JLPT N4]\n- **津波（つなみ）** — wago noun, \"tsunami.\" 津 = harbor + 波 = wave. [JLPT N2]\n- **高さ30センチ** — 高さ = height (30 cm). Scientific measurement. [JLPT N3]"
  },
  {
    "index": 301,
    "explanation": "**To be stranded/lost in the {mountains / sea}. / A ship is wrecked. / Five people were caught in an avalanche.**\n\n---\n\n- **遭難（そうなん）する** — kango suru-verb, 自動詞, \"to be stranded, lost in disaster.\" 遭 = encounter (misfortune) + 難 = difficulty. Specifically outdoor/maritime disasters. [JLPT N2]\n- **山（やま）/海（うみ）で遭難する** — で marks location of disaster. [JLPT N4]\n- **船（ふね）が遭難する** — shipwreck. [JLPT N5]\n- **雪崩（なだれ）で5人が遭難した** — 雪崩 = avalanche (wago) + で (cause) + 5人が (subject). [JLPT N2]"
  },
  {
    "index": 302,
    "explanation": "**An accident occurred and the trains stopped. / {Incidents / pests / infectious diseases} break out.**\n\n---\n\n- **発生（はっせい）する** — kango suru-verb, 自動詞, \"to occur, arise, break out.\" 発 = start + 生 = generate. Used for negative/sudden events. Counterpart 他動詞 not common. Note: Chinese 发生 has same meaning (true friend). [JLPT N2]\n- **事故（じこ）が発生し** — し (continuative, formal clause connector). [JLPT N3]\n- **電車（でんしゃ）がストップした** — ストップする (loanword suru-verb, \"to stop\"). [JLPT N4]\n- **事件（じけん）/害虫（がいちゅう）/伝染病（でんせんびょう）** — typical collocations showing 発生 for undesirable events. [JLPT N2]"
  },
  {
    "index": 303,
    "explanation": "**An actor appears on stage. / This writer appeared on the scene like a comet.**\n\n---\n\n- **登場（とうじょう）する** — kango suru-verb, 自動詞, \"to appear (on stage, in a story, in society).\" 登 = ascend + 場 = place. [JLPT N2]\n- **舞台（ぶたい）** — kango noun, \"stage.\" [JLPT N3]\n- **俳優（はいゆう）** — kango noun, \"actor.\" [JLPT N2]\n- **すい星（せい）のように登場した** — すい星 (彗星, \"comet\") + のように (simile). Metaphorical: appearing suddenly and brilliantly, like a comet — brief, brilliant emergence. [JLPT N2]"
  },
  {
    "index": 304,
    "explanation": "**The economic situation recovers. / Recovered from a serious illness.**\n\n---\n\n- **回復（かいふく）する** — kango suru-verb, 自動詞, \"to recover, regain, return to normal.\" 回 = return + 復 = restore. Health, economy, mental state. Can also be 他動詞 (健康を回復する). Note: Chinese 恢复 has same meaning (true friend). [JLPT N2]\n- **経済状況（けいざいじょうきょう）** — kango noun, \"economic situation.\" [JLPT N2]\n- **重い病気（おもいびょうき）** — 重い (い-adj, \"serious\" for illness) + 病気. [JLPT N4]\n- **〜から回復した** — から marks source of recovery. [JLPT N3]"
  },
  {
    "index": 305,
    "explanation": "**I was able to graduate from university with help from my relatives.**\n\n---\n\n- **援助（えんじょ）** — kango noun, \"assistance, aid, support.\" 援 = help + 助 = assist. Formal, often financial. Slightly more formal than 支援. [JLPT N2]\n- **親戚（しんせき）の援助で** — で (means/instrument). \"Through relatives' support.\" [JLPT N3]\n- **大学を卒業（そつぎょう）できた** — 卒業する (他動詞) + できた (past potential). \"Was able to graduate.\" [JLPT N3]"
  },
  {
    "index": 306,
    "explanation": "**Now that we had a child, we signed up for life insurance.**\n\n---\n\n- **保険（ほけん）** — kango noun, \"insurance.\" 保 = protect + 険 = risk. [JLPT N2]\n- **生命保険（せいめいほけん）** — kango noun, \"life insurance.\" [JLPT N2]\n- **子どもが生まれたので** — 生まれる (自動詞, \"to be born\"). Counterpart 他動詞: 産む. ので = reason. [JLPT N4]\n- **保険に入（はい）った** — 保険に入る (set phrase, 自動詞, \"to sign up for\"). Counterpart 他動詞: 入れる. [JLPT N2]"
  },
  {
    "index": 307,
    "explanation": "**At the drinking party, we order more beer. / \"I would like to add to my earlier order.\"**\n\n---\n\n- **追加（ついか）する** — kango suru-verb, 他動詞, \"to add, append, order more.\" 追 = follow + 加 = add. In restaurant context: order more of something already ordered. Note: Chinese false friend — 追加 in Chinese means \"add\" generally, not specifically \"re-order.\" [JLPT N2]\n- **飲み会（のみかい）で** — 飲み会 = drinking party. Nominalized from 飲む + 会. [JLPT N3]\n- **さっきの注文（ちゅうもん）に追加したい** — さっきの + 注文 = order + に (target) + 追加したい (want to add). んですが = polite request softener. [JLPT N2]"
  },
  {
    "index": 308,
    "explanation": "**This technology can be applied to various machines.**\n\n---\n\n- **応用（おうよう）する** — kango suru-verb, 他動詞, \"to apply, put to practical use.\" 応 = respond + 用 = use. Taking a principle/technology and applying to new context. Note: Chinese 应用 has same meaning (true friend). [JLPT N2]\n- **技術（ぎじゅつ）** — kango noun, \"technology, technique.\" [JLPT N3]\n- **いろいろな機械（きかい）** — いろいろな = various + 機械 = machine(s). [JLPT N4]\n- **応用できる** — potential form of 応用する. に marks target of application. [JLPT N2]"
  },
  {
    "index": 309,
    "explanation": "**If you cannot answer 5 out of 10 questions, you are disqualified.**\n\n---\n\n- **解答（かいとう）/回答（かいとう）** — Both read かいとう. 解答 = \"answer\" to test/problem (academic). 回答 = \"reply\" to question/survey (formal). Both are kango suru-verbs (他動詞). 解 = solve + 答 = answer / 回 = return + 答 = answer. [JLPT N2]\n- **10問（じゅうもん）のうち5問（ごもん）** — 5 out of 10 questions. [JLPT N3]\n- **解答できない** — 解答する + できない (negative potential). [JLPT N2]\n- **失格（しっかく）になります** — 失格 = disqualification (失 = lose + 格 = qualification). [JLPT N2]"
  },
  {
    "index": 310,
    "explanation": "**Even after 3 hours of discussion, no conclusion was reached.**\n\n---\n\n- **結論（けつろん）** — kango noun, \"conclusion.\" 結 = tie + 論 = argument. Collocation: 結論が出る/出ない (reached/not reached). [JLPT N2]\n- **3時間（さんじかん）議論（ぎろん）しても** — 議論する + ても (concessive, \"even though\"). [JLPT N2]\n- **結論は出（で）なかった** — 出る (自動詞, \"to emerge\"). Counterpart 他動詞: 出す. 「結論が出る」= a conclusion is reached. [JLPT N3]"
  },
  {
    "index": 311,
    "explanation": "**I was told to come up with ideas for the new product.**\n\n---\n\n- **案（あん）** — kango noun, \"plan, proposal, idea.\" Shorter/less formal than 計画 or 提案. Rough or initial idea. 案を出す = put forward an idea. [JLPT N2]\n- **新製品（しんせいひん）** — kango noun, \"new product.\" [JLPT N2]\n- **案を出（だ）すように言（い）われた** — 出す (他動詞, \"to produce, put forward\"). Counterpart 自動詞: 出る. ように言われた (passive of 言う + ように, \"was told to\"). [JLPT N3]"
  },
  {
    "index": 312,
    "explanation": "**The population is concentrated in large cities. / I could not concentrate on work because I was worried.**\n\n---\n\n- **集中（しゅうちゅう）する** — kango suru-verb, 自動詞, \"to concentrate, to be focused on.\" 集 = gather + 中 = center/middle. Gathering at one point. Takes に for target (work, location). [JLPT N2]\n- **人口（じんこう）は大都市（だいとし）に集中（しゅうちゅう）している** — 人口 = population + 大都市 = large city. に marks concentration point. [JLPT N2]\n- **心配事（しんぱいごと）があって** — 心配事 = worry/concern (thing to worry about) + ある + て (reason). [JLPT N3]\n- **仕事（しごと）に集中（しゅうちゅう）できなかった** — 集中する + できなかった (past negative potential). \"Could not concentrate on work.\" [JLPT N2]"
  },
  {
    "index": 313,
    "explanation": "**When writing a report, you must distinguish between facts and opinions.**\n\n---\n\n- **区別（くべつ）する** — kango suru-verb, 他動詞, \"to distinguish, differentiate.\" 区 = section/divide + 別 = separate. Takes と...を or を for things distinguished. [JLPT N2]\n- **レポートを書（か）くとき** — レポート = report + を書く (他動詞, \"to write\"). Counterpart 自動詞: 書かれる. + とき = when. [JLPT N4]\n- **事実（じじつ）と意見（いけん）** — 事実 = fact + と + 意見 = opinion. The classic epistemological distinction. [JLPT N2]\n- **書（か）かなければならない** — 書く + なければならない (obligation, \"must\"). [JLPT N4]"
  },
  {
    "index": 314,
    "explanation": "**I want to create a society without discrimination. / These days, fewer companies discriminate based on gender in pay.**\n\n---\n\n- **差別（さべつ）する** — kango suru-verb/noun, 他動詞, \"to discriminate.\" 差 = difference + 別 = separate. Unfair treatment based on category. Takes を for the target of discrimination. [JLPT N2]\n- **差別（さべつ）のない社会（しゃかい）** — 差別 + のない (without) + 社会 = society. [JLPT N2]\n- **つくりたい** — 作る (他動詞, \"to create, make\") + たい (want to). Counterpart 自動詞: 作られる. [JLPT N5]\n- **今（いま）は** — は marks contrast with the past (fewer now than before). [JLPT N5]\n- **給料（きゅうりょう）で男女（だんじょ）を差別（さべつ）する** — 給料 = salary/wages + で (in terms of) + 男女 = men and women. Gender-based pay discrimination. [JLPT N3]"
  },
  {
    "index": 315,
    "explanation": "**Nagoya is located midway between Tokyo and Osaka. / A statement was announced that took a middle position between the two countries' opinions.**\n\n---\n\n- **中間（ちゅうかん）** — kango noun, \"middle, midpoint, intermediate.\" 中 = middle + 間 = space/between. Physical or abstract midpoint. [JLPT N2]\n- **東京（とうきょう）と大阪（おおさか）の中間（ちゅうかん）にある** — 中間 + にある (to be located at). [JLPT N2]\n- **二国間（にこっかん）の意見（いけん）の中間（ちゅうかん）を取（と）った** — 二国間 = bilateral/two-country + 意見 = opinions + 中間を取った (took the middle ground). 取る (他動詞, \"to take\"). Counterpart 自動詞: 取られる. [JLPT N2]\n- **声明（せいめい）が発（はっ）表（ぴょう）された** — 声明 = statement + 発表する (suru-verb, \"to announce, publish\") + された (passive). [JLPT N2]"
  },
  {
    "index": 316,
    "explanation": "**Left and right are reversed in a mirror. / The result was the opposite of what I expected.**\n\n---\n\n- **逆（ぎゃく）** — noun/な-adj, \"reverse, opposite, contrary.\" Kango. Indicates inversion or opposition. [JLPT N2]\n- **鏡（かがみ）では左右（さゆう）が逆（ぎゃく）になる** — 鏡 = mirror + では (in the mirror, contrastive) + 左右 = left and right + 逆になる (become reversed). なる (自動詞). [JLPT N2]\n- **予想（よそう）と逆（ぎゃく）の結果（けっか）** — 予想 = expectation/prediction + と (contrast) + 逆 + の + 結果 = result. [JLPT N3]"
  },
  {
    "index": 317,
    "explanation": "**Dialects are hard for people from other regions to understand. / I would like to live in another country.**\n\n---\n\n- **よそ** — noun/adj, \"another (place), other, outside.\" Wago. Refers to places/people outside one's own group. Often implies distance or unfamiliarity. Written in kana to distinguish from kanji homophones. [JLPT N2]\n- **方言（ほうげん）** — kango noun, \"dialect.\" 方 = direction/region + 言 = speech + 言語 (language). [JLPT N2]\n- **土地（とち）の人（ひと）** — 土地 = region/land (here: local area) + 人 = people. [JLPT N3]\n- **わかりにくい** — わかる (自動詞, \"to understand\") + にくい (difficult to). \"Hard to understand.\" [JLPT N4]\n- **よその国（くに）** — よその (attributive) + 国 = country. [JLPT N5]"
  },
  {
    "index": 318,
    "explanation": "**\"I do not know, so please ask someone else.\" / \"Are there any other questions?\"**\n\n---\n\n- **外（ほか）** — noun, \"other, else, besides.\" Wago. Different from 他（た）which is more formal/kango. Often used in 「ほかの」(other ~) or 「ほかに」(anything else). Note: Chinese false friend — 外 in Chinese means \"outside,\" not \"other.\" [JLPT N4]\n- **私（わたし）にはわかりません** — 私 + には (to me, topic marker emphasis) + わかりません (polite negative of わかる, 自動詞, \"to understand\"). [JLPT N5]\n- **ほかの人（ひと）に聞（き）いてください** — 聞く (他動詞, \"to ask\") + て + ください (request). Counterpart 自動詞: 聞こえる. [JLPT N5]\n- **ほかに質問（しつもん）はありませんか** — ほかに = anything else + 質問 = question(s) + は + ありませんか (polite negative question). [JLPT N3]"
  },
  {
    "index": 319,
    "explanation": "**There is a fence at the boundary between the neighboring houses. / After the autumn equinox, it suddenly became cool.**\n\n---\n\n- **境（さかい）** — noun, \"boundary, border, dividing line.\" Wago. Can be physical boundary or temporal/abstract turning point. [JLPT N2]\n- **隣（となり）の家（いえ）との境（さかい）** — 隣 = neighboring + 家 = house + との + 境 = boundary with. [JLPT N3]\n- **塀（へい）** — noun, \"fence, wall.\" Kango. [JLPT N2]\n- **秋分の日（しゅうぶんのひ）を境（さかい）に** — set pattern, 「〜を境に」= \"with ~ as the turning point / since ~.\" 秋分の日 = autumn equinox. [JLPT N2]\n- **急（きゅう）に涼（すず）しくなった** — 急に (adverb, \"suddenly\") + 涼しくなった (涼しい, い-adj, \"cool\" + くなった = became cool). [JLPT N3]"
  },
  {
    "index": 320,
    "explanation": "**Half of what she said is a lie.**\n\n---\n\n- **半ば（なかば）** — noun/adverb, \"half, midpoint, halfway.\" Wago (from 中 + ば). Can modify a noun (半ばうそ) or function adverbially. Note: not the same as 半分（はんぶん）— 半ば implies imprecision or roughness (\"roughly half\"). [JLPT N2]\n- **彼女（かのじょ）の話（はなし）** — 彼女 = she + の + 話 = story/what she said. [JLPT N5]\n- **うそだ** — うそ = lie + だ (copula). [JLPT N4]"
  },
  {
    "index": 321,
    "explanation": "**I usually wake up at 7, but today I overslept.**\n\n---\n\n- **普段（ふだん）** — noun/adverb, \"usually, normally, ordinarily.\" Wago (普 = general/widespread + 段 = stage/level). Describes habitual or typical state. Contrasts with specific exceptions (today). [JLPT N2]\n- **7時（じ）に起（お）きる** — 起きる (自動詞, \"to wake up, get up\"). Counterpart 他動詞: 起こす. [JLPT N5]\n- **が** — adversative conjunction, \"but.\" [JLPT N5]\n- **今日（きょう）は** — は marks contrast (contrastive topic): \"today, however...\" [JLPT N5]\n- **寝坊（ねぼう）してしまった** — 寝坊する (suru-verb, 自動詞, \"to oversleep\") + てしまった (completion/regret). 寝坊 = sleeping + 坊 (monk/room — staying in bed too long). [JLPT N2]"
  },
  {
    "index": 322,
    "explanation": "**To carry out daily routine tasks.**\n\n---\n\n- **日常（にちじょう）** — kango noun/な-adj, \"daily, everyday, routine.\" 日 = day + 常 = constant. Refers to the ordinary, recurring aspects of life. Often used as a modifier (日常の業務, 日常生活). Note: Chinese 日常 has same meaning (true friend). [JLPT N2]\n- **業務（ぎょうむ）** — kango noun, \"business, work, operations.\" More formal than 仕事. [JLPT N2]\n- **果た（は）たす** — 果たす (他動詞, \"to fulfill, accomplish, carry out\"). Counterpart 自動詞: 果たされる. 「業務を果たす」= to fulfill one's duties. [JLPT N2]"
  },
  {
    "index": 323,
    "explanation": "**This medicine cannot be obtained at ordinary stores. / {Public / worldly} general {opinions / customs}.**\n\n---\n\n- **一般（いっぱん）** — kango noun/な-adj, \"general, common, ordinary.\" 一 = one + 般 = kind/sort. Refers to what is common to a group or to the general public. 一般の店 = ordinary/regular stores (not specialty shops). [JLPT N2]\n- **手（て）に入（はい）らない** — 手に入る (set phrase, 自動詞, \"to be obtainable, to come into one's hands\"). Counterpart 他動詞: 手に入れる. Negative = cannot be obtained. [JLPT N3]\n- **薬（くすり）** — noun, \"medicine, drug.\" [JLPT N5]\n- **国民（こくみん）/世間（せけん）一般（いっぱん）** — 国民一般 = the general public/nationals; 世間一般 = general society/world. 世間 = society/public (wago concept with kango reading). [JLPT N2]\n- **意見（いけん）/習慣（しゅうかん）** — 意見 = opinion + 習慣 = custom/habit. [JLPT N3]"
  },
  {
    "index": 324,
    "explanation": "**It is common sense for a working adult to take proper responsibility for mistakes. / That person has no common sense.**\n\n---\n\n- **常識（じょうしき）** — kango noun, \"common sense.\" 常 = common/constant + 識 = knowledge. Shared understanding of what is reasonable in society. [JLPT N2]\n- **ミスをした** — ミス (loanword, \"mistake\") + をした (する, \"to make\"). [JLPT N3]\n- **きちんと** — adverb, \"properly, neatly, correctly.\" [JLPT N3]\n- **責任（せきにん）をとる** — set phrase (他動詞), 責任 = responsibility + とる = take. 「責任をとる」= to take responsibility. [JLPT N2]\n- **社会人（しゃかいじん）** — kango noun, \"working adult, member of society.\" Distinct from 学生 (student). [JLPT N2]\n- **常識がない** — ない marks absence. 「常識がない」= lacks common sense. [JLPT N2]"
  },
  {
    "index": 325,
    "explanation": "**Proverbs often contain moral lessons.**\n\n---\n\n- **ことわざ** — noun, \"proverb, saying.\" Wago (from 言 + 葉 = words/sayings that have been passed down). Written entirely in kana because it is native Japanese vocabulary. [JLPT N2]\n- **教訓（きょうくん）** — kango noun, \"moral lesson, teaching.\" 教 = teach + 訓 = instruction/training. Often used for the lesson derived from experience or traditional wisdom. [JLPT N2]\n- **含ま（ふくま）れていることが多い** — 含まれる (自動詞, passive of 含む, \"to be included, to contain\") + ている (state) + ことが多い (it is often the case that). Counterpart 他動詞: 含む. [JLPT N3]"
  },
  {
    "index": 326,
    "explanation": "**All citizens have the right to live a healthy life. / To assert one's rights.**\n\n---\n\n- **権利（けんり）** — kango noun, \"right, entitlement.\" 権 = authority/power + 利 = benefit. Legal or moral entitlement. [JLPT N2]\n- **すべての国民（こくみん）には** — すべて = all + 国民 = citizens/nationals + には (topic emphasis). [JLPT N2]\n- **健康的（けんこうてきな）生活（せいかつ）を送（おく）る** — 健康的 = healthy + 生活 = life/living + を送る (他動詞, \"to live, to spend\"). Counterpart 自動詞: 送られる. [JLPT N2]\n- **権利（けんり）を主張（しゅちょう）する** — 権利 + を主張する (他動詞, \"to assert, claim\"). [JLPT N2]"
  },
  {
    "index": 327,
    "explanation": "**Parents have an obligation to give their children an education. / To fulfill one's duties as a member of society.**\n\n---\n\n- **義務（ぎむ）** — kango noun, \"obligation, duty.\" 義 = righteousness + 務 = task/duty. Legal or moral requirement. Often paired with 権利 (rights): 権利と義務. [JLPT N2]\n- **親（おや）** — noun, \"parent(s).\" Wago. [JLPT N4]\n- **教育（きょういく）を受（う）けさせる** — 教育 = education + 受けさせる (causative of 受ける, 他動詞, \"to receive\"). Counterpart 自動詞: 受けられる. 「教育を受けさせる」= to make/let someone receive education (cause them to be educated). [JLPT N2]\n- **社会人（しゃかいじん）としての義務（ぎむ）を果た（は）たす** — 社会人として = as a member of society + の + 義務 = duty + を果たす (他動詞, \"to fulfill\"). Counterpart 自動詞: 果たされる. [JLPT N2]"
  },
  {
    "index": 328,
    "explanation": "**The trigger for the fight was something trivial.**\n\n---\n\n- **きっかけ** — noun, \"trigger, opportunity, chance, starting point.\" Wago (from kick + 掛ける = \"to set in motion\"). Written in kana. Marks the event that initiates a chain of events. [JLPT N2]\n- **けんか** — noun, \"fight, quarrel.\" Wago (喧嘩). Written in kana in the sentence. [JLPT N3]\n- **つまらないことだった** — つまらない (い-adj, \"trivial, boring, silly\") + ことだった (was something). 「つまらないこと」= something trivial/silly. [JLPT N4]"
  },
  {
    "index": 329,
    "explanation": "**His actions were truly admirable. / Those three always act together.**\n\n---\n\n- **行動（こうどう）する** — kango suru-verb/noun, 自動詞, \"to act, to take action.\" 行 = go + 動 = move. Physical action or behavior. 行動する = to act; 行動 = actions/behavior (noun). [JLPT N2]\n- **彼（かれ）の行動（こうどう）は、とても立派（りっぱ）だった** — 立派な (な-adj, \"admirable, splendid, impressive\"). Past: 立派だった. [JLPT N2]\n- **あの3人（さんにん）は** — あの = those + 3人 = three people. [JLPT N5]\n- **いつも一緒（いっしょ）に行動（こうどう）している** — いつも = always + 一緒に = together (に marks manner) + 行動している (acting, progressive/state). [JLPT N2]"
  },
  {
    "index": 330,
    "explanation": "**Nowadays, computers are often used for creating documents.**\n\n---\n\n- **使用（しよう）する** — kango suru-verb, 他動詞, \"to use.\" 使 = use + 用 = employ. More formal than 使う. Often used in written/official contexts (rules, manuals, specifications). Note: Chinese 使用 has same meaning (true friend). [JLPT N2]\n- **文書（ぶんしょ）の作成（さくせい）** — 文書 = document(s) + 作成 = creation/preparation. 作成する = to create/prepare. [JLPT N2]\n- **パソコン** — loanword, \"personal computer (PC).\" [JLPT N4]\n- **使用（しよう）されることが多い** — 使用される (passive of 使用する, \"is used\") + ことが多い (it is often the case that). [JLPT N2]"
  },
  {
    "index": 331,
    "explanation": "**The application deadline is October 31. / I submit a report to the company.**\n\n---\n\n- **提出（ていしゅつ）する** — kango suru-verb, 他動詞, \"to submit, to present (a document).\" 提 = present + 出 = submit/bring out. Formal, used for official documents. Note: Chinese 提出 has same meaning (true friend). [JLPT N2]\n- **願書（がんしょ）の提出（ていしゅつ）** — 願書 = application form + の提出 = submission. 願 = request + 書 = document. [JLPT N2]\n- **10月31日（じゅうがつさんじゅういちにち）までだ** — まで = until. Deadline expression. [JLPT N5]\n- **報告書（ほうこくしょ）を提出（ていしゅつ）する** — 報告書 = report document + を提出する. [JLPT N2]"
  },
  {
    "index": 332,
    "explanation": "**I got the payment deadline extended. / The expiration date of this ticket is March 5.**\n\n---\n\n- **期限（きげん）** — kango noun, \"deadline, time limit, term.\" 期 = period + 限 = limit. [JLPT N2]\n- **支払（しはらい）の期限（きげん）を延（の）ばしてもらった** — 支払い = payment + の期限 = deadline + を延ばしてもらった (causative-te + もらう, \"had someone extend for me\"). 延ばす (他動詞, \"to extend, postpone\"). Counterpart 自動詞: 延びる. [JLPT N2]\n- **有効期限（ゆうこうきげん）** — kango noun, \"expiration date, validity period.\" 有効 = valid + 期限 = deadline. [JLPT N2]\n- **このチケットの有効期限（ゆうこうきげん）は3月5日（さんがついつか）です** — チケット = ticket (loanword). [JLPT N4]"
  },
  {
    "index": 333,
    "explanation": "**Due to heavy rain, the sports day was postponed to one week later. / To postpone departure by one day.**\n\n---\n\n- **延期（えんき）する** — kango suru-verb, 他動詞, \"to postpone, to defer.\" 延 = extend + 期 = period. Moving an event to a later date. Note: Chinese 延期 has same meaning (true friend). [JLPT N2]\n- **大雨（おおあめ）のため** — 大雨 = heavy rain + のため = because of (reason, formal). [JLPT N3]\n- **運動会（うんどうかい）は1週間後（いっしゅうかんご）に延期（えんき）された** — 運動会 + は + 1週間後 = one week later + に (target date) + 延期された (passive, \"was postponed\"). [JLPT N2]\n- **出発（しゅっぱつ）を1日延期（えんき）する** — 出発 = departure + を (object) + 1日 (by one day) + 延期する. [JLPT N2]"
  }
]

with open('output/explanations_unit04_all.json', 'w', encoding='utf-8') as f:
    json.dump(entries, f, ensure_ascii=False, indent=2)

print(f'Wrote {len(entries)} entries to output/explanations_unit04_all.json')
