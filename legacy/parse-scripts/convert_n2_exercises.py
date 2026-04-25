#!/usr/bin/env python3
"""
convert_n2_exercises.py

Converts raw N2 vocabulary exercise OCR JSONs + answer key pages into
enriched JSON format for the exercisesFromJSON tool (json_to_test.js).

Usage:
    python parse/scripts/convert_n2_exercises.py

Output:
    D:/n2Prepare/tools/exercisesFromJSON/data/n2/unit01/unit01_with_answers_1.json
    ... etc.
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict, OrderedDict

JSON_DIR = Path("json")
TOOL_DATA_DIR = Path("D:/n2Prepare/tools/exercisesFromJSON/data/n2")

# ─────────────────────────────────────────────────────────────────────────────
# Exercise page groups
# (folder_key, unit_num_or_None, unit_title, word_range, set_num, [page_nums])
# ─────────────────────────────────────────────────────────────────────────────

GROUPS = [
    ("unit01", 1,    "名詞 A",           "1–50",      1, [15, 16]),
    ("unit01", 1,    "名詞 A",           "51–100",    2, [23, 24]),
    ("unit01", 1,    "名詞 A",           "1–100",     3, [25, 26]),
    ("unit02", 2,    "動詞 A",           "101–160",   1, [35, 36]),
    ("unit02", 2,    "動詞 A",           "161–220",   2, [47, 48]),
    ("unit02", 2,    "動詞 A",           "101–220",   3, [49, 50]),
    ("unit03", 3,    "形容詞 A",         "221–270",   1, [61, 62]),
    ("unit04", 4,    "名詞 B",           "271–320",   1, [71, 72]),
    ("unit04", 4,    "名詞 B",           "321–370",   2, [79, 80]),
    ("unit04", 4,    "名詞 B",           "271–370",   3, [81, 82]),
    ("matome1", None, "まとめ1 複合動詞", "371–460",  1, [92, 93, 94]),
    ("matome1", None, "まとめ1 複合動詞", "371–460",  2, [95, 96]),
    ("unit05", 5,    "カタカナ A",       "461–510",   1, [107]),
    ("unit05", 5,    "カタカナ A",       "461–510",   2, [108]),
    ("unit06", 6,    "副詞 A + 接続詞",  "511–580",   1, [119, 120]),
    ("unit06", 6,    "副詞 A + 接続詞",  "511–580",   2, [253, 254]),
    ("unit07", 7,    "名詞 C",           "581–630",   1, [131, 132]),
    ("unit07", 7,    "名詞 C",           "631–680",   2, [141, 142]),
    ("unit07", 7,    "名詞 C",           "581–680",   3, [143, 144]),
    ("unit08", 8,    "動詞 B",           "681–740",   1, [157, 158]),
    ("unit08", 8,    "動詞 B",           "741–790",   2, [167, 168]),
    ("unit08", 8,    "動詞 B",           "681–790",   3, [169, 170]),
    ("unit09", 9,    "カタカナ B",       "791–840",   1, [179]),
    ("unit09", 9,    "カタカナ B",       "461–840",   2, [180, 181, 182]),
    ("unit10", 10,   "形容詞 B",         "841–890",   1, [191, 192]),
    ("unit10", 10,   "形容詞 B",         "841–890",   2, [193, 194]),
    ("unit11", 11,   "名詞 D",           "891–940",   1, [203, 204]),
    ("unit11", 11,   "名詞 D",           "941–990",   2, [213, 214, 215, 216]),
    ("unit12", 12,   "動詞 C",           "991–1040",  1, [227, 228]),
    ("unit12", 12,   "動詞 C",           "1041–1090", 2, [237, 238]),
    ("unit12", 12,   "動詞 C",           "991–1090",  3, [239, 240]),
    ("unit13", 13,   "副詞 B + 連体詞",  "1091–1160", 1, [251, 252]),
]

# ─────────────────────────────────────────────────────────────────────────────
# Load pages
# ─────────────────────────────────────────────────────────────────────────────

def load_pages():
    exercise_pages = {}
    answer_key_raw = []
    for path in sorted(JSON_DIR.glob("page_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pt = data.get("page_type", "")
        pnum = data.get("page", 0)
        if pt == "exercise":
            exercise_pages[pnum] = data
        elif pt == "answer_key":
            answer_key_raw.append((pnum, data.get("raw_text") or ""))
    answer_key_raw.sort()
    combined_ak = "\n\n".join(text for _, text in answer_key_raw)
    return exercise_pages, combined_ak


# ─────────────────────────────────────────────────────────────────────────────
# Answer key parser
# ─────────────────────────────────────────────────────────────────────────────

# Full-width Roman numerals used in answer keys
FW_ROMAN = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"
FW_ROMAN_RE = re.compile(r'^([' + FW_ROMAN + r']+)$')

def parse_answer_key(combined_text):
    """
    Parse combined answer key text into:
      dict[section_key] = {label: answers}

    section_key format: "unit01_1-50_I", "matome1_371-460_I", etc.
    label: "Ⅰ", "Ⅱ", ...
    answers: list of strings (numbered answers or word lists)
    """
    lines = combined_text.split('\n')

    result = {}

    # State
    current_unit = None    # "unit01", "matome1", etc.
    current_range = None   # "1-50", "371-460", etc.
    current_mondai = None  # "I", "II", etc. (from 練習問題)
    current_label = None   # "Ⅰ", "Ⅱ", etc.
    current_sub = None     # "A", "B", "C" sub-sections
    current_lines = []

    def flush_label():
        nonlocal current_lines, current_sub
        if current_unit and current_range and current_mondai and current_label:
            key = f"{current_unit}_{current_range}_{current_mondai}"
            if key not in result:
                result[key] = {}
            lbl = current_label
            if current_sub:
                lbl = f"{current_label}_{current_sub}"
            if lbl not in result[key]:
                result[key][lbl] = []
            result[key][lbl].extend(l for l in current_lines if l)
        current_lines = []

    def normalize_range(r):
        """Normalize range string: '1～50' → '1-50'"""
        return r.replace('～', '-').replace('〜', '-').replace('–', '-').replace('—', '-')

    def roman_to_ascii(fw):
        fw_to_ascii = {
            'Ⅰ': 'I', 'Ⅱ': 'II', 'Ⅲ': 'III', 'Ⅳ': 'IV', 'Ⅴ': 'V',
            'Ⅵ': 'VI', 'Ⅶ': 'VII', 'Ⅷ': 'VIII', 'Ⅸ': 'IX', 'Ⅹ': 'X',
            'Ⅺ': 'XI', 'Ⅻ': 'XII',
        }
        return ''.join(fw_to_ascii.get(c, c) for c in fw)

    def mondai_roman(text):
        """Extract mondai number from '練習問題Ⅰ' or '練習問題I' etc. → 'I'"""
        m = re.search(r'練習問題\s*([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩI-vIVX]+)', text)
        if m:
            r = m.group(1)
            if any(c in FW_ROMAN for c in r):
                return roman_to_ascii(r)
            return r.upper()
        return None

    UNIT_RE = re.compile(r'^(Unit\s+(\d+)|まとめ\s*(\d+))')
    RANGE_RE = re.compile(r'^(\d+)\s*[～〜~–\-]\s*(\d+)\s*$')
    MONDAI_RE = re.compile(r'練習問題')
    SUB_RE = re.compile(r'^([A-Z])\s*$')
    LABEL_RE = re.compile(r'^([' + FW_ROMAN + r']+)\s*$')

    for line in lines:
        line = line.rstrip()

        # Unit header
        m = UNIT_RE.match(line)
        if m:
            flush_label()
            current_label = None
            current_sub = None
            if m.group(2):  # "Unit N"
                unit_num = int(m.group(2))
                current_unit = f"unit{unit_num:02d}"
            else:  # "まとめN"
                matome_num = int(m.group(3))
                current_unit = f"matome{matome_num}"
            current_range = None
            current_mondai = None
            continue

        # Word range
        m = RANGE_RE.match(line)
        if m:
            flush_label()
            current_label = None
            current_sub = None
            current_range = f"{m.group(1)}-{m.group(2)}"
            continue

        # 練習問題 header
        if MONDAI_RE.search(line):
            flush_label()
            current_label = None
            current_sub = None
            mondai = mondai_roman(line)
            if mondai:
                current_mondai = mondai
            continue

        # Exercise label (full-width Roman numeral alone on a line)
        m = LABEL_RE.match(line)
        if m:
            flush_label()
            current_sub = None
            current_label = m.group(1)
            continue

        # Sub-section label (A, B, C on its own line)
        m = SUB_RE.match(line)
        if m and current_label:
            flush_label()
            current_sub = m.group(1)
            continue

        # Answer line
        if current_label:
            current_lines.append(line)

    flush_label()
    return result


def get_answers_for_section(ak_dict, unit_key, word_range, mondai_ascii):
    """Look up answers for a section in the answer key dict."""
    norm_range = word_range.replace('–', '-').replace('—', '-')
    key = f"{unit_key}_{norm_range}_{mondai_ascii}"
    return ak_dict.get(key, {})


# ─────────────────────────────────────────────────────────────────────────────
# Exercise page raw text parser
# ─────────────────────────────────────────────────────────────────────────────

ASCII_ROMAN_LABELS = ['XII', 'XI', 'X', 'IX', 'VIII', 'VII', 'VI', 'V', 'IV', 'III', 'II', 'I']

def split_raw_into_blocks(raw_text):
    """
    Split a raw exercise page text into exercise blocks.

    Returns: list of (label, instruction, body_text)
    where body_text is everything after the instruction until the next block.
    """
    if not raw_text:
        return []

    # Normalise: collapse multiple spaces/newlines into single space
    text = re.sub(r'\s+', ' ', raw_text).strip()

    # Skip page header up to "Step N N N N" or "練習問題"
    # Find the first occurrence of an exercise label as a standalone token
    # Build pattern from longest to shortest to avoid prefix matches
    label_re = re.compile(
        r'(?:^|\s)(' + '|'.join(ASCII_ROMAN_LABELS) + r')(?=\s)',
    )

    matches = list(label_re.finditer(text))
    if not matches:
        return []

    # Filter: keep only labels that form an increasing sequence (I, II, III, ...)
    # to avoid false positives from Roman numerals in content
    def roman_value(s):
        vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
        v = 0
        prev = 0
        for c in reversed(s):
            cv = vals.get(c, 0)
            if cv < prev:
                v -= cv
            else:
                v += cv
            prev = cv
        return v

    # Keep matches where the label sequence is non-decreasing and starts near 1
    filtered = []
    last_val = 0
    for m in matches:
        label = m.group(1)
        val = roman_value(label)
        if val >= last_val and val <= last_val + 3:  # allow small gaps
            filtered.append(m)
            last_val = val

    if not filtered:
        filtered = matches  # fallback: use all

    # Split text into blocks at each label position
    blocks = []
    for i, m in enumerate(filtered):
        label = m.group(1)
        start = m.end()  # position after the label
        end = filtered[i + 1].start() if i + 1 < len(filtered) else len(text)
        block_text = text[start:end].strip()
        blocks.append((label, block_text))

    # For each block: first sentence is instruction, rest is body
    result = []
    for label, block_text in blocks:
        # Instruction ends at first question ("1. ") or at a word list boundary
        first_q = re.search(r'\s1\.\s', block_text)
        if first_q:
            instruction = block_text[:first_q.start()].strip()
            body = block_text[first_q.start():].strip()
        else:
            # No numbered questions → whole block is instruction + word list
            # Instruction is up to the first Japanese punctuation or the whole thing
            # Split at common word separators
            instruction = block_text.strip()
            body = ""
        result.append((label, instruction, body))

    return result


def split_structured_raw_into_blocks(raw_text):
    """
    Parser for structured raw_text (pages with \\n preserved and full-width
    Roman numerals like Ⅰ, Ⅱ, Ⅲ as exercise section markers).

    Returns: list of (label, instruction, body_lines)
    """
    FW = "ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ"
    # Full-width Roman numeral at start of line, optionally followed by instruction
    FW_LABEL_RE = re.compile(r'^([' + FW + r']+)\s*(.*)')

    lines = raw_text.split('\n')

    blocks = []
    current_label = None
    current_instruction = ""
    current_body = []

    def flush():
        if current_label:
            blocks.append((current_label, current_instruction, current_body[:]))

    for line in lines:
        line = line.rstrip()
        m = FW_LABEL_RE.match(line)
        if m:
            flush()
            fw_label = m.group(1)
            # Convert full-width → ASCII
            fw_to_ascii = {
                'Ⅰ': 'I', 'Ⅱ': 'II', 'Ⅲ': 'III', 'Ⅳ': 'IV', 'Ⅴ': 'V',
                'Ⅵ': 'VI', 'Ⅶ': 'VII', 'Ⅷ': 'VIII', 'Ⅸ': 'IX', 'Ⅹ': 'X',
                'Ⅺ': 'XI', 'Ⅻ': 'XII',
            }
            ascii_label = ''.join(fw_to_ascii.get(c, c) for c in fw_label)
            current_label = ascii_label
            current_instruction = m.group(2).strip()
            current_body = []
        elif current_label is not None:
            current_body.append(line)

    flush()

    # Post-process: split each body into question objects
    result = []
    for label, instruction, body_lines in blocks:
        # Flatten multi-question lines: "1. X 2. Y" → ["1. X", "2. Y"]
        flat_body = []
        for line in body_lines:
            # Split on inline question numbers: "1. ... 2. ..."
            parts = re.split(r'(?<=。|）|）)\s+(?=\d{1,2}\.\s)', line)
            if len(parts) > 1:
                flat_body.extend(p.strip() for p in parts if p.strip())
            else:
                flat_body.append(line)

        result.append((label, instruction, "\n".join(flat_body)))

    return result


def parse_word_list(text):
    """Parse a space-separated word list from text."""
    # Remove trailing page number (a digit at end)
    text = re.sub(r'\s+\d+\s*$', '', text).strip()
    # Split on spaces, commas, 、, ・
    words = re.split(r'[\s　、・,]+', text)
    return [w.strip() for w in words if w.strip()]


def parse_numbered_questions(body_text):
    """
    Parse numbered questions from body_text.

    Returns: list of (qnum, qtext)
    """
    # Match patterns like "1. ...", "1 . ...", etc.
    q_re = re.compile(r'(?:^|\s)(\d{1,2})\.\s+')
    matches = list(q_re.finditer(body_text))
    questions = []
    for i, m in enumerate(matches):
        qnum = int(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body_text)
        qtext = body_text[start:end].strip()
        # Remove trailing page number
        qtext = re.sub(r'\s+\d{1,3}\s*$', '', qtext).strip()
        questions.append((qnum, qtext))
    return questions


def parse_options_from_question(qtext):
    """
    Extract options from question text containing 〔 opt1 opt2 opt3 〕.
    Returns: (phrase, options) where phrase has 〔  〕 placeholder.
    """
    m = re.search(r'〔([^〕]+)〕', qtext)
    if not m:
        return qtext, []
    inner = m.group(1).strip()
    options = [o.strip() for o in inner.split() if o.strip()]
    phrase = qtext[:m.start()] + '〔  〕' + qtext[m.end():]
    phrase = phrase.strip()
    return phrase, options


def parse_abcd_options_from_question(qtext):
    """
    Extract a/b/c/d options from question text.
    Returns: (question_text, options_list) or (qtext, []) if no options.
    """
    # Options look like: "a かけて b 出して c 集めて d たって"
    # or embedded as newline-separated
    opt_re = re.compile(r'\s+([a-d])\s+(\S+(?:\s+\S+){0,3}?)(?=\s+[a-d]\s|\s*$)')
    opts = opt_re.findall(qtext)
    if len(opts) >= 2:
        # Strip the options part from qtext
        first_opt_match = re.search(r'\s+[a-d]\s+\S', qtext)
        main_text = qtext[:first_opt_match.start()].strip() if first_opt_match else qtext
        options = [f"{letter} {text.strip()}" for letter, text in opts]
        return main_text, options
    return qtext, []


# ─────────────────────────────────────────────────────────────────────────────
# Convert one exercise block to enriched format
# ─────────────────────────────────────────────────────────────────────────────

def detect_type(label_data):
    """Detect exercise type from instruction + data fields."""
    instruction = label_data.get("instruction", "")
    words = label_data.get("words") or label_data.get("word_list")
    questions = label_data.get("questions", [])

    if words:
        return "B"
    if re.search(r'助詞|ひらがな', instruction):
        return "A"
    if re.search(r'反対', instruction):
        return "E"
    if re.search(r'意味が近い|近い', instruction) and not re.search(r'最も近い', instruction):
        return "F"
    if re.search(r'一つのことば|一つのもの', instruction) and any(
        isinstance(q, dict) and q.get("base") for q in questions
    ):
        return "D"
    if re.search(r'a・b・c・d|a．b．c．d|a[、,]b[、,]c[、,]d', instruction):
        return "K"
    # Check if questions are strings with 〔 〕 brackets
    if questions and isinstance(questions[0], str) and '〔' in questions[0]:
        return "C"
    if questions and isinstance(questions[0], dict) and questions[0].get("options"):
        if questions[0]["options"] and questions[0]["options"][0].startswith("a "):
            return "K"
        return "C"
    if re.search(r'選んで書き|下から選', instruction):
        return "G"
    if re.search(r'表を完成', instruction):
        return "H"
    if re.search(r'最もよいもの|選びなさい', instruction):
        return "K"
    return "G"  # default: fill-in


def build_exercise_object(label, raw_label_data, answer_lines):
    """
    Build enriched exercise object from raw data + answer lines.

    answer_lines: list of strings from answer key for this exercise label
    """
    instruction = raw_label_data.get("instruction", "").strip()
    raw_questions = raw_label_data.get("questions", [])
    raw_words = raw_label_data.get("word_list") or raw_label_data.get("words") or []
    raw_options = raw_label_data.get("options", [])  # top-level token bank

    ex = {"id": label, "instruction": instruction}

    # Parse answers from answer key
    # answer_lines may be: ["1. を", "2. に、を", ...] or ["味方、まね、..."] etc.
    numbered_answers = {}
    list_answers = []
    for line in answer_lines:
        line = line.strip()
        if not line:
            continue
        # Numbered: "1. を" or "1. のびる"
        m = re.match(r'^(\d+)\.\s+(.+)$', line)
        if m:
            numbered_answers[int(m.group(1))] = m.group(2).strip()
        else:
            # Could be a comma-separated word list on one line
            if '、' in line or ',' in line:
                list_answers.extend(w.strip() for w in re.split(r'[、,]', line) if w.strip())
            else:
                list_answers.append(line)

    # Determine exercise type and build accordingly
    etype = detect_type(raw_label_data)

    # ── Type B: checkbox ──────────────────────────────────────────────────────
    if raw_words:
        ex["words"] = list(raw_words)
        ex["questions"] = []  # required by json_to_test.js even for word-list exercises
        # answer_key = the correct (checked) words from answer lines
        if list_answers:
            ex["answer_key"] = list_answers
        elif numbered_answers:
            # Shouldn't happen for B, but handle gracefully
            ex["answer_key"] = list(numbered_answers.values())
        else:
            ex["answer_key"] = []
        return ex

    # ── Type A: particle fill-in ──────────────────────────────────────────────
    if etype == "A":
        questions = []
        for q in raw_questions:
            if isinstance(q, dict):
                qnum = q.get("id") or q.get("num")
                qtext = q.get("text", "")
                ans = numbered_answers.get(qnum, q.get("answer", ""))
            else:
                # string: "1. text..."
                m = re.match(r'^(\d+)\.\s+(.+)$', str(q))
                if m:
                    qnum = int(m.group(1))
                    qtext = m.group(2).strip()
                    ans = numbered_answers.get(qnum, "")
                else:
                    continue
            questions.append({"id": qnum, "text": qtext, "answer": ans})
        ex["questions"] = questions
        return ex

    # ── Type K: a/b/c/d multiple choice ──────────────────────────────────────
    if etype == "K":
        questions = []
        for q in raw_questions:
            if isinstance(q, dict):
                qnum = q.get("id") or q.get("num")
                qtext = q.get("text", "")
                opts = q.get("options", [])
                ans = numbered_answers.get(qnum, q.get("answer", ""))
            else:
                s = str(q)
                m = re.match(r'^(\d+)\.\s+(.+)$', s)
                if not m:
                    continue
                qnum = int(m.group(1))
                rest = m.group(2).strip()
                qtext, opts = parse_abcd_options_from_question(rest)
                ans = numbered_answers.get(qnum, "")
            questions.append({
                "id": qnum,
                "text": qtext,
                "options": opts if opts else [f"a ", "b ", "c ", "d "],
                "answer": ans
            })
        ex["questions"] = questions
        return ex

    # ── Type C: multiple choice from 〔 〕 ───────────────────────────────────
    if etype == "C":
        questions = []
        answer_key = {}
        section = "A"
        for q in raw_questions:
            if isinstance(q, dict):
                qnum = q.get("id") or q.get("num")
                phrase = q.get("phrase", q.get("text", ""))
                opts = q.get("options", [])
                ans = numbered_answers.get(qnum, q.get("answer", ""))
            else:
                s = str(q)
                m = re.match(r'^(\d+)\.\s+(.+)$', s)
                if not m:
                    continue
                qnum = int(m.group(1))
                phrase, opts = parse_options_from_question(m.group(2).strip())
                ans = numbered_answers.get(qnum, "")
            questions.append({"id": qnum, "phrase": phrase, "options": opts})
            if ans:
                answer_key.setdefault(section, []).append(ans)
        ex["section"] = section
        ex["questions"] = questions
        if answer_key:
            ex["answer_key"] = answer_key
        return ex

    # ── Type E: antonym write-in ──────────────────────────────────────────────
    if etype == "E":
        questions = []
        for q in raw_questions:
            if isinstance(q, dict):
                qnum = q.get("id") or q.get("num")
                word = q.get("word", q.get("phrase", q.get("text", "")))
                ans = numbered_answers.get(qnum, q.get("answer", ""))
            else:
                s = str(q)
                m = re.match(r'^(\d+)\.\s+(.+)$', s)
                if not m:
                    continue
                qnum = int(m.group(1))
                word = m.group(2).strip()
                # Strip trailing ( ) from word: "敵 ⇔ ( )" → "敵"
                word = re.sub(r'\s*[⇔←→]\s*\(.*?\).*$', '', word).strip()
                word = re.sub(r'\s*\(.*?\)\s*$', '', word).strip()
                ans = numbered_answers.get(qnum, "")
            questions.append({"id": qnum, "word": word, "answer": ans})
        ex["questions"] = questions
        return ex

    # ── Type F: synonym token bank ────────────────────────────────────────────
    if etype == "F":
        questions = []
        for q in raw_questions:
            if isinstance(q, dict):
                qnum = q.get("id") or q.get("num")
                word = q.get("word", q.get("text", ""))
                ans = numbered_answers.get(qnum, q.get("answer", ""))
            else:
                s = str(q)
                m = re.match(r'^(\d+)\.\s+(.+)$', s)
                if not m:
                    continue
                qnum = int(m.group(1))
                word = m.group(2).strip()
                word = re.sub(r'\s*\(.*?\)\s*$', '', word).strip()
                ans = numbered_answers.get(qnum, "")
            questions.append({"id": qnum, "word": word, "answer": ans})
        if raw_options:
            ex["options"] = list(raw_options)
        ex["questions"] = questions
        return ex

    # ── Type D: compound word token bank ─────────────────────────────────────
    if etype == "D":
        questions = []
        for q in raw_questions:
            if isinstance(q, dict) and q.get("base"):
                qnum = q.get("id") or q.get("num")
                base = q.get("base", "")
                hint = q.get("hint", "")
                ans = numbered_answers.get(qnum, q.get("answer", ""))
                questions.append({"id": qnum, "base": base, "hint": hint, "answer": ans})
        if raw_options:
            ex["options"] = list(raw_options)
        ex["questions"] = questions
        return ex

    # ── Type G: sentence fill-in token bank (default) ────────────────────────
    questions = []
    for q in raw_questions:
        if isinstance(q, dict):
            qnum = q.get("id") or q.get("num")
            qtext = q.get("text", q.get("phrase", ""))
            ans = numbered_answers.get(qnum, q.get("answer", ""))
            if isinstance(ans, list):
                ans = "、".join(ans)
        else:
            s = str(q)
            m = re.match(r'^(\d+)\.\s+(.+)$', s)
            if not m:
                continue
            qnum = int(m.group(1))
            qtext = m.group(2).strip()
            ans = numbered_answers.get(qnum, "")
        questions.append({"id": qnum, "text": qtext, "answer": ans})
    if raw_options:
        ex["options"] = list(raw_options)
    ex["questions"] = questions
    return ex


# ─────────────────────────────────────────────────────────────────────────────
# Collect exercises from a set of pages
# ─────────────────────────────────────────────────────────────────────────────

def collect_exercises_from_pages(page_data_list):
    """
    Merge exercises from multiple pages (handling continuations).
    Returns: OrderedDict mapping label → raw exercise data dict
    """
    merged = OrderedDict()

    for page_data in page_data_list:
        exs = page_data.get("exercises", [])
        raw = page_data.get("raw_text", "")

        if exs:
            # Structured exercises available
            for ex in exs:
                label = ex.get("label") or ex.get("id", "?")
                if label not in merged:
                    merged[label] = {
                        "instruction": ex.get("instruction", ""),
                        "questions": list(ex.get("questions", [])),
                        "word_list": list(ex.get("word_list", [])),
                        "options": list(ex.get("options", [])),
                    }
                else:
                    # Continuation: extend questions
                    merged[label]["questions"].extend(ex.get("questions", []))
        else:
            # Parse from raw_text
            if not raw:
                continue
            # Choose parser: structured (has \n + full-width Roman) vs flat
            if '\n' in raw and any(c in raw for c in 'ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ'):
                blocks = split_structured_raw_into_blocks(raw)
            else:
                blocks = split_raw_into_blocks(raw)
            for label, instruction, body in blocks:
                # For structured pages, normalise body newlines to spaces for
                # word-list detection, but keep multi-line numbered questions
                body_flat = re.sub(r'\s+', ' ', body).strip()
                # Check if this is a word-list exercise (no numbered questions)
                numbered_qs = parse_numbered_questions(body_flat)
                if not numbered_qs:
                    # Likely a word list
                    words = parse_word_list((instruction + " " + body_flat).strip())
                    # Separate instruction from words: instruction ends at first ○ or word list
                    # Heuristic: if instruction ends with "。" or "い。", words follow
                    instr_end = max(
                        instruction.rfind('。'),
                        instruction.rfind('い'),
                        instruction.rfind('さい'),
                    )
                    if label not in merged:
                        merged[label] = {
                            "instruction": instruction,
                            "questions": [],
                            "word_list": words,
                            "options": [],
                        }
                    else:
                        merged[label]["word_list"].extend(words)
                else:
                    # Has numbered questions
                    q_objs = []
                    for qnum, qtext in parse_numbered_questions(body_flat):
                        # Check for embedded a/b/c/d options
                        main, opts = parse_abcd_options_from_question(qtext)
                        if opts:
                            q_objs.append({
                                "id": qnum, "text": main, "options": opts
                            })
                        else:
                            # Check for 〔 〕 options
                            phrase, bracket_opts = parse_options_from_question(qtext)
                            if bracket_opts:
                                q_objs.append({
                                    "id": qnum, "phrase": phrase, "options": bracket_opts
                                })
                            else:
                                q_objs.append({"id": qnum, "text": qtext})

                    if label not in merged:
                        merged[label] = {
                            "instruction": instruction,
                            "questions": q_objs,
                            "word_list": [],
                            "options": [],
                        }
                    else:
                        merged[label]["questions"].extend(q_objs)

    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Build one enriched JSON for a group
# ─────────────────────────────────────────────────────────────────────────────

def build_enriched_json(group, exercise_pages, ak_dict):
    folder_key, unit_num, unit_title, word_range, set_num, pages = group

    # Load page data
    page_data_list = [exercise_pages[p] for p in pages if p in exercise_pages]
    if not page_data_list:
        print(f"  SKIP {folder_key} set {set_num}: no pages found ({pages})")
        return None

    # Collect exercises
    raw_exercises = collect_exercises_from_pages(page_data_list)
    if not raw_exercises:
        print(f"  WARN {folder_key} set {set_num}: no exercises extracted")

    # Get unit key for answer key lookup
    ak_unit_key = folder_key  # "unit01", "matome1", etc.
    norm_range = word_range.replace('–', '-').replace('—', '-')

    # Determine 練習問題 number for answer key lookup
    # Set 1 and 2 map to 練習問題I, set 3 maps to 練習問題II (usually)
    # But this isn't always true — infer from section text
    mondai_map = {1: "I", 2: "II", 3: "II"}
    # For units with 3+ sets: set 1 = range1 I, set 2 = range2 I, set 3 = cross II
    # For units with 2 sets: set 1 = I, set 2 = II
    # Heuristic based on section name of first page
    first_section = page_data_list[0].get("section", "")
    if "練習問題 II" in first_section or "練習問題Ⅱ" in first_section:
        ak_mondai = "II"
    elif "練習問題 I" in first_section or "練習問題Ⅰ" in first_section:
        ak_mondai = "I"
    else:
        ak_mondai = mondai_map.get(set_num, "I")

    # Get answer key section
    ak_section = ak_dict.get(f"{ak_unit_key}_{norm_range}_{ak_mondai}", {})
    if not ak_section:
        # Try without range (some answer key sections don't have range keys)
        for key in ak_dict:
            if key.startswith(f"{ak_unit_key}_") and key.endswith(f"_{ak_mondai}"):
                if norm_range.split('-')[0] in key:
                    ak_section = ak_dict[key]
                    break

    # Build exercises list
    exercises_out = []
    for label, raw_data in raw_exercises.items():
        # Find answers for this label from answer key
        # Try full-width roman numeral forms
        fw_map = {
            'I': 'Ⅰ', 'II': 'Ⅱ', 'III': 'Ⅲ', 'IV': 'Ⅳ', 'V': 'Ⅴ',
            'VI': 'Ⅵ', 'VII': 'Ⅶ', 'VIII': 'Ⅷ', 'IX': 'Ⅸ', 'X': 'Ⅹ',
            'XI': 'Ⅺ', 'XII': 'Ⅻ',
        }
        fw_label = fw_map.get(label, label)
        answer_lines = ak_section.get(fw_label, ak_section.get(label, []))

        ex_obj = build_exercise_object(label, raw_data, answer_lines)
        exercises_out.append(ex_obj)

    # Source page refs
    source_pages = [p for p in pages if p in exercise_pages]

    enriched = {
        "_unit": unit_num,
        "_unit_title": unit_title,
        "_range": word_range,
        "_set": set_num,
        "_source_pages": source_pages,
        "_description": f"{unit_title} {word_range} — set {set_num}",
        "exercises": exercises_out,
    }
    return enriched


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("Loading pages…")
    exercise_pages, combined_ak = load_pages()
    print(f"  {len(exercise_pages)} exercise pages loaded")

    print("Parsing answer key…")
    ak_dict = parse_answer_key(combined_ak)
    print(f"  {len(ak_dict)} answer key sections parsed")
    if "--debug-ak" in sys.argv:
        for k, v in sorted(ak_dict.items()):
            print(f"    {k}: {list(v.keys())}")

    written = 0
    skipped = 0
    for group in GROUPS:
        folder_key = group[0]
        set_num = group[4]

        result = build_enriched_json(group, exercise_pages, ak_dict)
        if result is None:
            skipped += 1
            continue

        # Write output
        out_dir = TOOL_DATA_DIR / folder_key
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{folder_key}_with_answers_{set_num}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        ex_count = len(result["exercises"])
        q_count = sum(
            len(e.get("questions", [])) or len(e.get("words", []))
            for e in result["exercises"]
        )
        print(f"  wrote {out_path}  ({ex_count} exercises, ~{q_count} items)")
        written += 1

    print(f"\nDone. {written} JSON files written, {skipped} skipped.")
    print(f"Output folder: {TOOL_DATA_DIR.resolve()}")


if __name__ == "__main__":
    main()
