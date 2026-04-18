import json

entries = [
    {"index": 1, "entry_id": 581, "word": "食料 / 食糧（しょくりょう）", "sentence": "日本は食料の自給率が低いと言われる。",
     "explanation": "**It is said that Japan's food self-sufficiency rate is low.**\n\n---\n\n- **食料 / 食糧（しょくりょう）** — kango noun, \"food, provisions.\" 食料 is everyday food supplies; 食糧 leans toward grain/staple food. Chinese 食糧 has a narrower meaning (grain only) — partial false friend. [JLPT N2]\n- **自給率（じきゅうりつ）** — kango noun, \"self-sufficiency rate.\" 自給 (self-supply) + 率 (rate). Collocates with 食料, エネルギー. [JLPT N2]\n- **低（ひく）い** — い-adjective, \"low.\" Opposite: 高い. [JLPT N5]\n- **〜と言われる** — と (quotation) + 言われる (passive of 言う). \"It is said that...\" Impersonal passive expressing a widely held view. [JLPT N4]"},
    
    {"index": 2, "entry_id": 582, "word": "粒（つぶ）", "sentence": "ぶどうを一粒食べる。",
     "explanation": "**Eat one grape.**\n\n---\n\n- **粒（つぶ）** — noun, counter suffix for small round objects (grains, drops, pills). Wago. As a counter: 一粒（ひとつぶ）, 二粒（ふたつぶ）. [JLPT N2]\n- **ぶどう** — noun, \"grapes.\" Kana is standard; kanji 葡萄 is rare. [JLPT N3]\n- **一（いち）粒（つぶ）** — counter + 粒. The counter つ is used with つ for small objects. [JLPT N2]\n- **食（た）べる** — 他動詞, \"to eat.\" [JLPT N5]"},

    {"index": 3, "entry_id": 583, "word": "くず（くず）", "sentence": "野菜のくずを捨てる。",
     "explanation": "**Throw away vegetable scraps.**\n\n---\n\n- **くず** — noun, \"scraps, waste, refuse, trimmings.\" Wago. Refers to unusable leftover parts (peels, stems, ends). Also means \"trash person\" colloquially. Kanji: 屑. [JLPT N2]\n- **野菜（やさい）の** — 野菜 = vegetables. の marks possession/association: \"vegetable scraps.\" [JLPT N5]\n- **捨（す）てる** — 他動詞, \"to throw away, to discard.\" Counterpart 自動詞: 捨てられる (passive). [JLPT N4]"},

    {"index": 4, "entry_id": 584, "word": "監督（かんとく）", "sentence": "スポーツチームの監督を務める。",
     "explanation": "**Serve as the manager/coach of a sports team.**\n\n---\n\n- **監督（かんとく）** — kango noun, \"director, supervisor, manager, coach.\" In sports: team manager/head coach. In film: director. Chinese 監督 has similar meaning (true friend). [JLPT N2]\n- **スポーツチームの** — スポーツ (sports) + チーム (team) + の. [JLPT N5]\n- **務（つと）める** — 他動詞, \"to serve (in a role), to fulfill (a duty).\" Collocates with 役, 教師, 社長. Counterpart 自動詞 not standard. [JLPT N2]"},

    {"index": 5, "entry_id": 585, "word": "収穫（しゅうかく）", "sentence": "農作物を収穫する。",
     "explanation": "**Harvest crops.**\n\n---\n\n- **収穫（しゅうかく）** — kango noun/suru-verb, \"harvest,收获.\" Also used figuratively for \"results, gains\" (e.g., 収穫がある = \"it was productive\"). Chinese 収穫 is identical (true friend). [JLPT N2]\n- **農作物（のうさくもつ）** — kango noun, \"agricultural products, crops.\" 農 (agriculture) + 作物 (crops). [JLPT N2]\n- **〜を収穫する** — suru-verb used 他動詞 here. Counterpart 自動詞: 収穫される (passive). [JLPT N2]"},

    {"index": 6, "entry_id": 586, "word": "産地（さんち）", "sentence": "青森県は、りんごの産地として有名だ。",
     "explanation": "**Aomori Prefecture is famous as a production area for apples.**\n\n---\n\n- **産地（さんち）** — kango noun, \"production area, region known for producing something.\" 産 (produce) + 地 (place). Often appears as 〜の産地. [JLPT N2]\n- **青森県（あおもりけん）** — proper noun, \"Aomori Prefecture\" (in northern Honshu, famous for apples). [JLPT N2]\n- **〜として** — particle, \"as, in the capacity of.\" 「産地として」= \"as a production area.\" [JLPT N3]\n- **有名（ゆうめい）だ** — な-adjective, \"famous.\" [JLPT N4]"},

    {"index": 7, "entry_id": 587, "word": "土地（とち）", "sentence": "土地を買って家を建てる。",
     "explanation": "**Buy land and build a house.**\n\n---\n\n- **土地（とち）** — kango noun, \"land, plot.\" Specifically refers to real estate land (not just ground/soil). Chinese 土地 has broader meaning (territory, land) — partial overlap. [JLPT N2]\n- **買（か）って** — 買う (他動詞, \"to buy\") + て-form (sequential action). [JLPT N5]\n- **家（いえ）を建（た）てる** — 建てる (他動詞, \"to build\"). Counterpart 自動詞: 建つ. [JLPT N4]"},

    {"index": 8, "entry_id": 588, "word": "倉庫（そうこ）", "sentence": "港には多くの倉庫が並んでいる。",
     "explanation": **"Many warehouses line the port."**\n\n---\n\n- **倉庫（そうこ）** — kango noun, \"warehouse, storehouse.\" 倉 = storehouse + 庫 = warehouse. Chinese 倉庫 is a true friend. [JLPT N2]\n- **港（みなと）** — noun, \"port, harbor.\" [JLPT N3]\n- **多（おお）くの** — 多く (many, adverbial/noun form of 多い) + の. Modifies 倉庫. [JLPT N4]\n- **並（なら）んでいる** — 並ぶ (自動詞, \"to line up, to be arranged\") + ている (state). Counterpart 他動詞: 並べる. [JLPT N3]"},

    {"index": 9, "entry_id": 589, "word": "解放（かいほう）", "sentence": "人質を解放する。",
     "explanation": "**Release the hostages.**\n\n---\n\n- **解放（かいほう）** — kango suru-verb/noun, \"release, liberation, freeing.\" 解 = untie + 放 = release. Used for hostages, prisoners, oppressed groups. Chinese 解放 is a true friend. [JLPT N2]\n- **人質（ひとじち）** — kango noun, \"hostage.\" 人 (person) + 質 (pledge/hostage). [JLPT N2]\n- **〜を解放する** — 他動詞 usage. The object is the thing/person being freed. [JLPT N2]"},

    {"index": 10, "entry_id": 590, "word": "収集（しゅうしゅう）", "sentence": "ごみは可燃・不燃に分別して収集する地域が多い。",
     "explanation": **"In many areas, garbage is sorted into combustible and non-combustible and then collected."**\n\n---\n\n- **収集（しゅうしゅう）** — kango suru-verb/noun, \"collection, gathering.\" 収 = gather + 集 = collect. Collocates with ごみ, データ, 情報. Chinese 收集 is similar (true friend). [JLPT N2]\n- **可燃（かねん）・不燃（ふねん）** — kango nouns, \"combustible / non-combustible.\" Standard waste-sorting categories in Japan. [JLPT N2]\n- **分別（ぶんべつ）して** — 分別する (kango suru-verb, 他動詞, \"to sort, classify\") + て-form (means/method). [JLPT N2]\n- **地域（ちいき）が多（おお）い** — 地域 (\"area, region\") + が多い (\"there are many\"). [JLPT N3]"},
]

print(f"Batch 1: {len(entries)} entries processed")
print(json.dumps(entries, ensure_ascii=False, indent=2)[:200])
