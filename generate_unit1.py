import json
import os

outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "explanations_unit01_all.json")

entries = []

def add(index, explanation):
    entries.append({"index": index, "explanation": explanation})

# Entry 1
add(1, """**To live a happy life.**

---

- **人生（じんせい）** — noun, "life" (one's entire lifespan/existence). Kango. Unlike 生活 (everyday living), 人生 refers to the broader arc of one's life. [JLPT N2]
- **幸（しあわ）せな** — な-adjective, "happy, fortunate." Wago. 幸せ functions as both noun and な-adjective. [JLPT N4]
- **送（おく）る** — 他動詞, "to spend, to live (a life)." Counterpart 自動詞: 送られる (passive). Collocates with 人生, 毎日, 休日. [JLPT N3]""")

# Entry 2
add(2, """**All people are equal.**

---

- **人間（にんげん）** — noun, "human being, person." Kango. Refers to humans as a species or as individuals with character. [JLPT N3]
- **皆（みな）** — pronoun, "all, everyone." Wago. [JLPT N4]
- **平等（びょうどう）である** — kango noun + copula, "equal." である is the formal/written copula. [JLPT N2]""")

# Entry 3
add(3, """**\"There was a phone call from someone called Satou.\"**

---

- **〜という** — pattern, "called/named." 「佐藤さんという人」= "a person called Mr./Ms. Satou." Used when the speaker doesn't know the person well. [JLPT N4]
- **人（ひと）** — noun, "person." Most general word for a person. [JLPT N5]
- **電話（でんわ）がありました** — 電話 + ある (他動詞 for inanimate existence). ありました is polite past. [JLPT N5]
- **〜よ** — sentence-ending particle, signals new information. [JLPT N5]""")

# Entry 4
add(4, """**It is believed that the ancestors of humankind originated in Africa.**

---

- **人類（じんるい）** — kango noun, "humankind, mankind." Used in scientific contexts. [JLPT N2]
- **祖先（そせん）** — kango noun, "ancestor, forebear." Biological ancestors of a species or lineage. [JLPT N2]
- **発生（はっせい）する** — kango suru-verb, 自動詞, "to originate, to arise." Counterpart 他動詞 not common. [JLPT N2]
- **〜と考えられている** — と (quotation) + 考える + られている (passive progressive). "It is believed that..." Academic passive expressing consensus. [JLPT N3]""")

# Entry 5
add(5, """**All my relatives live nearby.**

---

- **親戚（しんせき）** — kango noun, "relatives, kin." Extended family outside the nuclear family. Note: Chinese 亲戚 has the same meaning (true friend). [JLPT N3]
- **みな** — pronoun, "all, everyone." = 皆（みな）. [JLPT N4]
- **近く（ちかく）に住んでいる** — 住む (自動詞, "to reside") + ている (state). Counterpart 他動詞 rare. [JLPT N5]""")

# Entry 6
add(6, """**The Kobayashi couple are always on good terms with each other.**

---

- **夫婦（ふうふ）** — kango noun, "husband and wife, married couple." Refers only to the marital pair, not including children. [JLPT N3]
- **〜さん夫婦** — pattern, "the [surname] couple." Attaches to a family name. [JLPT N3]
- **仲（なか）がいい** — set phrase, "to be on good terms." 仲 = rapport/relationship. Opposite: 仲が悪い. [JLPT N4]""")

# Entry 7
add(7, """**In Japan, there was a tendency for the eldest son to be treated as important.**

---

- **長男（ちょうなん）** — kango noun, "eldest son." Cultural note: Traditional Japanese 家制度 placed special inheritance duties on the eldest son. [JLPT N2]
- **大事（だいじ）にされる** — 大事 (な-adj, "important") + に + される (passive of する). "To be cherished/treated as important." [JLPT N4]
- **傾向（けいこう）があった** — 傾向 (noun, "tendency") + がある + past. Indicates a general social pattern. [JLPT N2]""")

# Entry 8
add(8, """**The owner of that soba shop is still young, but his skills are good.**

---

- **そば屋（や）の主人（しゅじん）** — そば屋 = soba shop; 主人 = "owner, master" (of a shop). Note: 主人 can also mean "my husband" (humble) — context determines meaning. [JLPT N3/N2]
- **腕（うで）がいい** — set phrase, "to be skillful" (especially in cooking/craftsmanship). Literally "good arm," extended semantically. [JLPT N2]
- **が** — conjunctive particle, adversative "but." [JLPT N5]""")

# Entry 9
add(9, """**I have a younger twin brother.**

---

- **双子（ふたご）** — noun, "twins." Wago. 双子の弟 = younger twin brother. [JLPT N2]
- **弟（おとうと）** — noun, "younger brother." [JLPT N5]
- **います** — いる (自動詞, animate existence), polite form. [JLPT N5]""")

# Entry 10
add(10, """"(Announcement) We will now make a lost child announcement."**

---

- **迷子（まいご）** — noun, "lost child; being lost." From 迷う ("to be lost") + 子. [JLPT N2]
- **お知らせ** — お (honorific prefix) + 知らせ (noun, "notice"). Polite form used in public announcements. [JLPT N4]
- **〜をいたします** — いたす (humble する) + ます. Standard announcement language. [JLPT N4]""")

# Entry 11
add(11, """"I spoke to them thinking they were a friend, but they were a complete stranger."**

---

- **友だちだと思って** — 思う (他動詞, "to think") + て-form. 「〜と思って」= "thinking that..." [JLPT N5]
- **声（こえ）をかける** — set phrase, 他動詞, "to speak to, to call out to, to address." 自動詞 counterpart: 声がかかる (rare). [JLPT N3]
- **まったくの他人（たにん）** — まったくの (な-adj, "complete, utter") + 他人 ("stranger, unrelated person"). 他 = other + 人 = person. [JLPT N3]
- **だった** — past copula. 「他人だった」= "was a stranger." [JLPT N5]""")

# Entry 12
add(12, """**The siblings split into enemies and allies and fought.**

---

- **兄弟（きょうだい）** — noun, "siblings" (can mean brothers specifically or siblings generally). [JLPT N5]
- **敵（てき）と味方（みかた）に分（わ）かれて** — 敵 ("enemy") + 味方 ("ally") + に + 分かれる (自動詞, "to split/divide into"). Counterpart 他動詞: 分ける. [JLPT N3]
- **戦（たたか）った** — 戦う (自動詞, "to fight, to battle"). Counterpart 他動詞: 戦わせる. Past tense. [JLPT N3]""")

# Entry 13
add(13, """"No matter what happens, I am on your side."**

---

- **何（なに）があっても** — 何 + が + ある + ても (concessive conditional). "No matter what happens / Whatever may occur." [JLPT N4]
- **味方（みかた）** — noun, "ally, supporter, one's side." 味 = flavor/support + 方 = direction/side. Verb form: 味方する (to take someone's side). Opposite: 敵（てき）. [JLPT N3]
- **です** — polite copula. [JLPT N5]""")

# Entry 14
add(14, """**Choose from below what the author most wants to say.**

---

- **筆者（ひっしゃ）** — kango noun, "author, writer" (specifically the writer of an essay, article, or text being read). Used in academic/test contexts. 筆 = brush/writing + 者 = person. [JLPT N2]
- **最も（もっとも）言（い）いたいこと** — 最も (adverb, "most") + 言いたい (want to say, 言う + たい) + こと (nominalizer). "What (the author) most wants to say." [JLPT N5]
- **下（した）から選（え）らびなさい** — 下から ("from below") + 選ぶ (他動詞, "to choose/select") + なさい (imperative). 選ぶ counterpart 自動詞: 選ばれる (passive). [JLPT N4]""")

# Entry 15
add(15, """**Thanks to advances in medicine, human lifespan has extended considerably compared to 100 years ago.**

---

- **医学（いがく）の進歩（しんぽ）によって** — 医学 ("medicine") + 進歩 ("progress, advancement") + によって ("due to, thanks to"). Indicates cause/reason, especially for positive outcomes. [JLPT N3/N2]
- **寿命（じゅみょう）** — kango noun, "lifespan, life expectancy." [JLPT N2]
- **100年前（ねんまえ）に比べると** — 比べる (他動詞, "to compare") + と (conditional). Counterpart 自動詞: 比べられる. "When compared to..." [JLPT N3]
- **ずいぶん伸（の）びた** — ずいぶん (adverb, "considerably, quite a bit") + 伸びた (past of 伸びる, 自動詞, "to extend, to grow"). Counterpart 他動詞: 伸ばす. [JLPT N3]""")

# Entry 16
add(16, """**My hope for the future is to work overseas.**

---

- **将来（しょうらい）** — kango noun, "future, prospect." 将 = future + 来 = come. Note: Chinese 将来 means "future" — same meaning (true friend). [JLPT N3]
- **希望（きぼう）** — kango noun, "hope, wish, aspiration." [JLPT N3]
- **海外（かいがい）で働（はたら）くことだ** — 海外 ("overseas") + で (location of action) + 働く (自動詞, "to work") + こと (nominalizer) + だ (copula). Counterpart 他動詞: 働かせる. [JLPT N4]""")

# Entry 17
add(17, """**She has musical talent.**

---

- **才能（さいのう）** — kango noun, "talent, ability, gift." 才 = talent + 能 = ability. Natural, innate ability as opposed to acquired skills. [JLPT N2]
- **音楽（おんがく）の** — 音楽 = music. の marks possession/association. [JLPT N5]
- **〜がある** — "to have" (possession of an abstract quality). For Chinese speakers: Japanese uses が for inherent abilities, not を. [JLPT N5]""")

# Entry 18
add(18, """**I don't have the ability to solve this problem.**

---

- **能力（のうりょく）** — kango noun, "ability, capability." More formal and measurable than 才能; refers to skills that can be developed. 能 = ability + 力 = power. [JLPT N2]
- **問題（もんだい）を解決（かいけつ）する** — 問題 ("problem") + 解決する (kango suru-verb, 他動詞, "to solve, to resolve"). Counterpart 自動詞: 解決する can also be used intransitively. [JLPT N3/N2]
- **〜がない** — negation of possession. 「能力がない」= "don't have the ability." [JLPT N5]""")

# Entry 19
add(19, """"Please tell me your personality's strengths and weaknesses."**

---

- **性格（せいかく）の長所（ちょうしょ）と短所（たんしょ）** — 性格 ("personality") + 長所 ("strength, good point") + 短所 ("weakness, bad point"). 長所 and 短所 are a paired set — always learned together. [JLPT N3/N2]
- **言（い）ってください** — 言う (他動詞, "to say, to tell") + て-form + ください (polite request). [JLPT N5]""")

# Entry 20
add(20, """**I want to do education that develops children's individuality.**

---

- **個性（こせい）** — kango noun, "individuality, personality, uniqueness." 個 = individual + 性 = nature. Often contrasted with 協調性 (cooperativeness) in educational discourse. [JLPT N2]
- **子（こ）どもたちの** — 子ども ("children") + たち (plural suffix) + の. [JLPT N5]
- **伸（の）ばすような** — 伸ばす (他動詞, "to extend, to develop, to nurture") + ような (such as to / that would). Counterpart 自動詞: 伸びる. Here: "develop/nurture (individuality)." [JLPT N3]
- **教育（きょういく）がしたい** — 教育 ("education") + がしたい (want to do, する + たい). [JLPT N5]""")

# Entry 21
add(21, """**My left-handedness is a genetic inheritance from my parents.**

---

- **左利（ひだりき）き** — noun, "left-handedness." 左 = left + 利き = dominant (hand). The opposite is 右利き（みぎきき）. [JLPT N2]
- **親（おや）からの** — 親 ("parent(s)") + から ("from") + の (nominalizing). [JLPT N5]
- **遺伝（いでん）** — kango noun, "heredity, genetics." 遺 = leave behind + 伝 = transmit. As a verb: 遺伝する (自動詞). Counterpart 他動詞: 遺伝させる. [JLPT N2]
- **だ** — plain copula. [JLPT N5]""")

# Entry 22
add(22, """**Her movements are graceful and beautiful.**

---

- **動作（どうさ）** — kango noun, "movement, motion, gesture." 動 = move + 作 = make. Refers to physical bodily movements. [JLPT N2]
- **優雅（ゆうが）で** — な-adjective, "graceful, elegant." Kango. で is the て-form of the な-adjective copula, connecting to the next descriptor. [JLPT N2]
- **美（うつく）しい** — い-adjective, "beautiful." Wago. Often describes physical beauty or aesthetic qualities. [JLPT N4]""")

# Entry 23
add(23, """**Children tend to want to imitate everything their parents do.**

---

- **何（なに）でも** — pronoun, "anything, everything." も adds emphasis. [JLPT N5]
- **親（おや）のまねをしたがる** — まね（真似）("imitation, copy") + を + したがる (want to do, する + たがる). たがる is used for third-person desire (vs. たい for first person). Counterpart 他動詞: まねる exists as a verb. [JLPT N3/N2]
- **〜ものだ** — set expression, "it is natural that..., people tend to..." Expresses general truths or social observations. [JLPT N3]""")

# Entry 24
add(24, """**According to the survey results, the most common response was an average sleep time of 7 hours.**

---

- **アンケートの結果（けっか）** — アンケート (French "enquête", "survey/questionnaire") + 結果 ("result"). [JLPT N3]
- **睡眠（すいみん）時間（じかん）** — kango compound, "sleep time, hours of sleep." 睡眠 = sleep + 時間 = time. [JLPT N3]
- **平均（へいきん）7時間** — 平均 ("average") + 7時間. [JLPT N3]
- **〜という人（ひと）が最も（もっとも）多（おお）かった** — という ("that says/called") + 人 ("person") + が + 最も ("most") + 多かった (past of 多い, "many"). [JLPT N5]""")

# Entry 25
add(25, """"I have a cold right now and don't have an appetite."**

---

- **かぜをひいて** — かぜをひく (set phrase, 他動詞, "to catch a cold"). て-form connects cause to result. [JLPT N4]
- **食欲（しょくよく）** — kango noun, "appetite." 食 = eating + 欲 = desire. Common collocations: 食欲がある/ない, 食欲が出る/落ちる. [JLPT N2]
- **ない** — negation. 「食欲がない」= "have no appetite." [JLPT N5]""")

# Entry 26
add(26, """"Since living alone, the number of times I eat out has increased."**

---

- **一人（ひとり）ぐらしになって** — 一人暮らし ("living alone") + になって (becoming, て-form of なる). The change of state leads to the result. [JLPT N3]
- **外食（がいしょく）** — kango noun, "eating out, dining out." 外 = outside + 食 = eating. As verb: 外食する (自動詞). Counterpart: 自炊（じすい）する ("to cook for oneself"). [JLPT N2]
- **増（ふ）えた** — 増える (自動詞, "to increase"). Counterpart 他動詞: 増やす. Past tense. [JLPT N4]""")

# Entry 27
add(27, """**Recently, the number of men who also do housework and childcare has increased.**

---

- **最近（さいきん）は** — adverb/noun, "recently, lately." は sets the time topic. [JLPT N5]
- **家事（かじ）** — noun, "housework, household chores." Wago. 家 = house + 事 = matters/tasks. Covers cooking, cleaning, laundry. [JLPT N3]
- **育児（いくじ）** — kango noun, "childcare, raising children." 育 = raise + 児 = child. Often paired with 家事 in modern discourse. [JLPT N2]
- **もする** — も ("also") + する (他動詞, "to do"). Indicates addition to other activities. [JLPT N5]
- **男性（だんせい）が増（ふ）えた** — 男性 ("men") + が + 増えた (past of 増える, 自動詞). Counterpart 他動詞: 増やす. [JLPT N4]""")

# Entry 28
add(28, """**The other day, my older sister gave birth to a baby girl.**

---

- **先日（せんじつ）** — kango noun/adverb, "the other day, recently." More formal than この間. [JLPT N2]
- **姉（あね）が** — 姉 = "older sister" (speaker's own). は vs. が: が marks the subject of the action. [JLPT N5]
- **女の子（おんなのこ）を出産（しゅっさん）した** — 女の子 ("girl") + を + 出産する (kango suru-verb, 他動詞, "to give birth to"). Counterpart 自動詞: 出産する can also be used intransitively (彼女が出産した). [JLPT N2]""")

# Entry 29
add(29, """**To provide care/nursing for elderly people.**

---

- **お年寄（としよ）り** — polite noun, "elderly person, senior." お (honorific prefix) + 年寄り. More respectful than 老人（ろうじん）. [JLPT N3]
- **介護（かいご）** — kango noun, "nursing care, caregiving" (especially for elderly or disabled). 介 = assist + 護 = protect. Very important concept in modern Japan due to aging society. As verb: 介護する (他動詞). [JLPT N2]
- **をする** — する (他動詞, "to do"). [JLPT N5]""")

# Entry 30
add(30, """"We've both been working for 20 years since we got married."**

---

- **結婚（けっこん）20年（ねん）** — 結婚 ("marriage") + 20年 ("20 years"). Elliptical: 「結婚して20年」understood. [JLPT N5]
- **ずっと** — adverb, "continuously, all along." Emphasizes the duration. [JLPT N4]
- **共働（ともばたら）き** — noun, "both spouses working, dual-income household." 共 = together + 働き = working. Wago reading. As adjective: 共働きの (couple). [JLPT N2]
- **です** — polite copula. [JLPT N5]""")

# Entry 31
add(31, """**I go to work at 8 every morning.**

---

- **毎朝（まいあさ）8時（じ）に** — 毎朝 ("every morning") + 8時に ("at 8 o'clock"). に marks the specific time. [JLPT N5]
- **出勤（しゅっきん）している** — kango suru-verb, 自動詞, "to go to work, to commute to the office." 出 = go out + 勤 = serve (employment). Counterpart: 退勤（たいきん）する ("to leave work"). The 〜ている form here indicates a habitual action. [JLPT N3]""")

# Entry 32
add(32, """"I'd like to get promoted, but I also don't want a life that's all about work."**

---

- **出世（しゅっせ）もしたい** — 出世 (kango noun, "promotion, success in life/career") + も ("also") + したい (want to do, する + たい). 出世 carries connotations of climbing the corporate ladder, not just a simple promotion. [JLPT N2]
- **が** — conjunctive particle, adversative "but." [JLPT N5]
- **仕事（しごと）ばかりの人生（じんせい）も嫌（いや）だ** — 仕事 ("work") + ばかり ("nothing but") + の + 人生 ("life") + も ("also") + 嫌だ ("don't want, dislike"). 「ばかり」expresses excess — "a life consumed by work." [JLPT N4/N5]""")

# Entry 33
add(33, """**As one's position rises, stress increases too.**

---

- **地位（ちい）が上（あ）がるとともに** — 地位 ("position, status, rank") + が + 上がる (自動詞, "to rise, to go up") + とともに ("along with, as..."). Counterpart 他動詞: 上げる. とともに expresses simultaneous change. [JLPT N2]
- **ストレスも増（ふ）える** — ストレス ("stress") + も ("also") + 増える (自動詞, "to increase"). Counterpart 他動詞: 増やす. [JLPT N4]""")

# Entry 34
add(34, """**I took the entrance exam for a university in Tokyo.**

---

- **東京（とうきょう）の大学（だいがく）** — 東京 + の + 大学 ("university"). [JLPT N5]
- **受験（じゅけん）した** — kango suru-verb, 他動詞, "to take an entrance exam." 受 = receive + 験 = test. The object of 受験する is the institution being applied to (大学を受験する). Counterpart: 合格する ("to pass"). [JLPT N3]""")

# Entry 35
add(35, """**I majored in economics at university.**

---

- **大学（だいがく）で** — 大学 ("university") + で (location of action). [JLPT N5]
- **経済学（けいざいがく）を専攻（せんこう）した** — 経済学 ("economics") + を + 専攻する (kango suru-verb, 他動詞, "to major in, to specialize in"). 専 = special + 攻 = study. Counterpart 自動詞: 専攻している (state). [JLPT N2]""")

# Entry 36
add(36, """"Get ready, we're going out."**

---

- **出（で）かけるから** — 出かける (自動詞, "to go out, to leave the house") + から ("because, so"). 出かける counterpart 他動詞: none directly; causative 出かけさせる. [JLPT N4]
- **支度（したく）しなさい** — 支度 (noun, "preparation, getting ready") + しなさい (imperative of する). 支度 covers preparations like dressing, packing, etc. Wago reading. [JLPT N2]""")

# Entry 37
add(37, """**In the entryway, there is a large mirror that reflects one's whole body.**

---

- **玄関（げんかん）** — kango noun, "entryway, genkan" (Japanese home entrance). Kanga from Chinese architecture. [JLPT N3]
- **全身（ぜんしん）を映（うつ）す** — 全身 ("whole body") + を + 映す (他動詞, "to reflect, to show (in a mirror)"). Counterpart 自動詞: 映る. [JLPT N3]
- **大（おお）きな鏡（かがみ）が置（お）いてある** — 大きな ("large") + 鏡 ("mirror") + が + 置いてある (て-form of 置く + ある). 置いてある indicates a state resulting from someone having placed something — "is placed / is there." [JLPT N4]""")

# Entry 38
add(38, """**As you get older, wrinkles on your face increase.**

---

- **年（とし）をとると** — 年をとる (set phrase, 自動詞, "to grow older, to age") + と (conditional "when"). [JLPT N4]
- **顔（かお）のしわが増（ふ）える** — 顔 ("face") + しわ ("wrinkles, lines") + が + 増える (自動詞, "to increase"). Counterpart 他動詞: 増やす. [JLPT N5/N4]""")

# Entry 39
add(39, """"Go to the interview in proper attire."**

---

- **面接（めんせつ）** — kango noun, "interview" (especially job interview). 面 = face + 接 = meet/contact. [JLPT N3]
- **には** — に (destination) + は (topic emphasis). "For the purpose of going to..." [JLPT N5]
- **きちんとした** — adverb きちんと ("properly, neatly") + した (past of する, functioning as adjective modifier). "Proper, neat." [JLPT N3]
- **服装（ふくそう）** — kango noun, "clothing, attire, dress." 服 = clothes + 装 = attire. Covers overall appearance/dress code. [JLPT N2]
- **で行（い）きなさい** — で (means/manner) + 行きなさい (imperative of 行く, "go"). [JLPT N5]""")

# Entry 40
add(40, """**To express gratitude for someone's kindness.**

---

- **親切（しんせつ）にしてもらった** — 親切 (な-adj, "kind, kind-hearted") + に + してもらった (て-form of する + もらった, "received the favor of"). 「〜てもらう」expresses receiving a benefit from someone. [JLPT N4]
- **礼（れい）を述（の）べる** — 礼 ("thanks, gratitude, bow") + を + 述べる (他動詞, "to express, to state, to articulate"). Kango verb. Counterpart 自動詞: 述べられる. Common collocation for formal thanks. [JLPT N2]""")

# Entry 41
add(41, """"You have a nice tie," he says as flattery.**

---

- **いいネクタイですね** — いい ("good, nice") + ネクタイ ("necktie, tie") + です + ね (seeking agreement/softening). [JLPT N5]
- **と** — quotation particle. Marks the content of speech. [JLPT N5]
- **世辞（せじ）を言（い）う** — 世辞 ("flattery, polite compliment, insincere praise") + を + 言う (他動詞, "to say"). Note: 世辞 is almost always used in set phrases like 世辞を言う, 世辞ではない ("not just flattery"). Wago reading, though it uses kanji. [JLPT N2]""")

# Entry 42
add(42, """**Tanaka is always making excuses and refuses to admit his own failures.**

---

- **田中（たなか）さんはいつも** — 田中 + は + いつも ("always"). [JLPT N5]
- **言い訳（いわけ）ばかり言って** — 言い訳 ("excuse, justification") + ばかり ("nothing but") + 言って (て-form of 言う). 「ばかり」emphasizes the excessive/constant nature. [JLPT N2]
- **自分（じぶん）の失敗（しっぱい）を認（み）めようとしない** — 自分 ("oneself") + の + 失敗 ("failure, mistake") + を + 認めよう (volitional of 認める, "to admit, to acknowledge") + としない ("try not to / refuse to"). 認める counterpart 自動詞: 認められる (passive). [JLPT N3]""")

# Entry 43
add(43, """**Nonaka is a person with very rich conversation topics, and it's enjoyable talking with them.**

---

- **話題（わだい）が豊富（ほうふ）な人（ひと）で** — 話題 ("conversation topic, subject of discussion") + が + 豊富な (な-adj, "rich, abundant, extensive") + 人 ("person") + で (て-form of copula, connecting clauses). 話 = talk + 題 = topic. [JLPT N2]
- **話（はな）していて楽（たの）しい** — 話して (て-form of 話す, "to talk, to converse") + いる + て-form + 楽しい (い-adj, "enjoyable, fun"). The 〜ている + て-form construction links the activity to the feeling. [JLPT N5]""")

# Entry 44
add(44, """"I trust you and will confide my secret to you."**

---

- **あなたを信用（しんよう）して** — 信用する (kango suru-verb, 他動詞, "to trust, to have faith in"). 信 = believe + 用 = use. て-form connects to the next action. Note: Chinese 信用 means "credit/trust" — similar but Japanese 信用 emphasizes personal trust. Counterpart 自動詞: 信用される (passive). [JLPT N3]
- **私（わたし）の秘密（ひみつ）を打（う）ち明（あ）けます** — 秘密 ("secret") + を + 打ち明ける (他動詞, "to confide, to reveal, to confess"). 打ち明ける = 打ち (thoroughly) + 明ける (to make clear/reveal). Counterpart 自動詞: 打ち明けられる. [JLPT N2]""")

# Entry 45
add(45, """**Mother Teresa is respected by people all over the world.**

---

- **マザー・テレサ** — proper noun, "Mother Teresa." [JLPT N3]
- **世界中（せかいじゅう）の人々（ひとびと）に** — 世界中 ("all over the world") + の + 人々 ("people," plural of 人) + に (agent in passive construction). [JLPT N4/N2]
- **尊敬（そんけい）されている** — 尊敬する (kango suru-verb, 他動詞, "to respect, to admire") + れている (passive + progressive state). 尊 = precious + 敬 = respect. The passive form 「尊敬されている」= "is respected by." Counterpart 自動詞: 尊敬される. [JLPT N2]""")

# Entry 46
add(46, """**When praised, many people respond modestly by saying "No, not at all."**

---

- **ほめられたとき** — ほめる (他動詞, "to praise, to compliment") + られた (passive past) + とき ("when"). "When one was praised." [JLPT N4]
- **謙遜（けんそん）して** — 謙遜する (kango suru-verb, 自動詞, "to be modest, to be humble"). 謙 = humble + 遜 = modest. Cultural note: In Japan, deflecting compliments with謙遜 is expected social behavior. Counterpart 他動詞: 謙遜させる. [JLPT N2]
- **「そんなことはありません」と** — "That's not the case" + と (quotation). Standard Japanese modest response to praise. [JLPT N5]
- **言（い）う人（ひと）も多（おお）い** — 言う + 人 ("person who says") + も ("also") + 多い ("many"). [JLPT N5]""")

# Entry 47
add(47, """**I was expecting Yamamoto to perform well, but the results ended up disappointing.**

---

- **山本選（せん）手（しゅ）の活躍（かつやく）を期待（きたい）していたが** — 選手 ("athlete, player") + の + 活躍 ("active performance, exploits") + を + 期待していた (past progressive of 期待する, "to expect, to look forward to") + が (adversative "but"). 期 = period/expect + 待 = wait. Counterpart 自動詞: 期待される. [JLPT N2]
- **期待はずれの結果（けっか）に終（お）わった** — 期待はずれ ("disappointing, failing to meet expectations") + の + 結果 ("result") + に + 終わった (past of 終わる, 自動詞, "to end"). はずれ = miss/failure (from 外れる). Counterpart 他動詞: 終わらせる. [JLPT N3]""")

# Entry 48
add(48, """**After my father's death, my mother went through hardships to raise us.**

---

- **父（ちち）の死後（しご）** — 父 ("my father," humble) + の + 死後 ("after death"). 死後 is kango, formal. [JLPT N2]
- **母（はは）は苦労（くろう）して** — 母 ("my mother," humble) + は + 苦労して (て-form of 苦労する, 自動詞, "to go through hardships, to suffer"). 苦 = suffering + 労 = labor. Counterpart 他動詞: 苦労させる. [JLPT N3]
- **私（わたし）たちを育（そだ）ててくれた** — 私たち ("us") + を + 育ててくれた (て-form of 育てる, 他動詞, "to raise, to bring up" + くれた, indicating benefit to the speaker). Counterpart 自動詞: 育つ. The くれた adds emotional depth — acknowledges the mother's sacrifice. [JLPT N4]""")

# Entry 49
add(49, """**Her will is {firm / strong}, so she will surely achieve her goal.**

---

- **意志（いし）/ 意思（いし）** — Both read いし but differ: 意志 = "will, intention, determination" (focus on personal resolve); 意思 = "intent, intention, meaning" (focus on communicated intent or meaning behind words). Here意志 is correct with 固い/強い. [JLPT N2]
- **固（かた）い／強（つよ）い** — 固い ("firm, solid") and 強い ("strong") are both used with 意志.意志が固い = "firm-willed, determined"; 意志が強い = "strong-willed." For Chinese speakers: 固い does not mean "stubborn" here — it means "steadfast." [JLPT N5]
- **きっと目的（もくてき）を達成（たっせい）するだろう** — きっと ("surely, certainly") + 目的 ("goal, purpose") + を + 達成する (kango suru-verb, 他動詞, "to achieve, to accomplish") + だろう (conjecture, "will probably"). Counterpart 自動詞: 達成される. [JLPT N3]""")

# Entry 50
add(50, """**Tanaka's emotions show on his face immediately.**

---

- **感情（かんじょう）が顔（かお）に出（で）る** — 感情 ("emotion, feeling") + が + 顔に出る (set phrase, 自動詞, "to show on one's face"). 出る = to come out, to appear. Counterpart 他動詞: 出す. This idiom means the person cannot hide their feelings. [JLPT N3]
- **すぐに** — adverb, "immediately, right away." [JLPT N5]""")

# Entry 51
add(51, """**I went to the supermarket to buy ingredients for dinner.**

---

- **スーパーへ** — スーパー ("supermarket") + へ (direction particle). [JLPT N5]
- **夕食（ゆうしょく）の材料（ざいりょう）** — 夕食 ("dinner, evening meal") + の + 材料 ("ingredients, materials"). 材料 is kango. In cooking context, 材料 = cooking ingredients. In other contexts, it can mean raw materials. [JLPT N3]
- **買（か）いに行（い）った** — 買いに (purpose: "to buy") + 行った (past of 行く, "to go"). V-stem + に + 行く = "go to do V." [JLPT N5]""")

# Entry 52
add(52, """**I picked up a stone that was lying on the ground.**

---

- **グラウンド** — noun, "ground, sports field." From English "ground." Specifically refers to an outdoor sports field (baseball, track, etc.), not the earth itself. [JLPT N3]
- **落（お）ちている** — 落ちる (自動詞, "to fall, to be dropped") + ている (state). "Is lying/fallen." Counterpart 他動詞: 落とす. [JLPT N4]
- **石（いし）を拾（ひろ）った** — 石 ("stone, rock") + を + 拾った (past of 拾う, 他動詞, "to pick up"). Counterpart 自動詞: 拾われる. [JLPT N4]""")

# Entry 53
add(53, """**To tie old newspapers together with string.**

---

- **古新聞（ふるしんぶん）** — 古 (old) + 新聞 ("newspaper"). 「古新聞」= old newspapers. [JLPT N4]
- **ひも** — noun, "string, cord, rope." Written in hiragana; kanji form is 紐. Refers to thin cord used for tying things. [JLPT N2]
- **で縛（しば）る** — で (means, "with") + 縛る (他動詞, "to tie, to bind"). Counterpart 自動詞: 縛られる (passive). Kanji: 縛る. [JLPT N2]""")

# Entry 54
add(54, """"That shop is always crowded, and you need a numbered ticket to enter."**

---

- **いつも込（こ）んでいて** — いつも ("always") + 込んでいる (state of 込む, 自動詞, "to be crowded") + て-form. Counterpart 他動詞: 込める. [JLPT N3]
- **入（はい）るのに** — 入る (自動詞, "to enter") + の (nominalizer) + に ("for, in order to"). Counterpart 他動詞: 入れる. [JLPT N5]
- **整理券（せいりけん）が必要（ひつよう）だ** — 整理券 ("numbered ticket, queue ticket") + が + 必要だ ("is necessary"). 整理券 is issued at busy shops/restaurants to manage queues. [JLPT N2]""")

# Entry 55
add(55, """**To make a class roster.**

---

- **クラスの名簿（めいぼ）を作（つく）る** — クラス ("class") + の + 名簿 ("name list, roster, register") + を + 作る (他動詞, "to make, to create"). 名 = name + 簿 = register/book. Counterpart 自動詞: 作られる. [JLPT N3/N4]""")

# Entry 56
add(56, """**To tabulate the grades into a table/chart.**

---

- **成績（せいせき）を表（ひょう）にする** — 成績 ("grades, academic performance") + を + 表 ("table, chart") + に + する ("to make into"). 「AをBにする」= "to turn A into B." [JLPT N3/N5]""")

# Entry 57
add(57, """**To thread a needle.**

---

- **針（はり）に糸（いと）を通（とお）す** — 針 ("needle") + に (target) + 糸 ("thread") + を + 通す (他動詞, "to thread, to pass through"). Counterpart 自動詞: 通る. This is the standard expression for threading a needle. [JLPT N3]""")

# Entry 58
add(58, """**To open a bottle of beer / To pull the cork from a beer bottle.**

---

- **ビール** — noun, "beer." [JLPT N5]
- **栓（せん）を抜（ぬ）く** — 栓 ("stopper, cork, cap") + を + 抜く (他動詞, "to pull out, to remove, to open"). Counterpart 自動詞: 抜ける. 「栓を抜く」is a set phrase meaning "to open a bottle." [JLPT N2]""")

# Entry 59
add(59, """**My glasses fogged up from the steam of the udon noodles.**

---

- **うどんの湯気（ゆげ）で** — うどん ("udon noodles") + の + 湯気 ("steam, vapor") + で (cause/reason). 湯気 is specifically the visible steam rising from hot food or baths, not general water vapor. [JLPT N2]
- **眼鏡（めがね）がくもってしまった** — 眼鏡 ("glasses") + が + くもった (past of くもる, 自動詞, "to fog up, to become cloudy") + てしまった (completion/regret). 「〜てしまう」adds a sense of inconvenience here. Counterpart 他動詞: くもらせる. [JLPT N2]""")

# Entry 60
add(60, """**My room faces south and gets good sunlight.**

---

- **私（わたし）の部屋（へや）は南向（みなみむ）きで** — 部屋 ("room") + 南向き ("south-facing") + で (て-form of copula). 南向き = 南 (south) + 向き (facing). [JLPT N4]
- **日当（ひあ）たりがいい** — set phrase, "to get good sunlight, to be sunny." 日当たり = 日 (sun) + 当たり (exposure to). Opposite: 日当たりが悪い. Very common in real estate descriptions. [JLPT N2]""")

# Entry 61
add(61, """**Last night, I finished off a whole bottle of wine by myself.**

---

- **昨夜（さくや）** — noun, "last night." More literary than 昨夜（ゆうべ）. [JLPT N2]
- **一人（ひとり）で** — adverb, "alone, by oneself." [JLPT N5]
- **ワインびんを空（ら）にした** — ワインびん ("wine bottle") + を + 空にした (past of 空にする, 他動詞, "to empty, to finish off"). 空 here is read ら and means "empty." Counterpart 自動詞: 空く（あく）. For Chinese speakers: 空 here does not mean "sky" — it means "empty." [JLPT N2]""")

# Entry 62
add(62, """**The earthquake caused the house to tilt diagonally.**

---

- **地震（じしん）で** — 地震 ("earthquake") + で (cause/reason). [JLPT N4]
- **家（いえ）が斜（なな）めに傾（かたむ）いた** — 家 ("house") + が + 斜めに ("diagonally, at a slant") + 傾いた (past of 傾く, 自動詞, "to tilt, to lean"). Counterpart 他動詞: 傾げる. 斜め = diagonal/slant. [JLPT N2]""")

# Entry 63
add(63, """**When applying to the company, I wrote a resume/CV.**

---

- **会社（かいしゃ）に応募（おうぼ）するにあたり** — 会社 ("company") + に + 応募する (kango suru-verb, 他動詞, "to apply (for a position/job)") + にあたり ("upon, when"). 応募 = 応 (respond) + 募 (recruit). 〜にあたり is a formal expression meaning "at the time of, when doing." [JLPT N2]
- **履歴書（りれきしょ）を書（か）いた** — 履歴書 ("resume, CV") + を + 書いた (past of 書く, 他動詞, "to write"). 履歴書 = 履歴 ("history, record") + 書 ("document"). [JLPT N3]""")

# Entry 64
add(64, """**My father enjoys fishing as a hobby/recreation.**

---

- **うちの父（ちち）は** — うちの ("our/my," informal) + 父 ("my father," humble). うち is a casual alternative to 私の家. [JLPT N5]
- **釣（つ）り** — noun, "fishing." From 釣る ("to fish"). Written without kanji here. [JLPT N3]
- **を娯楽（ごらく）として楽（たの）しんでいる** — 娯楽 ("recreation, amusement, hobby") + として ("as") + 楽しんでいる (progressive of 楽しむ, 他動詞, "to enjoy"). 娯楽 = kango, formal word for leisure activities. Counterpart 自動詞: 楽しまれる. [JLPT N2]""")

# Entry 65
add(65, """**I asked a friend to be the master of ceremonies at a wedding.**

---

- **友人（ゆうじん）に** — 友人 ("friend") + に (target of the request). More formal than 友達. [JLPT N4]
- **結婚（けっこん）式の司会（しかい）** — 結婚式 ("wedding ceremony") + の + 司会 ("master of ceremonies, MC"). 司 = manage + 会 = meeting/gathering. [JLPT N2]
- **を頼（たの）んだ** — 頼む (他動詞, "to ask, to request, to entrust") + past. Counterpart 自動詞: 頼まれる (passive). 「人に〜を頼む」= "to ask someone to do something." [JLPT N4]""")

# Entry 66
add(66, """**A party was held to welcome the new employees.**

---

- **新入社員（しんにゅうしゃいん）を歓迎（かんげい）する会（かい）が開（ひら）かれた** — 新入社員 ("new employees") + を + 歓迎する (kango suru-verb, 他動詞, "to welcome") + 会 ("party, gathering") + が + 開かれた (passive past of 開く, "to hold/open"). 開く is 他動詞 here (to hold an event), counterpart 自動詞: 開く（あく）. The passive 「開かれた」= "was held." [JLPT N2/N3]""")

# Entry 67
add(67, """"A large crowd of people were lined up at the {bank / public office / hospital ...} counter."**

---

- **銀行（ぎんこう）／役所（やくしょ）／病院（びょういん）** — 銀行 = bank, 役所 = public/government office, 病院 = hospital. [JLPT N5/N3]
- **の窓口（まどぐち）には** — 窓口 ("counter, window, service desk") + には. Literally 窓 (window) + 口 (opening). Extended meaning: "point of contact" (in business: 窓口担当者 = person in charge). [JLPT N2]
- **大勢（おおぜい）の人（ひと）が並（なら）んでいた** — 大勢 ("many people, crowd") + の + 人 + が + 並んでいた (past progressive of 並ぶ, 自動詞, "to line up, to be lined up"). Counterpart 他動詞: 並べる. [JLPT N4]""")

# Entry 68
add(68, """**To go through enrollment procedures.**

---

- **入学（にゅうがく）の手続（てつづ）きをする** — 入学 ("school enrollment, entering school") + の + 手続き ("procedure, formalities") + を + する (他動詞). 手続き = 手続 + き. The kanji 手続き or 手続き are both used. Note: For Chinese speakers, 手続き is similar to 手续. [JLPT N3]""")

# Entry 69
add(69, """"It is a 10-minute walk from the station to my house."**

---

- **駅（えき）からうちまで** — 駅 ("station") + から ("from") + うち ("home, my house," casual) + まで ("to"). [JLPT N5]
- **徒歩（とほ）10分（ぷん）** — 徒歩 (kango noun, "walking, on foot") + 10分. 徒 = on foot + 歩 = walk. Used in real estate, directions, and formal contexts. Reading とほ (not とぼ). [JLPT N2]""")

# Entry 70
add(70, """**On Sundays in the city center, there is nowhere to park.**

---

- **日曜日（にちようび）の都心（としん）** — 日曜日 ("Sunday") + の + 都心 ("city center, downtown"). 都 = capital + 心 = center. [JLPT N3]
- **駐車（ちゅうしゃ）するところがない** — 駐車する (kango suru-verb, 他動詞, "to park (a vehicle)") + ところ ("place") + が + ない ("there is no"). 駐車 = 駐 (station) + 車 = vehicle. Counterpart: 駐車されない. ところ = place to do something. [JLPT N2/N5]""")

# Entry 71
add(71, """"To violate {rules / laws ...}"**

---

- **規則（きそく）／法律（ほうりつ）に違反（いはん）する** — 規則 ("rules, regulations") / 法律 ("laws") + に + 違反する (kango suru-verb, 自動詞, "to violate, to contravene"). 違反 = 違 (differ/wrong) + 反 = reverse/oppose. Takes に, not を. Counterpart 他動詞: 違反させる. [JLPT N2]""")

# Entry 72
add(72, """"That shop is open until 9 on weekdays."**

---

- **あの店（みせ）は** — あの ("that") + 店 ("shop") + は. [JLPT N5]
- **平日（へいじつ）は** — 平日 (kango noun, "weekday, business day") + は. Contrast: 休日（きゅうじつ）= holiday/day off, 土日（どにち）= weekend. Note: Chinese 平日 means "ordinary days" — similar but Japanese specifically means "non-holiday." [JLPT N2]
- **9時（じ）まで営業（えいぎょう）している** — 9時まで ("until 9 o'clock") + 営業している (progressive of 営業する, 自動詞, "to be open for business, to operate"). 営業 = 営 = manage + 業 = business. [JLPT N3]""")

# Entry 73
add(73, """**To write the date.**

---

- **日付（ひづけ）** — noun, "date" (the calendar date written on a document). 日 = day + 付 = attach/mark. Common collocations: 日付を書く, 日付を入れる, 日付が変わる (the date changes at midnight). [JLPT N3]""")

# Entry 74
add(74, """**It's cold in the mornings and evenings, but mild weather continues during the day.**

---

- **朝晩（あさばん）は冷（ひ）え込（こ）むが** — 朝晩 ("mornings and evenings") + は + 冷え込む (自動詞, "to get cold, to turn chilly") + が (adversative "but"). 冷え込む = 冷え (coldness) + 込む (to become deeply). Counterpart 他動詞: none. [JLPT N2]
- **日中（にっちゅう）は穏（おだ）やかな天気（てんき）が続（つづ）いている** — 日中 ("during the day, daytime") + は + 穏やかな (な-adj, "mild, calm, gentle") + 天気 ("weather") + が + 続いている (progressive of 続く, 自動詞, "to continue"). Counterpart 他動詞: 続ける. Note: 日中 is read にっちゅう here (not にっちゅう or ひるなか). [JLPT N3]""")

# Entry 75
add(75, """**I changed my travel schedule due to sudden business.**

---

- **急（きゅう）な用事（ようじ）で** — 急な (な-adj, "sudden, unexpected") + 用事 ("business, errand, matter") + で (reason). [JLPT N4]
- **旅行（りょこう）の日程（にってい）を変（か）えた** — 旅行 ("travel, trip") + の + 日程 ("schedule, itinerary") + を + 変えた (past of 変える, 他動詞, "to change"). 日程 = 日 = day + 程 = extent/schedule. Counterpart 自動詞: 変わる. [JLPT N3/N2]""")

# Entry 76
add(76, """"Nikko can be reached from Tokyo on a day trip."**

---

- **日光（にっこう）** — proper noun, "Nikko" (a famous tourist city in Tochigi Prefecture, known for shrines and nature). [JLPT N2]
- **東京（とうきょう）から** — 東京 + から ("from"). [JLPT N5]
- **日帰（ひがえ）りで行（い）けます** — 日帰り (noun, "day trip, returning the same day") + で (manner) + 行けます (potential form of 行く, "can go"). 日帰り = 日 (day) + 帰り (return). Counterpart verb: 日帰りする. [JLPT N2]""")

# Entry 77
add(77, """**The children line up in an orderly manner and enter the classroom.**

---

- **子（こ）どもたちが** — 子ども ("children") + たち (plural) + が (subject). [JLPT N5]
- **教室（きょうしつ）に** — 教室 ("classroom") + に (destination). [JLPT N5]
- **順序（じゅんじょ）よく並（なら）んで入（はい）っていく** — 順序 ("order, sequence") + よく (adverbial form of いい, "well") + 並んで (て-form of 並ぶ, 自動詞, "to line up") + 入っていく (entering + ていく, movement away from the speaker). Counterpart 他動詞: 並べる. 「順序よく」= "in order, orderly." [JLPT N3]""")

# Entry 78
add(78, """**From March to April is a busy period for our company.**

---

- **3月（さんがつ）から4月（しがつ）は** — 3月 ("March") + から ("from") + 4月 ("April") + は (topic). [JLPT N5]
- **うち会社（かいしゃ）にとって** — うちの ("our/my") + 会社 ("company") + にとって ("for, from the perspective of"). [JLPT N4]
- **忙（いそが）しい時期（じき）だ** — 忙しい (い-adj, "busy") + 時期 ("period, season, time"). 時期 refers to a specific time period with particular characteristics, distinct from 時間 (duration) or 時 (point in time). [JLPT N3]""")

# Entry 79
add(79, """**The station front used to be fields, but now it has become a large shopping center.**

---

- **駅前（えきまえ）は昔（むかし）は畑（はたけ）だったが** — 駅前 ("station front, area around the station") + は + 昔 ("the past, old days") + は + 畑 ("fields, farmland") + だった (past copula) + が (adversative "but"). The first は is topic, the second は is contrast. [JLPT N5]
- **現在（げんざい）は** — 現在 (kango noun, "present, current") + は. Formal equivalent of 今（いま）. [JLPT N3]
- **大（おお）きなショッピングセンターになっている** — 大きな ("large") + ショッピングセンター ("shopping center") + に + なっている (state resulting from change, なる + ている). [JLPT N4]""")

# Entry 80
add(80, """**Due to a sudden illness, the train made an unscheduled stop at this station.**

---

- **急病人（きゅうびょうにん）が出（で）たため** — 急病人 ("sudden patient, person taken ill suddenly") + が + 出た (past of 出る, 自動詞, "to appear, to occur") + ため ("because, due to"). ため indicates a direct cause, more formal than から. Counterpart 他動詞: 出す. [JLPT N2]
- **列車（れっしゃ）は臨時（りんじ）にこの駅（えき）に停車（ていしゃ）した** — 列車 ("train") + は + 臨時に (adverb, "temporarily, on an emergency basis") + この駅 ("this station") + に + 停車した (past of 停車する, 自動詞, "to stop (at a station)"). 臨時 = 臨 = face/encounter + 時 = time → "ad hoc, temporary, special." Counterpart: 停車させる. [JLPT N3]""")

# Entry 81
add(81, """**To save money for travel expenses.**

---

- **旅行（りょこう）の費用（ひよう）をためる** — 旅行 ("travel") + の + 費用 ("cost, expenses, funds") + を + ためる (他動詞, "to save, to accumulate"). 費用 is kango, more formal than お金. Counterpart 自動詞: たまる. [JLPT N3]""")

# Entry 82
add(82, """**Books are sold at the fixed price everywhere.**

---

- **本（ほん）はどこでも** — 本 ("book") + は + どこでも ("everywhere, anywhere"). [JLPT N5]
- **定価（ていか）で売（う）られている** — 定価 ("fixed price, list price, retail price") + で (manner) + 売られている (passive progressive of 売る, 他動詞, "to sell"). 定価 = 定 (fixed) + 価 = price. Note: Japan has a 再販売価格維持制度 (resale price maintenance system) for books. Counterpart 自動詞: 売れる. [JLPT N2]""")

# Entry 83
add(83, """"Since we're buying in bulk, could you give us a discount?"**

---

- **まとめて買（か）うから** — まとめて (adverb, "in bulk, all together") + 買う ("to buy") + から ("because, so"). まとめる = to gather/consolidate. [JLPT N3]
- **少（すこ）し割引（わりびき）してください** — 少し ("a little, slightly") + 割引 (kango noun/suru-verb, "discount, price reduction") + してください (polite request). 割引 = 割 (divide) + 引 = pull/reduce. Takes を: 割引をする. As adverb: 割引で. [JLPT N2]""")

# Entry 84
add(84, """"I bought 500-yen apples (normally 4 for 550 yen) by getting a discount."**

---

- **4個（こ）550円（えん）のりんごを** — 4個 ("4 pieces") + 550円 ("550 yen") + の + りんご ("apple") + を. [JLPT N5]
- **おまけしてもらって** — おまけ (noun, "extra, bonus, discount, throw-in") + して (te-form of する) + もらって (て-form of もらう, "to receive a favor"). 「おまけする」= to give a discount/extra. 「おまけしてもらう」= to receive a discount. おまけ also means "bonus feature, extra" (e.g., DVDおまけ). [JLPT N2]
- **500円（えん）で買（か）った** — 500円で ("for 500 yen") + 買った (past of 買う, "to buy"). で marks the price. [JLPT N5]""")

# Entry 85
add(85, """"Right now, we are giving away free samples."**

---

- **ただ今（ただいま）** — adverb, "right now, at this moment." More polite than just 今. Also means "I'm home" — context determines. [JLPT N4]
- **無料（むりょう）で** — 無料 (kango noun/な-adj, "free of charge, free") + で (manner). 無 = no + 料 = fee. [JLPT N3]
- **試供品（しきょうひん）をさしあげております** — 試供品 ("sample, free sample") + を + さしあげております (humble progressive of あげる, 他動詞, "to give"). さしあげる is the humble form of あげる, and おります is humble for いる. Extremely polite commercial language. [JLPT N2]""")

# Entry 86
add(86, """"He bought a new car and, get this, paid in cash."**

---

- **彼（かれ）は新車（しんしゃ）を買（か）って** — 彼 ("he") + は + 新車 ("new car") + を + 買って (て-form of 買う, connecting to next action). [JLPT N5]
- **なんと** — interjection/adverb, "would you believe it, surprisingly, get this." Expresses surprise at what follows. [JLPT N2]
- **現金（げんきん）で支払（しはら）ったそうだ** — 現金 ("cash") + で (manner) + 支払った (past of 支払う, 他動詞, "to pay") + そうだ (hearsay, "I hear that"). 支払う counterpart 自動詞: 支払われる. The そうだ indicates the speaker heard this from someone else. [JLPT N3]""")

# Entry 87
add(87, """**If you add up the area of Tokyo's 23 wards, it comes to 2,187 km².**

---

- **東京23区（とうきょうにじゅうさんく）の面積（めんせき）** — 東京23区 ("Tokyo's 23 special wards") + の + 面積 ("area, surface area"). 面 = surface + 積 = accumulate/measure. [JLPT N3]
- **合計（ごうけい）すると** — 合計する (kango suru-verb, 他動詞, "to add up, to total") + と (conditional "if"). 合計 = 合 = combine + 計 = calculate. Counterpart 自動詞: 合計される. [JLPT N2]
- **2,187 km² になる** — になる ("comes to, becomes"). Marks the resulting total. [JLPT N5]""")

# Entry 88
add(88, """**He earns income by running a café.**

---

- **彼（かれ）は喫茶店（きっさてん）を経営（けいえい）して** — 喫茶店 ("café, coffee shop") + を + 経営して (て-form of 経営する, 他動詞, "to manage, to operate (a business)"). 経営 = 経 = manage + 営 = operate. Counterpart 自動詞: 経営される. [JLPT N2]
- **収入（しゅうにゅう）を得（え）ている** — 収入 ("income, revenue") + を + 得ている (progressive of 得る, 他動詞, "to obtain, to earn, to gain"). 得る counterpart 自動詞: 得られる. [JLPT N2]""")

# Entry 89
add(89, """**This year expenses exceeded income, so we're in the red.**

---

- **今年（ことし）は支出（ししゅつ）が収入（しゅうにゅう）を上回（うわまわ）って** — 支出 ("expenses, expenditure") + が + 収入 ("income") + を + 上回って (て-form of 上回る, 他動詞, "to exceed, to surpass"). 上回る = 上 (above) + 回る (go around/surpass). Counterpart 自動詞: 上回られる. [JLPT N2]
- **赤字（あかじ）になった** — 赤字 ("deficit, being in the red") + に + なった (past of なる, "to become"). 赤字 literally means "red characters/figures" — from the accounting practice of writing deficits in red ink. Opposite: 黒字（くろじ）("in the black, surplus"). [JLPT N2]""")

# Entry 90
add(90, """**To draw up/prepare the budget for the next fiscal year.**

---

- **来年度（らいねんど）の予算（よさん）を立てる** — 来年度 ("next fiscal year") + の + 予算 ("budget") + を + 立てる (他動詞, "to establish, to draw up, to set"). 予算 = 予 = beforehand + 算 = calculate. 立てる is used with plans, budgets, and goals (計画を立てる, 目標を立てる). Counterpart 自動詞: 立つ. [JLPT N2]""")

# Entry 91
add(91, """**It is natural for companies to pursue profit.**

---

- **企業（きぎょう）が利益（りえき）を追求（ついきゅう）するのは** — 企業 ("company, enterprise") + が + 利益 ("profit, benefit") + を + 追求するのは (nominalized form of 追求する, 他動詞, "to pursue, to seek"). 追求 = 追 = chase + 求 = seek. Counterpart 自動詞: 追求される. のは nominalizes the clause. [JLPT N2]
- **当然（とうぜん）だ** — な-adjective, "natural, obvious, as it should be." 当 = appropriate + 然 = so/like. [JLPT N2]""")

# Entry 92
add(92, """**This month expenses were high, so the household budget is/went into the red.**

---

- **今月（こんげつ）は支出（ししゅつ）が多（おお）く** — 今月 ("this month") + は + 支出 ("expenses") + が + 多く (adverbial form of 多い, "much/many," connecting clauses). [JLPT N5]
- **家計（かけい）は赤字（あかじ）だった／になった** — 家計 ("household budget, family finances") + は + 赤字 ("deficit, in the red") + だった (was) / になった (became). 家計 = 家 = home + 計 = finances. [JLPT N2]""")

# Entry 93
add(93, """**We spent money on advertising, so sales increased.**

---

- **宣伝（せんでん）に経費（けいひ）をかけたので** — 宣伝 ("advertising, promotion") + に (target) + 経費 ("expenses, costs") + を + かけた (past of かける, 他動詞, "to spend (money, time, effort)") + ので (because, reason). 経費 = kango, business expenses. かける counterpart 自動詞: かけられる. [JLPT N2]
- **売（う）り上（あ）げが伸（の）びた** — 売り上げ ("sales, revenue") + が + 伸びた (past of 伸びる, 自動詞, "to grow, to increase"). Counterpart 他動詞: 伸ばす. 売り上げ = 売り (selling) + 上げ (raising). [JLPT N3]""")

# Entry 94
add(94, """"To count {money / the number of people ...}"**

---

- **金（かね）／人数（にんずう）を勘定（かんじょう）する** — 金 ("money") / 人数 ("number of people") + を + 勘定する (kango suru-verb, 他動詞, "to count, to calculate, to figure out"). 勘定 = 勘 = intuition/calculate + 定 = determine. Note: 勘定 also means "the bill/check" at a restaurant (勘定してください = "check, please"). Counterpart 自動詞: 勘定される. [JLPT N2]""")

# Entry 95
add(95, """**I broke the neighbor's window, so I paid for the repairs as compensation.**

---

- **隣（となり）の家（いえ）の窓（まど）ガラスを割（わ）ってしまったので** — 隣の家 ("neighbor's house") + の + 窓ガラス ("window glass") + を + 割ってしまった (past of 割る, 他動詞, "to break, to smash" + てしまった, indicating regret/completion) + ので (because). Counterpart 自動詞: 割れる. [JLPT N4]
- **修理代（しゅうりだい）を弁償（べんしょう）した** — 修理代 ("repair cost") + を + 弁償した (past of 弁償する, 他動詞, "to compensate for, to make restitution for"). 弁償 = 弁 = handle + 償 = compensate. Used specifically for compensating for damage or loss. Counterpart 自動詞: 弁償される. [JLPT N2]""")

# Entry 96
add(96, """**To request materials from the university.**

---

- **大学（だいがく）に資料（しりょう）を請求（せいきゅう）する** — 大学 ("university") + に (target) + 資料 ("materials, documents, data") + を + 請求する (kango suru-verb, 他動詞, "to request, to claim, to demand"). 請求 = 請 = request + 求 = seek. Note: 請求 can mean both "to request (materials)" and "to bill/demand payment" (請求書 = invoice). Context determines. Counterpart 自動詞: 請求される. [JLPT N2]""")

# Entry 97
add(97, """**When the economy worsens, the number of bankrupt companies increases.**

---

- **景気（けいき）が悪（わる）くなると** — 景気 ("economy, business conditions, market mood") + が + 悪くなる (becomes worse, 悪い + なる) + と (conditional "when"). 景気 literally = 景 = scene/appearance + 気 = mood/spirit. Note: Japanese 景气 is not the same as Chinese 景气 in usage — Japanese 景気 specifically refers to economic conditions/business cycle. [JLPT N2]
- **倒産（とうさん）する会社（かいしゃ）が増（ふ）える** — 倒産する (kango suru-verb, 自動詞, "to go bankrupt, to become insolvent") + 会社 ("company") + が + 増える (自動詞, "to increase"). 倒産 = 倒 = fall/collapse + 産 = property/business. Counterpart 他動詞: 倒産させる. [JLPT N2]""")

# Entry 98
add(98, """**I donated money for the earthquake disaster victims.**

---

- **地震（じしん）の被災者（ひさいしゃ）のために** — 地震 ("earthquake") + の + 被災者 ("disaster victim, affected person") + のために ("for the sake of"). 被災者 = 被 = suffer + 災 = disaster + 者 = person. [JLPT N2]
- **募金（ぼきん）した** — 募金する (kango suru-verb, 他動詞, "to donate, to make a charitable contribution"). 募 = solicit/recruit + 金 = money. Also used as a noun: 募金をする. Counterpart: 募金される. Note: 募金 can also mean "to collect donations" (soliciting side). Context clarifies. [JLPT N2]""")

# Entry 99
add(99, """**They were recruiting part-timers, so I applied.**

---

- **アルバイトを募集（ぼしゅう）していたので** — アルバイト ("part-time job," from German "Arbeit") + を + 募集していた (past progressive of 募集する, 他動詞, "to recruit, to solicit applications") + ので (because). 募集 = 募 = solicit + 集 = gather. Counterpart 自動詞: 募集される. [JLPT N2]
- **応募（おうぼ）した** — 応募する (kango suru-verb, 自動詞, "to apply, to enter (a competition)"). 応募 = 応 = respond + 募 = recruit. The relationship: company 募集する → person 応募する. [JLPT N3]""")

# Entry 100
add(100, """**The newer the information, the higher its value.**

---

- **情報（じょうほう）は新（あたら）しいほど** — 情報 ("information, news") + は + 新しい (い-adj, "new") + ほど ("the more... the more"). 「〜ば〜ほど」or 「〜ほど」= "the more X, the more Y." [JLPT N3]
- **価値（かち）が高（たか）い** — 価値 ("value, worth") + が + 高い (い-adj, "high"). 価値 = 価 = price + 値 = value. Common collocation: 価値が高い/低い. For Chinese speakers: Chinese 价值 is very similar in meaning (true friend). [JLPT N2]""")

# Write to file
with open(outpath, "w", encoding="utf-8") as f:
    json.dump(entries, f, ensure_ascii=False, indent=2)

print(f"Unit 1: wrote {len(entries)} explanations")
