const fs = require('fs');
const path = require('path');
const { enrichMissingAnswers } = require('./answer_enrichment');

// ROOT = wordsAndExerciseInHtml/ (parent of this scripts/ directory)
const ROOT = path.resolve(__dirname, '..');
const DEFAULT_OUTPUT_ROOT = path.join(ROOT, 'exercises', 'n2');
const ANSWER_PAGES_DIR = path.join(ROOT, 'exercise_json', 'answerPages');

// Data root: intermediate JSON produced by convert_n2_exercises.py
const DATA_ROOT = path.join(ROOT, 'exercise_json', 'n2');

// CSS inlined — no dependency on a pre-existing template HTML file
const CSS = `* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Hiragino Sans', 'Meiryo', sans-serif; background: #f5f4f0; color: #1a1a1a; font-size: 15px; line-height: 1.8; }
.page { max-width: 780px; margin: 0 auto; padding: 24px 20px 60px; }
h1 { font-size: 20px; font-weight: 700; border-bottom: 2px solid #1a1a1a; padding-bottom: 8px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: baseline; }
h1 span { font-size: 13px; font-weight: 400; color: #666; }
.section { background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 20px 24px; margin-bottom: 20px; }
.section-title { font-size: 14px; font-weight: 700; background: #1a1a1a; color: #fff; padding: 4px 10px; border-radius: 4px; display: inline-block; margin-bottom: 16px; }
.section-q { font-size: 14px; font-weight: 600; margin-bottom: 14px; color: #333; }
.section-sub { font-size: 13px; font-weight: 700; color: #555; margin: 14px 0 8px; border-left: 3px solid #ccc; padding-left: 8px; }
.hint { font-size: 12px; color: #999; margin-bottom: 10px; }
.q-row { display: flex; align-items: baseline; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
.q-num { font-size: 13px; color: #999; min-width: 24px; flex-shrink: 0; }
.q-text { font-size: 15px; flex: 1; }
input.type-a { border: none; border-bottom: 1.5px solid #aaa; background: transparent; font-size: 15px; font-family: inherit; padding: 1px 4px; width: 52px; outline: none; color: #1a1a1a; transition: border-color 0.2s; }
input.type-a:focus { border-bottom-color: #1a55a0; }
.arrow { color: #aaa; margin: 0 4px; }
.word-grid { display: flex; flex-wrap: wrap; gap: 8px 18px; }
.word-item { display: flex; align-items: center; gap: 6px; font-size: 14px; cursor: pointer; }
.word-item input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; accent-color: #1a55a0; }
.s3-row { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.s3-label { font-size: 13px; color: #999; min-width: 24px; flex-shrink: 0; padding-top: 4px; }
.s3-phrase { font-size: 15px; flex: 1; min-width: 120px; }
.pill-group { display: flex; gap: 6px; flex-wrap: wrap; }
.pill { display: inline-block; padding: 4px 14px; border: 1.5px solid #ccc; border-radius: 20px; font-size: 14px; font-family: inherit; cursor: pointer; background: #fafafa; color: #444; transition: all 0.15s; user-select: none; }
.pill:hover { border-color: #1a55a0; color: #1a55a0; background: #eef3fb; }
.pill.selected { border-color: #1a55a0; background: #1a55a0; color: #fff; }
.compound-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; margin-bottom: 12px; }
.compound-item { display: flex; align-items: center; gap: 4px; font-size: 15px; flex-wrap: wrap; }
.blank-inp { border: none; border-bottom: 1.5px solid #aaa; background: transparent; font-size: 15px; font-family: inherit; padding: 1px 4px; min-width: 30px; width: 80px; outline: none; color: #1a1a1a; cursor: pointer; transition: border-color 0.2s; }
.blank-inp.active { border-bottom-color: #1a55a0; background: #eef3fb; border-radius: 3px 3px 0 0; }
.blank-inp-j { border: none; border-bottom: 1.5px solid #aaa; background: transparent; font-size: 15px; font-family: inherit; padding: 1px 4px; min-width: 60px; width: 100px; outline: none; color: #1a1a1a; transition: border-color 0.2s; }
.blank-inp-j:focus { border-bottom-color: #1a55a0; }
.token-bank { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; padding: 12px 14px; background: #f0ede6; border: 1px dashed #bbb; border-radius: 6px; }
.token { display: inline-block; padding: 5px 13px; border: 1.5px solid #999; border-radius: 20px; font-size: 14px; cursor: pointer; background: #fff; color: #1a1a1a; transition: all 0.15s; user-select: none; }
.token:hover:not(.used) { border-color: #1a55a0; color: #1a55a0; background: #eef3fb; }
.token.used { background: #e0e0e0; color: #aaa; border-color: #ccc; cursor: default; text-decoration: line-through; }
.verb-table { width: 100%; border-collapse: collapse; margin-top: 4px; }
.verb-table th, .verb-table td { border: 1px solid #ddd; padding: 7px 14px; font-size: 14px; }
.verb-table th { background: #f0ede6; font-weight: 700; text-align: center; }
.verb-table td { text-align: center; }
input.type-h { width: 100px; text-align: center; }
.mi-row { margin-bottom: 14px; }
.q-row.marked, .s3-row.marked, .compound-item.marked, .mi-row.marked { background: #fff9c4; border-left: 3px solid #f0a000; padding-left: 6px; border-radius: 3px; }
.pill.option-marked { background: #fff3b0 !important; border-color: #e0a000 !important; color: #7a5000 !important; }
.token.option-marked { background: #fff3b0 !important; border-color: #e0a000 !important; color: #7a5000 !important; }
.word-item.option-marked { background: #fff9c4; border-radius: 4px; padding: 2px 4px; }
input.correct, .blank-inp.correct, .blank-inp-j.correct { border-bottom-color: #2a9d4a !important; background: #eafaf0 !important; border-radius: 3px 3px 0 0; }
input.wrong, .blank-inp.wrong, .blank-inp-j.wrong { border-bottom-color: #d94040 !important; background: #fdf0f0 !important; border-radius: 3px 3px 0 0; }
.pill.correct-ans { border-color: #2a9d4a !important; color: #2a9d4a !important; font-weight: 700; }
.pill.wrong-sel { border-color: #d94040 !important; background: #fdf0f0 !important; color: #d94040 !important; }
.word-item.correct-cb { color: #2a9d4a; font-weight: 700; }
.word-item.wrong-cb { color: #d94040; }
.answer-reveal { color: #2a9d4a; font-size: 13px; font-weight: 700; margin-left: 4px; }
input:disabled, .blank-inp.locked, .blank-inp-j:disabled { opacity: 0.85; cursor: default; }
.pill.locked { pointer-events: none; }
.word-item.locked input { pointer-events: none; }
.score-bar { margin-top: 20px; padding: 14px 18px; border-radius: 8px; font-size: 15px; font-weight: 600; display: none; }
.score-bar.good { background: #eafaf0; border: 1.5px solid #2a9d4a; color: #1a6e35; }
.score-bar.bad { background: #fdf0f0; border: 1.5px solid #d94040; color: #a02020; }
.btn-row { display: flex; gap: 10px; margin-top: 24px; flex-wrap: wrap; }
button { font-family: inherit; font-size: 14px; padding: 9px 20px; border-radius: 6px; border: 1.5px solid #1a1a1a; cursor: pointer; font-weight: 600; transition: all 0.15s; }
.btn-clear { background: #fff; color: #1a1a1a; }
.btn-clear:hover { background: #f0ede6; }
.btn-check { background: #2a9d4a; color: #fff; border-color: #2a9d4a; }
.btn-check:hover { background: #228a3e; }
.btn-export { background: #1a55a0; color: #fff; border-color: #1a55a0; }
.export-box { margin-top: 16px; display: none; }
.export-box textarea { width: 100%; height: 280px; font-family: monospace; font-size: 12px; border: 1px solid #ccc; border-radius: 6px; padding: 10px; resize: vertical; background: #fafafa; color: #1a1a1a; }
.copy-btn { margin-top: 8px; background: #fff !important; border: 1.5px solid #aaa !important; color: #333 !important; font-size: 13px !important; padding: 6px 14px !important; font-weight: 400 !important; }
.copy-btn:hover { background: #f0ede6 !important; }
.q-block { margin-bottom: 18px; }
.q-block-text { font-size: 15px; margin-bottom: 8px; }
.word-badge { display: inline-block; background: #1a1a1a; color: #fff; font-size: 13px; font-weight: 700; padding: 2px 10px; border-radius: 4px; margin-bottom: 8px; }
.pill-group.vertical { flex-direction: column; gap: 5px; }
.pill-group.vertical .pill { text-align: left; border-radius: 6px; }
u { text-decoration: underline; text-underline-offset: 3px; }
.page-topbar { margin-bottom: 16px; }
.back-link { display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: 999px; border: 1.5px solid #cfd7e3; background: #fff; color: #1a55a0; text-decoration: none; font-size: 13px; font-weight: 700; letter-spacing: 0.01em; box-shadow: 0 8px 20px rgba(26,85,160,0.08); transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s, background 0.15s; }
.back-link:hover { transform: translateY(-1px); border-color: #1a55a0; background: #eef3fb; box-shadow: 0 12px 24px rgba(26,85,160,0.14); }
.back-link:focus-visible { outline: 3px solid rgba(26,85,160,0.25); outline-offset: 2px; }`;
const SHARED_PAGE_JS = fs.readFileSync(path.join(__dirname, 'shared_page_runtime.js'), 'utf8');
const EXTRA_PAGE_CSS = `
[data-control-kind="markable"],
.pill,
.token,
.word-item { position: relative; }

[data-control-kind="markable"].has-mark-toggle {
  padding-right: 44px;
}

.pill.has-mark-toggle,
.token.has-mark-toggle,
.word-item.has-mark-toggle {
  padding-right: 34px;
}

.pill.has-mark-toggle,
.token.has-mark-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding-right: 0;
}

.word-item.has-mark-toggle {
  gap: 8px;
  padding-right: 8px;
}

.pill {
  display: inline-flex !important;
  align-items: center;
  gap: 8px;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  color: inherit !important;
}

.pill-label {
  display: inline-block;
  padding: 4px 14px;
  border: 1.5px solid #ccc;
  border-radius: 20px;
  font-size: 14px;
  line-height: 1.3;
  background: #fafafa;
  color: #444;
  transition: all 0.15s;
}

.pill:hover .pill-label {
  border-color: #1a55a0;
  color: #1a55a0;
  background: #eef3fb;
}

.pill.selected .pill-label {
  border-color: #1a55a0;
  background: #1a55a0;
  color: #fff;
}

.mark-toggle {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 2;
  width: 24px;
  height: 24px;
  border: 1px solid #c7c2b3;
  border-radius: 999px;
  background: rgba(255,255,255,0.92);
  color: #8a7f62;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.pill.has-mark-toggle > .mark-toggle,
.token.has-mark-toggle > .mark-toggle,
.word-item.has-mark-toggle > .mark-toggle {
  position: static;
  top: auto;
  right: auto;
  margin-left: 2px;
  flex: 0 0 auto;
}

.mark-toggle:hover {
  border-color: #d09a1a;
  color: #b17800;
  background: #fff8df;
}

.mark-toggle.active {
  border-color: #c98a00;
  background: #fff0b8;
  color: #9b6800;
}

.q-row.marked, .s3-row.marked, .compound-item.marked, .mi-row.marked {
  background: #fffdf3;
  border-left: 3px solid #e0b24a;
  box-shadow: inset 0 0 0 1px rgba(224,178,74,0.28);
  padding-left: 6px;
  border-radius: 6px;
}

.pill.option-marked:not(.selected) .pill-label {
  background: #fafafa !important;
  color: #444 !important;
  border-color: #ccc !important;
  box-shadow: inset 0 0 0 2px #e0b24a;
}

.pill.selected.option-marked .pill-label {
  background: #1a55a0 !important;
  color: #fff !important;
  border-color: #1a55a0 !important;
  box-shadow: inset 0 0 0 2px #ffe08a, 0 0 0 1px rgba(224,178,74,0.18);
}

.token.option-marked:not(.used) {
  background: #fff !important;
  color: #1a1a1a !important;
  border-color: #999 !important;
  box-shadow: inset 0 0 0 2px #e0b24a;
}

.token.used.option-marked {
  background: #e0e0e0 !important;
  color: #aaa !important;
  border-color: #ccc !important;
  box-shadow: inset 0 0 0 2px #e0b24a;
}

.word-item.option-marked {
  background: #fffdf3;
  border-radius: 6px;
  box-shadow: inset 0 0 0 2px #e0b24a;
}

.inline-choice {
  display: inline-flex;
  vertical-align: middle;
  margin: 0 4px;
}

`;

const INFERRED = {
  'unit05_with_answers_1.json': {
    IV: {
      1: ['プレゼント', '花', '手紙'],
      2: ['チーム', '仕事', '財産'],
      3: ['ねこ', '虫', '鳥'],
      4: ['パーティー', 'オリンピック', '会議'],
      5: ['油', '線', '辞書'],
      6: ['丈', '差', '距離']
    },
    V: {
      1: 'ふやす',
      2: '閉じる',
      3: 'ひく',
      4: 'はずれる'
    },
    VI: {
      1: 'とどけ',
      2: 'かえて',
      3: 'だまされ',
      4: 'たすけ',
      5: 'ころした',
      6: 'ぬすまれ',
      7: 'つかみ',
      8: ['とばない', 'おさえた'],
      9: 'にぎり',
      10: 'いじめ',
      11: 'かわった',
      12: 'にあって'
    }
  },
  'unit05_with_answers_2.json': {
    IV: {
      1: ['えんぴつ', 'えだ', 'ほね'],
      2: ['カメラ', 'パソコン', '本だな'],
      3: ['スカート', '本'],
      4: ['まどガラス', 'さら']
    },
    V: {
      1: ['ぼうし', 'めがね', 'ゆびわ'],
      2: ['うわさ', 'あせ', '音楽'],
      3: ['カード', 'ノート', 'パンフレット']
    },
    VI: {
      1: 'みかけ',
      2: 'ふって',
      3: 'まよい',
      4: 'ゆるして',
      5: 'くりかえし',
      6: 'たって',
      7: 'ねむり',
      8: 'ためし',
      9: 'あわてて',
      10: 'いのり',
      11: 'まちがい',
      12: ['ゆれ', 'さました']
    }
  },
  'unit05_with_answers_3.json': {
    III: {
      1: 'b',
      2: 'c',
      3: 'a',
      4: 'd',
      5: 'b'
    }
  }
};

function esc(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function normalizeText(text) {
  return String(text || '')
    .replace(/（\s*\/\s*）/g, '( / )')
    .replace(/（\s*）/g, '( )')
    .replace(/〔\s+/g, '〔 ')
    .replace(/\s+〕/g, ' 〕');
}

function splitBlankText(text) {
  return normalizeText(text).split(/\(\s*\)/);
}

function questionNo(q, fallbackIndex) {
  return q.id ?? q.number ?? q.index ?? fallbackIndex + 1;
}

function questionKey(q, fallbackIndex) {
  return String(questionNo(q, fallbackIndex));
}

function normalizeItem(item) {
  if (typeof item === 'string') return item;
  if (!item || typeof item !== 'object') return String(item || '');
  return item.kanji || item.word || item.text || item.reading || item.label || item.value || '';
}

function normalizeList(list) {
  if (!Array.isArray(list)) return [];
  return list.map(normalizeItem).filter(Boolean);
}

function optionsArray(options) {
  if (Array.isArray(options)) return normalizeList(options);
  if (options && typeof options === 'object') {
    return Object.keys(options).sort().map(key => `${key} ${options[key]}`);
  }
  return [];
}

function splitDelimited(text) {
  return String(text || '')
    .split(/[、,]/)
    .map(s => s.trim())
    .filter(Boolean);
}

function hasCountHint(text) {
  return /[（(][0-9０-９]+[）)]/.test(String(text || ''));
}

function parseCheckboxAnswers(answerKey) {
  if (!Array.isArray(answerKey)) return new Set();
  const flat = [];
  answerKey.forEach(entry => {
    if (Array.isArray(entry)) {
      entry.forEach(v => flat.push(...splitDelimited(v)));
    } else {
      flat.push(...splitDelimited(entry));
    }
  });
  return new Set(flat);
}

function hasAnswerData(ex) {
  if (!ex || typeof ex !== 'object') return false;
  if (Array.isArray(ex.answer_key) && ex.answer_key.length > 0) return true;
  if (ex.answer_key && typeof ex.answer_key === 'object' && Object.keys(ex.answer_key).length > 0) return true;
  return (ex.questions || []).some(q => q && q.answer != null);
}

function hasStandaloneWordList(ex) {
  return Array.isArray(ex.words) || Array.isArray(ex.options) || Array.isArray(ex.word_bank) || Array.isArray(ex.choices);
}

function hasLetteredOptions(options) {
  return (
    Array.isArray(options) && options.every(opt => /^[a-d]\s+/.test(String(opt)))
  ) || (
    options && !Array.isArray(options) && typeof options === 'object' &&
    Object.keys(options).every(key => /^[a-d]$/.test(key))
  );
}

function hasChoiceCountQuestion(questions) {
  return (questions || []).some(q => /〔/.test(String(q.text || '')) && hasCountHint(q.text || ''));
}

function hasBracketPrompt(questions) {
  return (questions || []).some(q => /〔/.test(String(q.text || '')));
}

function isPairExercise(ex, firstQ) {
  return !!(firstQ && firstQ.left && firstQ.right) ||
    (ex.instruction || '').includes('同じ意味') && Array.isArray(ex.answer_key);
}

function isCategorizationExercise(ex) {
  return Array.isArray(ex.categories) && Array.isArray(ex.word_bank);
}

function isTableExercise(ex) {
  return Array.isArray(ex.table) || (ex.table && Array.isArray(ex.table.rows));
}

function isSectionedExercise(ex) {
  return Array.isArray(ex.sections);
}

function hasSectionWordBanks(ex) {
  return Array.isArray(ex.sections) && ex.sections.some(section => Array.isArray(section.word_bank) && section.word_bank.length > 0);
}

function isSubSectionExercise(ex) {
  return Array.isArray(ex.sub_sections);
}

function isTokenCompositionExercise(ex, firstQ) {
  return (
    ((firstQ && ('base' in firstQ || 'prefix' in firstQ || 'suffix' in firstQ)) || false) &&
    (Array.isArray(ex.options) || Array.isArray(ex.word_bank))
  ) || (
    (ex.instruction || '').includes('一つのことばにしなさい') &&
    (Array.isArray(ex.word_bank) || Array.isArray(ex.options) || Array.isArray(ex.choices))
  );
}

function isConjugationExercise(ex) {
  const questions = ex.questions || [];
  return questions.some(q => q && (q.answer_conjugated != null || q.answer_base != null));
}

function isEditableSectionTokenExercise(ex) {
  const instruction = ex.instruction || '';
  return isSectionedExercise(ex) &&
    hasSectionWordBanks(ex) &&
    instruction.includes('適当な形');
}

function isUsagePromptExercise(ex, firstQ) {
  const instruction = ex.instruction || '';
  return (
    Array.isArray(firstQ.options) &&
    !!firstQ.target &&
    !instruction.includes('意味が最も近い')
  );
}

function isSingleChoiceExercise(questions) {
  return (questions || []).some(q => Array.isArray(q.options));
}

function inferStructuralType(ex) {
  const instruction = ex.instruction || '';
  const questions = ex.questions || [];
  const firstQ = questions[0] || {};
  const standaloneWordList = hasStandaloneWordList(ex);
  const choiceCountQuestion = hasChoiceCountQuestion(questions);
  const bracketPrompt = hasBracketPrompt(questions);
  const belowSelectionPrompt = instruction.includes('下から') && (instruction.includes('えら') || instruction.includes('選'));
  const circlePrompt = /[◯〇○]/.test(instruction);
  const inlineOptionList = Array.isArray(firstQ.options) && !firstQ.text && !firstQ.phrase;

  if (isCategorizationExercise(ex)) return 'U';
  if (isSubSectionExercise(ex)) return 'N';
  if (isTableExercise(ex)) return 'H';
  if (isEditableSectionTokenExercise(ex)) return 'J';
  if (isSectionedExercise(ex)) return 'R';
  if (isPairExercise(ex, firstQ)) return 'O';
  if (isTokenCompositionExercise(ex, firstQ)) return 'D';
  if (isConjugationExercise(ex) && (Array.isArray(ex.options) || Array.isArray(ex.word_bank))) return 'J';
  if (isUsagePromptExercise(ex, firstQ)) return 'M';
  if (instruction.includes('意味が最も近い')) return 'L';
  if (choiceCountQuestion) return 'I';
  if (bracketPrompt && hasAnswerData(ex) && !isSingleChoiceExercise(questions)) return 'Q';
  if (circlePrompt && (standaloneWordList || inlineOptionList)) return 'B';
  if (hasLetteredOptions(firstQ.options)) return 'K';
  if (isSingleChoiceExercise(questions)) return 'C';
  if (belowSelectionPrompt && standaloneWordList) return 'G';
  return null;
}

function loadAnswerIndex(unitNumber) {
  const answerPath = path.join(
    ROOT,
    'vocab',
    'views',
    'exercises',
    `unit${String(unitNumber).padStart(2, '0')}_answers.json`
  );
  if (!fs.existsSync(answerPath)) return new Map();
  const raw = JSON.parse(fs.readFileSync(answerPath, 'utf8'));
  const map = new Map();
  for (const section of raw.answer_sections || []) {
    const answers = (((section.answers || [])[0] || {}).answers) || [];
    map.set(`${section._source_page}|${section.section}`, answers);
  }
  return map;
}

/**
 * Detects which renderer should handle an exercise payload.
 *
 * @param {object} ex Exercise JSON block from the source file.
 * @returns {string} Short renderer code used inside buildHtml().
 */
function detectType(ex) {
  const instruction = ex.instruction || '';
  const questions = ex.questions || [];
  const firstQ = questions[0] || {};
  const structuralType = inferStructuralType(ex);
  if (structuralType) return structuralType;
  if (instruction.includes('助詞')) return 'A';
  if (instruction.includes('短い形')) return 'S';
  if (instruction.includes('「的」のつくことば')) return 'S';
  if (instruction.includes('ひらがなを1字ずつ')) return 'T';
  if (instruction.includes('「ー」が一つ入ります')) return 'N';
  if (instruction.includes('答えは一つとはかぎりません')) return 'Q';
  if (instruction.includes('記号を書きなさい')) return 'P';
  if (instruction.includes('対義語') || instruction.includes('反対')) return 'E';
  if (instruction.includes('適当な形にして')) return 'J';
  if (instruction.includes('正しいことば')) return 'C';
  return '?';
}

function normalizeId(id) {
  return String(id).replace(/_cont$/, '');
}

function pageLabel(exercises) {
  const pages = [...new Set(exercises.map(ex => ex._source_page_num).filter(Boolean))].sort((a, b) => a - b);
  return pages.length <= 1 ? `p.${pages[0]}` : `p.${pages[0]}-${pages[pages.length - 1]}`;
}

function fillAnswers(filename, data) {
  const answerIndex = loadAnswerIndex(data._unit);
  const inferred = INFERRED[filename] || {};
  for (const ex of data.exercises) {
    const normId = normalizeId(ex.id);
    const fallbackAnswers = answerIndex.get(`${ex._source_page}|${normId}`) || [];

    if (ex.answer_key && typeof ex.answer_key === 'object' && !Array.isArray(ex.answer_key)) {
      (ex.sections || []).forEach(section => {
        const sectionAnswers = Array.isArray(ex.answer_key[section.id]) ? ex.answer_key[section.id] : [];
        (section.questions || []).forEach((q, idx) => {
          if (q.answer == null && sectionAnswers[idx] != null) q.answer = sectionAnswers[idx];
        });
      });
      (ex.sub_sections || []).forEach(section => {
        const sectionAnswers = Array.isArray(ex.answer_key[section.id]) ? ex.answer_key[section.id] : [];
        (section.questions || []).forEach((q, idx) => {
          if (q.answer == null && sectionAnswers[idx] != null) q.answer = sectionAnswers[idx];
        });
      });
    }

    for (const [idx, q] of (ex.questions || []).entries()) {
      if (q.answer == null) {
        const qNo = Number(questionNo(q, idx));
        const fromIndex = fallbackAnswers[qNo - 1];
        const fromInference = inferred[normId] ? inferred[normId][qNo] : undefined;
        const fromInlineKey = Array.isArray(ex.answer_key)
          ? (ex.answer_key.length === (ex.questions || []).length ? ex.answer_key[idx] : ex.answer_key[qNo - 1])
          : (ex.answer_key && typeof ex.answer_key === 'object' && ex.section && Array.isArray(ex.answer_key[ex.section])
            ? ex.answer_key[ex.section][qNo - 1]
            : undefined);
        const fromConjugated = q.answer_conjugated != null ? q.answer_conjugated : undefined;
        if (fromIndex != null) q.answer = fromIndex;
        else if (fromInlineKey != null) q.answer = fromInlineKey;
        else if (fromInference != null) q.answer = fromInference;
        else if (fromConjugated != null) q.answer = fromConjugated;
      }
    }
  }

  const exercises = data.exercises || [];
  for (let i = 0; i < exercises.length; ) {
    const groupId = normalizeId(exercises[i].id);
    let j = i;
    const grouped = [];
    while (j < exercises.length && normalizeId(exercises[j].id) === groupId) {
      grouped.push(exercises[j]);
      j += 1;
    }
    const pooledAnswers = grouped
      .flatMap(ex => Array.isArray(ex.answer_key) ? ex.answer_key : [])
      .filter(v => v != null);
    if (pooledAnswers.length > 0) {
      let cursor = 0;
      grouped.forEach(ex => {
        (ex.questions || []).forEach(q => {
          if (q.answer == null && pooledAnswers[cursor] != null) q.answer = pooledAnswers[cursor];
          cursor += 1;
        });
      });
    }
    i = j;
  }
}

function groupExercises(exercises) {
  const groups = [];
  for (const ex of exercises) {
    const type = detectType(ex);
    const id = normalizeId(ex.id);
    const prev = groups[groups.length - 1];
    if (prev && prev.id === id && prev.type === type) {
      prev.items.push(ex);
    } else {
      groups.push({ id, type, items: [ex] });
    }
  }
  return groups;
}

function createIdFactory() {
  let count = 0;
  return function makeId(prefix) {
    count += 1;
    return `${prefix}-${count}`;
  };
}

function controlAttrs(id, kind, extra = '') {
  return ` data-control-id="${esc(id)}" data-control-kind="${esc(kind)}"${extra}`;
}

function rowId(prefix, makeId) {
  return makeId(`${prefix}-row`);
}

function inputHtml(cls, ans, maxLength = 10, readOnly = false, controlId = '', kind = 'text-input') {
  const ro = readOnly ? ' readonly' : '';
  const attrs = controlId ? controlAttrs(controlId, kind) : '';
  return `<input type="text" class="${cls}" maxlength="${maxLength}" data-ans="${esc(ans)}"${ro}${attrs}>`;
}

function renderTypeAQuestion(q, idx, makeId) {
  const text = normalizeText(q.text);
  const answers = String(q.answer || '').split('、');
  const regex = /\(\s*\/\s*\)|\(\s*\)/g;
  const markId = rowId('type-a', makeId);
  let last = 0;
  let answerIndex = 0;
  let out = '';
  let match;
  while ((match = regex.exec(text)) !== null) {
    out += esc(text.slice(last, match.index));
    if (match[0].includes('/')) {
      const pair = String(answers[answerIndex] || '').split('／');
      out += `（${inputHtml('type-a', (pair[0] || '').trim(), 4, false, makeId('inp'), 'text-input')}／${inputHtml('type-a', (pair[1] || '').trim(), 4, false, makeId('inp'), 'text-input')}）`;
    } else {
      const ans = (answers[answerIndex] || '').trim();
      out += `（${inputHtml('type-a', ans, Math.max(4, ans.length + 2), false, makeId('inp'), 'text-input')}）`;
    }
    answerIndex += 1;
    last = regex.lastIndex;
  }
  out += esc(text.slice(last));
  return `<div class="q-row"${controlAttrs(markId, 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${out}</span></div>`;
}

function renderVerbTable(ex, makeId) {
  if (ex.table && Array.isArray(ex.table.rows)) {
    let answerIndex = 0;
    let body = '<table class="verb-table"><thead><tr>';
    (ex.table.headers || []).forEach(header => { body += `<th>${esc(header)}</th>`; });
    body += '</tr></thead><tbody>\n';
    (ex.table.rows || []).forEach(row => {
      body += '<tr>';
      row.forEach(cell => {
        if (cell) body += `<td>${esc(cell)}</td>`;
        else body += `<td>${inputHtml('type-a type-h', (ex.answer_key || [])[answerIndex++] || '', 12, false, makeId('inp'), 'text-input')}</td>`;
      });
      body += '</tr>\n';
    });
    body += '</tbody></table>';
    return body;
  }
  const answers = ex.answer_key || [];
  let body = '<table class="verb-table"><thead><tr><th>自動詞</th><th>他動詞</th></tr></thead><tbody>\n';
  ex.table.forEach((row, idx) => {
    const ans = answers[idx] || '';
    const left = row.intransitive ? esc(row.intransitive) : inputHtml('type-a type-h', ans, 12, false, makeId('inp'), 'text-input');
    const right = row.transitive ? esc(row.transitive) : inputHtml('type-a type-h', ans, 12, false, makeId('inp'), 'text-input');
    body += `<tr><td>${left}</td><td>${right}</td></tr>\n`;
  });
  body += '</tbody></table>';
  return body;
}

function renderTokenSentence(text, answers, blankClass, makeId, readOnly = true) {
  const parts = splitBlankText(text);
  const vals = Array.isArray(answers) ? answers : String(answers || '').split('、');
  const inputClass = readOnly ? 'blank-inp' : 'blank-inp-j';
  let out = '';
  for (let i = 0; i < parts.length; i++) {
    out += esc(parts[i]).replace(/\n/g, '<br>');
    if (i < parts.length - 1) {
      const ans = String(vals[i] || '').trim();
      if (readOnly) {
        out += `（<input type="text" class="${inputClass} ${blankClass}" readonly data-ans="${esc(ans)}"${controlAttrs(makeId('blank'), 'token-input')}>）`;
      } else {
        out += `（<input type="text" class="${inputClass} ${blankClass}" data-ans="${esc(ans)}"${controlAttrs(makeId('blank'), 'editable-token-input')}>）`;
      }
    }
  }
  return out;
}

/**
 * Renders a selectable pill list for single- or multi-choice sections.
 *
 * @param {Array<string>|object} options Raw option data from JSON.
 * @param {Function} makeId Stable control id factory for persistence.
 * @param {string} [extraClass=''] Optional extra class name.
 * @param {string} [style=''] Optional inline style for layout tweaks.
 * @returns {string} HTML fragment for the pill group.
 */
function renderPills(options, makeId, extraClass = '', style = '') {
  const cls = extraClass ? `pill-group ${extraClass}` : 'pill-group';
  const styleAttr = style ? ` style="${style}"` : '';
  return `<div class="${cls}"${styleAttr}>` + optionsArray(options).map(opt => {
    const match = String(opt).match(/^([a-d])\s+(.*)$/);
    if (match) return `<span class="pill" data-letter="${match[1]}"${controlAttrs(makeId('pill'), 'pill')}><span class="pill-label">${esc(opt)}</span></span>`;
    return `<span class="pill"${controlAttrs(makeId('pill'), 'pill')}><span class="pill-label">${esc(opt)}</span></span>`;
  }).join('') + '</div>';
}

function renderBlankTextQuestion(q, idx, text, answers, makeId, inputClass = 'type-a', maxLength = 10) {
  const parts = splitBlankText(text);
  const vals = Array.isArray(answers) ? answers : splitDelimited(answers);
  const markId = rowId('blank', makeId);
  let out = '';
  for (let i = 0; i < parts.length; i += 1) {
    out += esc(parts[i]).replace(/\n/g, '<br>');
    if (i < parts.length - 1) {
      const ans = String(vals[i] || '').trim();
      out += `（${inputHtml(inputClass, ans, Math.max(maxLength, ans.length + 2), false, makeId('inp'), 'text-input')}）`;
    }
  }
  return `<div class="q-row"${controlAttrs(markId, 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${out}</span></div>`;
}

function renderCharFillQuestion(q, idx, makeId) {
  const text = String(q.text || '');
  const blankMatches = text.match(/\(\s+\)/g) || text.match(/\(\s*\)/g) || [];
  const answer = String(q.answer || '');
  const chars = answer.length === blankMatches.length ? answer.split('') : splitDelimited(answer);
  let pos = 0;
  const markId = rowId('char', makeId);
  const out = text.replace(/\(\s+\)|\(\s*\)/g, function() {
    const ans = chars[pos] || '';
    pos += 1;
    return `(${inputHtml('type-a', ans, 4, false, makeId('inp'), 'text-input')})`;
  });
  return `<div class="q-row"${controlAttrs(markId, 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${out}</span></div>`;
}

function renderBracketInputQuestion(q, idx, makeId) {
  const text = normalizeText(q.text || '');
  const answers = splitDelimited(q.answer);
  let answerIndex = 0;
  const markId = rowId('bracket', makeId);
  const out = text.replace(/〔\s*([^〕]+?)\s*〕/g, function() {
    const ans = String(answers[answerIndex] || '').trim();
    answerIndex += 1;
    return `〔 ${inputHtml('type-a', ans, Math.max(8, ans.length + 2), false, makeId('inp'), 'text-input')} 〕`;
  }).replace(/\n/g, '<br>');
  return `<div class="q-row"${controlAttrs(markId, 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${out}</span></div>`;
}

function renderBracketChoiceQuestion(q, idx, makeId, multi = false) {
  const text = normalizeText(q.text || '');
  const answers = splitDelimited(q.answer);
  let answerIndex = 0;
  const markId = rowId('bracket', makeId);
  const pillGroupClass = multi ? 'inline-choice pill-group multi' : 'inline-choice pill-group';
  const out = text.replace(/〔\s*([^〕]+?)\s*〕/g, function(_match, rawChoices) {
    const ans = String(answers[answerIndex] || '').trim();
    answerIndex += 1;
    const choices = rawChoices.split(/\s+/).filter(Boolean);
    const pills = choices.map(function(choice) {
      return `<span class="pill"${controlAttrs(makeId('pill'), 'pill')}><span class="pill-label">${esc(choice)}</span></span>`;
    }).join('');
    return `<span class="${pillGroupClass}" data-ans="${esc(ans)}">${pills}</span>`;
  }).replace(/\n/g, '<br>');
  return `<div class="q-row"${controlAttrs(markId, 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${out}</span></div>`;
}

function inferUnderline(text) {
  const raw = String(text || '');
  const match = raw.match(/^(.*?)\s+([^\s]+)\s+(.*)$/);
  if (!match) return esc(raw);
  return `${esc(match[1])} <u>${esc(match[2])}</u> ${esc(match[3])}`.trim();
}

function highlightPromptTarget(phrase, target) {
  const rawPhrase = String(phrase || '');
  const rawTarget = String(target || '').trim();
  if (!rawPhrase) return '';
  if (!rawTarget) return esc(rawPhrase);
  const escapedTarget = rawTarget.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = rawPhrase.match(new RegExp(`^(.*?)(\\s*)(${escapedTarget})(\\s*)(.*)$`));
  if (!match) return esc(rawPhrase);
  return `${esc(match[1])}${match[2]}<u>${esc(match[3])}</u>${match[4]}${esc(match[5])}`.trim();
}

/**
 * Builds the visible prompt text for choice-heavy question types.
 *
 * @param {object} q Question payload from the JSON source.
 * @param {object} [options]
 * @param {boolean} [options.preferWordBadge=false] When true, show `word`
 *   data as a badge above the prompt text.
 * @param {boolean} [options.highlightTarget=false] When true, underline the
 *   target token inside `phrase`.
 * @returns {string} HTML fragment for the prompt area.
 */
function renderPromptContent(q, options = {}) {
  const preferWordBadge = !!options.preferWordBadge;
  const highlightTarget = !!options.highlightTarget;
  const parts = [];
  const phrase = q.phrase || q.text || '';
  const badge = q.word || (preferWordBadge && !phrase ? q.target : '');
  if (badge) parts.push(`<div class="word-badge">${esc(badge)}</div>`);
  if (phrase) {
    const phraseHtml = highlightTarget
      ? highlightPromptTarget(phrase, q.target)
      : esc(normalizeText(phrase));
    parts.push(`<span class="s3-phrase">${phraseHtml}</span>`);
  }
  return parts.join('');
}

function categoryAnswers(answerKey, id) {
  const raw = answerKey && typeof answerKey === 'object' ? answerKey[id] : null;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap(entry => splitDelimited(entry));
}

function stripBracketChoices(text) {
  return normalizeText(text).replace(/〔[^〕]*〕/g, '〔 〕');
}

function choiceOptions(q) {
  if (Array.isArray(q.options)) return optionsArray(q.options);
  const match = String(q.text || '').match(/〔\s*([^〕]+?)\s*〕/);
  if (!match) return [];
  return match[1].split(/\s+/).filter(Boolean);
}

function countHint(text) {
  const match = String(text || '').match(/[（(]([0-9０-９]+)[）)]/);
  return match ? match[1] : '';
}

function toPosixPath(filePath) {
  return filePath.split(path.sep).join('/');
}

function repoRelative(filePath) {
  return toPosixPath(path.relative(ROOT, filePath));
}

function pageTitle(data) {
  const unitTitle = String(data._unit_title || 'Test').trim();
  const label = pageLabel(data.exercises || []);
  return label ? `${unitTitle} ${label}` : unitTitle;
}

function resolveOutputPath(absJson, suffix = '.html', explicitSuffix = false, outRoot = DEFAULT_OUTPUT_ROOT) {
  if (outRoot) {
    const rel = path.relative(DATA_ROOT, absJson);
    return path.join(outRoot, rel).replace(/\.json$/i, suffix);
  }
  if (explicitSuffix) return absJson.replace(/\.json$/i, suffix);
  const codexOut = absJson.replace(/\.json$/i, '_codex.html');
  if (fs.existsSync(codexOut)) return codexOut;
  return absJson.replace(/\.json$/i, suffix);
}

function preferredHtmlForJson(absJson, outputRoot = DEFAULT_OUTPUT_ROOT) {
  if (outputRoot) {
    const rel = path.relative(DATA_ROOT, absJson);
    return path.join(outputRoot, rel).replace(/\.json$/i, '.html');
  }
  const codexPath = absJson.replace(/\.json$/i, '_codex.html');
  const htmlPath = absJson.replace(/\.json$/i, '.html');
  if (fs.existsSync(codexPath)) return codexPath;
  if (fs.existsSync(htmlPath)) return htmlPath;
  return null;
}

/**
 * Converts one JSON exercise file into a standalone interactive HTML page.
 *
 * @param {object} data Parsed exercise JSON payload.
 * @param {string} filename Source JSON file name.
 * @param {string} outPath Output HTML path.
 * @param {string} sourceJsonPath Absolute source JSON path.
 * @returns {string} Fully rendered HTML document.
 */
function buildHtml(data, filename, outPath, sourceJsonPath) {
  fillAnswers(filename, data);
  const groups = groupExercises(data.exercises);
  const initCalls = [];
  const sections = [];
  const makeId = createIdFactory();

  groups.forEach((group, index) => {
    const sectionNo = index + 1;
    const secId = `sec${group.type}${sectionNo}`;
    const first = group.items[0];
    let html = `  <div class="section" id="${secId}">\n`;
    html += `    <div class="section-title">${esc(group.id)}</div>\n`;
    html += `    <div class="section-q">${esc(first.instruction)}</div>\n`;

    if (group.type === 'A') {
      first.questions.forEach((q, idx) => {
        html += `    ${renderTypeAQuestion(q, idx, makeId)}\n`;
      });
    } else if (group.type === 'H') {
      html += `    ${renderVerbTable(first, makeId)}\n`;
    } else if (group.type === 'B') {
      const rawAnswers = Array.isArray(first.answer_key)
        ? first.answer_key
        : (((first.questions || [])[0] || {}).answer != null ? [((first.questions || [])[0] || {}).answer] : null);
      const answers = rawAnswers ? parseCheckboxAnswers(rawAnswers) : null;
      if (first.example) html += `    <div class="hint">${esc(first.example)}</div>\n`;
      html += '    <div class="word-grid">\n';
      (first.words || first.options || first.word_bank || first.choices || ((first.questions || [])[0] || {}).options || []).forEach(word => {
        const label = normalizeItem(word);
        const answerAttr = answers ? ` data-ans="${answers.has(label) ? 'true' : 'false'}"` : '';
        html += `      <label class="word-item"${answerAttr}${controlAttrs(makeId('checkbox'), 'checkbox-item')}><input type="checkbox"> ${esc(label)}</label>\n`;
      });
      html += '    </div>\n';
    } else if (group.type === 'O') {
      const bankId = `bank${sectionNo}`;
      if (first.header) html += `    <div class="hint">${esc(first.header)}</div>\n`;
      if (Array.isArray(first.word_bank) && first.word_bank.length) {
        html += '    <div class="hint">Click a blank, then click a word from the bank.</div>\n';
      }
      if (first.questions.some(q => q.left || q.right)) {
        first.questions.forEach((q, idx) => {
          const markId = rowId('pair', makeId);
          if (String(questionNo(q, idx)) === '例') {
            html += `    <div class="q-row"${controlAttrs(markId, 'markable')}><span class="q-num">例</span><span class="q-text">${esc(q.left || '')} ${esc(q.right || '')}</span></div>\n`;
            return;
          }
          const pair = String(q.answer || '').split('ー');
          html += `    <div class="q-row"${controlAttrs(markId, 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">（${inputHtml('type-a', (pair[0] || '').trim(), 10, false, makeId('inp'), 'text-input')}） - （${inputHtml('type-a', (pair[1] || '').trim(), 10, false, makeId('inp'), 'text-input')}）</span></div>\n`;
        });
      } else {
        const exampleLabel = (first.questions[0] || {}).text;
        const exampleRow = first.questions.find(q => String(q.index || q.id || '') === '例');
        if (exampleLabel) html += `    <div class="hint">${esc(exampleLabel)}</div>\n`;
        if (exampleRow) html += `    <div class="q-row"${controlAttrs(rowId('pair-example', makeId), 'markable')}><span class="q-num">例</span><span class="q-text">${esc(exampleRow.text || '')}</span></div>\n`;
        (first.answer_key || []).forEach((pairText, idx) => {
          const pair = String(pairText).split('ー');
          html += `    <div class="q-row"${controlAttrs(rowId('pair', makeId), 'markable')}><span class="q-num">${idx + 1}.</span><span class="q-text">(${inputHtml('type-a', (pair[0] || '').trim(), 10, false, makeId('inp'), 'text-input')}) - (${inputHtml('type-a', (pair[1] || '').trim(), 10, false, makeId('inp'), 'text-input')})</span></div>\n`;
        });
      }
      if (Array.isArray(first.word_bank)) {
        initCalls.push(`initTokenAssistSection('#${secId} input.type-a', '${bankId}');`);
        html += `    <div class="token-bank" id="${bankId}">\n`;
        first.word_bank.forEach(word => {
          const val = normalizeItem(word);
          html += `      <span class="token" data-val="${esc(val)}"${controlAttrs(makeId('token'), 'token')}>${esc(val)}</span>\n`;
        });
        html += '    </div>\n';
      }
    } else if (group.type === 'P') {
      first.questions.forEach((q, idx) => {
        html += `    ${renderBlankTextQuestion(q, idx, q.text || '', q.answer || '', makeId, 'type-a', 6)}\n`;
      });
      if (Array.isArray(first.word_bank)) {
        html += '    <div class="token-bank">\n';
        first.word_bank.forEach(word => {
          const symbol = word.symbol ? `${word.symbol}. ` : '';
          const val = word.kanji || word.word || word.reading || '';
          html += `      <span class="token"${controlAttrs(makeId('token'), 'token')}>${esc(symbol + val)}</span>\n`;
        });
        html += '    </div>\n';
      }
    } else if (group.type === 'Q') {
      const mergedQuestions = group.items.flatMap(item => item.questions || []);
      mergedQuestions.forEach((q, idx) => {
        html += `    ${renderBracketChoiceQuestion(q, idx, makeId, true)}\n`;
      });
    } else if (group.type === 'T') {
      first.questions.forEach((q, idx) => {
        html += `    ${renderCharFillQuestion(q, idx, makeId)}\n`;
      });
    } else if (group.type === 'R') {
      first.sections.forEach(section => {
        html += `    <div class="section-sub">${esc(section.id)}</div>\n`;
        section.questions.forEach((q, idx) => {
          html += `    ${renderBlankTextQuestion(q, idx, q.text || '', q.answer || '', makeId, 'type-a', 12)}\n`;
        });
        if (Array.isArray(section.word_bank)) {
          html += '    <div class="token-bank">\n';
          section.word_bank.forEach(word => {
            const val = normalizeItem(word);
            html += `      <span class="token"${controlAttrs(makeId('token'), 'token')}>${esc(val)}</span>\n`;
          });
          html += '    </div>\n';
        }
      });
    } else if (group.type === 'C') {
      first.questions.forEach((q, idx) => {
        html += `    <div class="s3-row" data-ans="${esc(q.answer || '')}"${controlAttrs(rowId('choice', makeId), 'markable')}><span class="s3-label">${esc(questionKey(q, idx))}.</span><span class="s3-phrase">${esc(stripBracketChoices(q.phrase || q.text))}</span>${renderPills(choiceOptions(q), makeId)}</div>\n`;
      });
    } else if (group.type === 'D') {
      const blankClass = `s${sectionNo}b`;
      const bankId = `bank${sectionNo}`;
      initCalls.push(`initTokenSection('${blankClass}', '${bankId}');`);
      html += '    <div class="hint">Click a blank, then click a word from the bank.</div>\n';
      html += '    <div class="compound-grid">\n';
      first.questions.forEach((q, idx) => {
        const parts = splitBlankText(q.text || '');
        const prefix = q.prefix ?? q.base ?? parts[0] ?? '';
        const suffix = q.suffix ?? parts[1] ?? '';
        html += `      <div class="compound-item"${controlAttrs(rowId('compound', makeId), 'markable')}><span>${esc(questionKey(q, idx))}. ${esc(prefix)}（</span><input type="text" class="blank-inp ${blankClass}" readonly data-ans="${esc(q.answer || q.hint || '')}"${controlAttrs(makeId('blank'), 'token-input')}><span>）${esc(suffix)}</span></div>\n`;
      });
      html += '    </div>\n';
      html += `    <div class="token-bank" id="${bankId}">\n`;
      (first.word_bank || first.options || first.choices || []).forEach(word => {
        const val = normalizeItem(word);
        html += `      <span class="token" data-val="${esc(val)}"${controlAttrs(makeId('token'), 'token')}>${esc(val)}</span>\n`;
      });
      html += '    </div>\n';
    } else if (group.type === 'G') {
      const blankClass = `s${sectionNo}b`;
      const bankId = `bank${sectionNo}`;
      initCalls.push(`initTokenSection('${blankClass}', '${bankId}');`);
      html += '    <div class="hint">Click a blank, then click a word from the bank.</div>\n';
      const wordBankItems = first.word_bank || first.options || first.choices || [];
      const symToWord = new Map();
      wordBankItems.forEach(word => {
        if (typeof word === 'object' && word !== null && word.symbol) symToWord.set(word.symbol, normalizeItem(word));
      });
      first.questions.forEach((q, idx) => {
        const ans = symToWord.size > 0
          ? String(q.answer || '').split('、').map(s => symToWord.get(s.trim()) || s.trim()).join('、')
          : q.answer;
        html += `    <div class="q-row"${controlAttrs(rowId('token-row', makeId), 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${renderTokenSentence(q.text, ans, blankClass, makeId, true)}</span></div>\n`;
      });
      html += `    <div class="token-bank" id="${bankId}">\n`;
      wordBankItems.forEach(word => {
        const symbol = (typeof word === 'object' && word !== null) ? (word.symbol || null) : null;
        const val = normalizeItem(word);
        const display = symbol ? `${symbol} ${val}` : val;
        html += `      <span class="token" data-val="${esc(val)}"${controlAttrs(makeId('token'), 'token')}>${esc(display)}</span>\n`;
      });
      html += '    </div>\n';
    } else if (group.type === 'I') {
      const bankOptions = normalizeList(first.word_bank || first.options || []);
      first.questions.forEach((q, idx) => {
        const answers = Array.isArray(q.answer) ? q.answer : splitDelimited(q.answer);
        const hint = countHint(q.text);
        const phrase = normalizeText(q.text).replace(/[（(][0-9０-９]+[）)]/, '').trim();
        html += `    <div class="mi-row" data-ans='${esc(JSON.stringify(answers))}'${controlAttrs(rowId('multi', makeId), 'markable')}>\n`;
        html += `      <div class="q-row"><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${esc(phrase)}</span></div>\n`;
        if (hint) html += `      <div class="hint">えらぶ数：${esc(hint)}</div>\n`;
        html += `      ${renderPills(bankOptions.length ? bankOptions : choiceOptions(q), makeId, 'multi')}\n`;
        html += '    </div>\n';
      });
    } else if (group.type === 'U') {
      const bankOptions = normalizeList(first.word_bank || []);
      first.categories.forEach((category, idx) => {
        const answers = categoryAnswers(first.answer_key, category.id);
        const attrs = answers.length ? ` data-ans='${esc(JSON.stringify(answers))}'` : '';
        html += `    <div class="mi-row"${attrs}${controlAttrs(rowId('category', makeId), 'markable')}>\n`;
        html += `      <div class="q-row"><span class="q-num">${esc(category.id || questionKey(category, idx))}.</span><span class="q-text">${esc(category.label || '')}</span></div>\n`;
        html += `      ${renderPills(bankOptions, makeId, 'multi')}\n`;
        html += '    </div>\n';
      });
    } else if (group.type === 'E' || group.type === 'S') {
      first.questions.forEach((q, idx) => {
        const parts = splitBlankText(q.text || '');
        html += `    <div class="q-row"${controlAttrs(rowId('write', makeId), 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${esc(parts[0])}（${inputHtml('type-a', q.answer || '', 14, false, makeId('inp'), 'text-input')}）${esc(parts[1] || '')}</span></div>\n`;
      });
    } else if (group.type === 'J') {
      html += '    <div class="hint">Click a word from the bank to fill the blank, then edit it to the correct form.</div>\n';
      if (Array.isArray(first.sections)) {
        first.sections.forEach((section, idxSection) => {
          const blankClass = `sJ${sectionNo}_${idxSection + 1}b`;
          const bankId = `bankJ${sectionNo}_${idxSection + 1}`;
          initCalls.push(`initTokenSectionJ('${blankClass}', '${bankId}');`);
          html += `    <div class="section-sub">${esc(section.id)}</div>\n`;
          section.questions.forEach((q, idx) => {
            html += `    <div class="q-row"${controlAttrs(rowId('edit', makeId), 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${renderTokenSentence(q.text, q.answer || q.answer_conjugated, blankClass, makeId, false)}</span></div>\n`;
          });
          html += `    <div class="token-bank" id="${bankId}">\n`;
          (section.word_bank || []).forEach(word => {
            const val = normalizeItem(word);
            html += `      <span class="token" data-val="${esc(val)}"${controlAttrs(makeId('token'), 'token')}>${esc(val)}</span>\n`;
          });
          html += '    </div>\n';
        });
      } else {
        const blankClass = `sJ${sectionNo}b`;
        const bankId = `bankJ${sectionNo}`;
        initCalls.push(`initTokenSectionJ('${blankClass}', '${bankId}');`);
        first.questions.forEach((q, idx) => {
          html += `    <div class="q-row"${controlAttrs(rowId('edit', makeId), 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${renderTokenSentence(q.text, q.answer || q.answer_conjugated, blankClass, makeId, false)}</span></div>\n`;
        });
        html += `    <div class="token-bank" id="${bankId}">\n`;
        (first.word_bank || first.options || []).forEach(word => {
          const val = normalizeItem(word);
          html += `      <span class="token" data-val="${esc(val)}"${controlAttrs(makeId('token'), 'token')}>${esc(val)}</span>\n`;
        });
        html += '    </div>\n';
      }
    } else if (group.type === 'K') {
      first.questions.forEach((q, idx) => {
        html += `    <div class="s3-row" data-ans="${esc(q.answer || '')}"${controlAttrs(rowId('mcq', makeId), 'markable')}><span class="s3-label">${esc(questionKey(q, idx))}.</span><div style="flex:1">${renderPromptContent(q, { preferWordBadge: true })}${renderPills(q.options, makeId, '', 'margin-top:6px')}</div></div>\n`;
      });
    } else if (group.type === 'L') {
      const mergedQuestions = group.items.flatMap(item => item.questions || []);
      let flatAnswers = [];
      group.items.forEach(item => {
        if (Array.isArray(item.answer_key)) flatAnswers = flatAnswers.concat(item.answer_key);
      });
      mergedQuestions.forEach((q, idx) => {
        const ans = q.answer || flatAnswers[idx] || '';
        html += `    <div class="s3-row" data-ans="${esc(ans)}"${controlAttrs(rowId('syn', makeId), 'markable')}><span class="s3-label">${esc(questionKey(q, idx))}.</span><div style="flex:1">${renderPromptContent(q, { highlightTarget: true })}${renderPills(q.options, makeId, '', 'margin-top:6px')}</div></div>\n`;
      });
    } else if (group.type === 'M') {
      first.questions.forEach((q, idx) => {
        html += `    <div class="s3-row" data-ans="${esc(q.answer || '')}"${controlAttrs(rowId('usage', makeId), 'markable')}><span class="s3-label">${esc(questionKey(q, idx))}.</span><div style="flex:1">${renderPromptContent(q, { preferWordBadge: true })}${renderPills(q.options, makeId, 'vertical', 'margin-top:6px')}</div></div>\n`;
      });
    } else if (group.type === 'N') {
      if (Array.isArray(first.sub_sections)) {
        first.sub_sections.forEach(sub => {
          html += `    <div class="section-sub">${esc(sub.id)} ${esc(sub.label || '')}</div>\n`;
          sub.questions.forEach((q, idx) => {
            html += `    <div class="q-row"${controlAttrs(rowId('sub', makeId), 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${esc(q.text)} → ${inputHtml('type-a', q.answer || '', Math.max(8, String(q.answer || '').length + 2), false, makeId('inp'), 'text-input')}</span></div>\n`;
          });
        });
      } else {
        first.questions.forEach((q, idx) => {
          html += `    <div class="q-row"${controlAttrs(rowId('sub', makeId), 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${esc(q.text)} → ${inputHtml('type-a', q.answer || '', Math.max(8, String(q.answer || '').length + 2), false, makeId('inp'), 'text-input')}</span></div>\n`;
        });
      }
    }

    html += '  </div>';
    sections.push(html);
  });

  const metadata = {
    pageId: repoRelative(outPath),
    pageTitle: pageTitle(data),
    unitLabel: path.basename(path.dirname(outPath)),
    sourceJson: repoRelative(sourceJsonPath)
  };

  const js = `${SHARED_PAGE_JS}\n${initCalls.join('\n')}\ndocument.querySelectorAll('.blank-inp, .blank-inp-j').forEach(setBlankWidth);\ninitPersistence();\nrestorePageState();`;
  const backHref = '../index.html';
  const pageCss = `${CSS}\n${EXTRA_PAGE_CSS}`;

  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${esc(pageTitle(data))}</title>
<style>
${pageCss}
</style>
</head>
<body>
<div class="page">
  <div class="page-topbar">
    <a class="back-link" href="${backHref}">← Back to Main Page</a>
  </div>
  <h1>${esc(data._unit_title)} <span>${esc(pageLabel(data.exercises))}</span></h1>

${sections.join('\n\n')}

  <div class="score-bar" id="score-bar"></div>
  <div class="btn-row">
    <button class="btn-clear" onclick="clearAll()">↺ Clear All</button>
    <button class="btn-check" onclick="checkAnswers()">✓ Check Answers</button>
    <button class="btn-export" onclick="exportAnswers()">↗ Export for AI Review</button>
  </div>
  <div class="export-box" id="export-box">
    <textarea id="export-text" readonly></textarea>
    <button class="copy-btn" onclick="copyExport()">Copy to clipboard</button>
  </div>
</div>
<script>
window.TEST_PAGE_META = ${JSON.stringify(metadata)};
</script>
<script>
${js}
</script>
</body>
</html>
`;
}

function walkFiles(rootDir, predicate, results = []) {
  if (!fs.existsSync(rootDir)) return results;
  fs.readdirSync(rootDir).sort().forEach(name => {
    const abs = path.join(rootDir, name);
    const stat = fs.statSync(abs);
    if (stat.isDirectory()) {
      walkFiles(abs, predicate, results);
    } else if (predicate(abs)) {
      results.push(abs);
    }
  });
  return results;
}

function collectGuideEntriesFromJson(outputRoot = null, jsonRoot = DATA_ROOT) {
  const htmlRoot = outputRoot || DATA_ROOT;
  const entries = [];
  walkFiles(jsonRoot, file => file.endsWith('.json')).forEach(jsonPath => {
    const htmlPath = preferredHtmlForJson(jsonPath, outputRoot);
    if (!htmlPath) return;
    const data = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
    const dirName = path.basename(path.dirname(jsonPath));
    entries.push({
      pageId: repoRelative(htmlPath),
      href: toPosixPath(path.relative(htmlRoot, htmlPath)),
      pageTitle: pageTitle(data),
      pageLabel: pageLabel(data.exercises || []),
      unitLabel: dirName,
      unitTitle: data._unit_title || dirName,
      sourceJson: repoRelative(jsonPath)
    });
  });
  return entries;
}

function parseEmbeddedPageMeta(html) {
  const metaMatch = html.match(/window\.TEST_PAGE_META\s*=\s*(\{[\s\S]*?\});/);
  if (!metaMatch) return null;
  try {
    return JSON.parse(metaMatch[1]);
  } catch (err) {
    return null;
  }
}

function collectGuideEntriesFromHtml(htmlRoot = DEFAULT_OUTPUT_ROOT) {
  const entries = [];
  walkFiles(htmlRoot, file => file.endsWith('.html') && path.basename(file).toLowerCase() !== 'index.html').forEach(htmlPath => {
    const html = fs.readFileSync(htmlPath, 'utf8');
    const meta = parseEmbeddedPageMeta(html) || {};
    const titleMatch = html.match(/<title>([\s\S]*?)<\/title>/i);
    const h1Match = html.match(/<h1>([\s\S]*?)<\/h1>/i);
    const unitLabel = path.basename(path.dirname(htmlPath));
    entries.push({
      pageId: meta.pageId || repoRelative(htmlPath),
      href: toPosixPath(path.relative(htmlRoot, htmlPath)),
      pageTitle: meta.pageTitle || (titleMatch ? titleMatch[1].replace(/<[^>]+>/g, '').trim() : path.basename(htmlPath, '.html')),
      pageLabel: '',
      unitLabel,
      unitTitle: h1Match ? h1Match[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim() : unitLabel,
      sourceJson: meta.sourceJson || ''
    });
  });
  return entries;
}

function buildGuideHtml(entries) {
  const guideCss = `
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Hiragino Sans', 'Meiryo', sans-serif; background: #f5f4f0; color: #1a1a1a; }
.page { max-width: 980px; margin: 0 auto; padding: 32px 20px 60px; }
h1 { font-size: 28px; margin-bottom: 8px; }
.intro { color: #666; margin-bottom: 24px; line-height: 1.7; }
.section { margin-bottom: 28px; }
.section h2 { font-size: 18px; margin-bottom: 14px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }
.group { margin-bottom: 24px; }
.group-title { font-size: 16px; font-weight: 700; margin-bottom: 10px; }
.card { display: block; text-decoration: none; color: inherit; background: #fff; border: 1px solid #ddd; border-radius: 10px; padding: 16px; transition: transform 0.15s, border-color 0.15s, box-shadow 0.15s; }
.card:hover { transform: translateY(-1px); border-color: #1a55a0; box-shadow: 0 10px 24px rgba(0,0,0,0.06); }
.card-top { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; margin-bottom: 8px; }
.card-title { font-size: 16px; font-weight: 700; line-height: 1.5; }
.card-meta { font-size: 12px; color: #666; margin-bottom: 6px; }
.card-sub { font-size: 13px; color: #555; }
.badge { font-size: 12px; font-weight: 700; border-radius: 999px; padding: 4px 10px; border: 1px solid #ccc; white-space: nowrap; }
.badge.not-started { background: #f5f5f5; color: #666; }
.badge.in-progress { background: #eef3fb; color: #1a55a0; border-color: #1a55a0; }
.badge.checked { background: #eafaf0; color: #1a6e35; border-color: #2a9d4a; }
.empty { background: #fff; border: 1px dashed #c8c8c8; border-radius: 10px; padding: 18px; color: #666; }
`;
  const guideJs = `
const GUIDE_ENTRIES = ${JSON.stringify(entries)};
const STORAGE_INDEX_KEY = 'n3-tests/index/v1';

function loadGuideIndex() {
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_INDEX_KEY) || '{}');
  } catch (err) {
    return {};
  }
}

function statusClass(status) {
  if (status === 'Checked') return 'checked';
  if (status === 'In progress') return 'in-progress';
  return 'not-started';
}

function entryState(entry, index) {
  const saved = index[entry.pageId] || {};
  return {
    pageId: entry.pageId,
    href: entry.href,
    pageTitle: entry.pageTitle,
    unitLabel: entry.unitLabel,
    unitTitle: entry.unitTitle,
    pageLabel: entry.pageLabel,
    status: saved.status || 'Not started',
    updatedAt: saved.updatedAt || '',
    checkedAt: saved.checkedAt || '',
    score: saved.score || null
  };
}

function compareResume(a, b) {
  const priority = { 'In progress': 0, 'Checked': 1, 'Not started': 2 };
  const pa = priority[a.status] ?? 9;
  const pb = priority[b.status] ?? 9;
  if (pa !== pb) return pa - pb;
  return String(b.updatedAt || '').localeCompare(String(a.updatedAt || ''));
}

function cardHtml(item) {
  const scoreText = item.score && item.score.total ? 'Latest score: ' + item.score.correct + '/' + item.score.total : (item.updatedAt ? 'Last used: ' + new Date(item.updatedAt).toLocaleString() : 'No saved progress yet');
  return '<a class="card" href="' + item.href + '">' +
    '<div class="card-top">' +
      '<div class="card-title">' + item.pageTitle + '</div>' +
      '<span class="badge ' + statusClass(item.status) + '">' + item.status + '</span>' +
    '</div>' +
    '<div class="card-meta">' + item.unitLabel + '</div>' +
    '<div class="card-sub">' + scoreText + '</div>' +
  '</a>';
}

function renderGuide() {
  const index = loadGuideIndex();
  const entries = GUIDE_ENTRIES.map(function(entry) { return entryState(entry, index); });
  const resume = entries.filter(function(entry) { return entry.status !== 'Not started'; }).sort(compareResume);
  document.getElementById('resume-list').innerHTML = resume.length ? resume.map(cardHtml).join('') : '<div class="empty">Saved progress will show up here after you start a test.</div>';

  const grouped = {};
  entries.forEach(function(entry) {
    if (!grouped[entry.unitLabel]) grouped[entry.unitLabel] = [];
    grouped[entry.unitLabel].push(entry);
  });
  const groupedHtml = Object.keys(grouped).sort().map(function(unitLabel) {
    const cards = grouped[unitLabel].sort(function(a, b) { return a.pageTitle.localeCompare(b.pageTitle); }).map(cardHtml).join('');
    return '<div class="group"><div class="group-title">' + unitLabel + '</div><div class="cards">' + cards + '</div></div>';
  }).join('');
  document.getElementById('all-tests').innerHTML = groupedHtml;
}

window.addEventListener('storage', function(event) {
  if (event.key === STORAGE_INDEX_KEY) renderGuide();
});

renderGuide();
`;

  return `<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>N2 語彙 練習問題</title>
<style>
${guideCss}
</style>
</head>
<body>
<div class="page">
  <h1>N2 語彙 練習問題</h1>
  <p class="intro">Use this page as the main entry point for all N2 vocabulary exercises. Your latest progress is restored automatically inside each exercise page, and recent work appears at the top here.</p>

  <section class="section">
    <h2>Resume</h2>
    <div class="cards" id="resume-list"></div>
  </section>

  <section class="section">
    <h2>All Tests</h2>
    <div id="all-tests"></div>
  </section>
</div>
<script>
${guideJs}
</script>
</body>
</html>
`;
}

function writeGuidePage(outputRoot = DEFAULT_OUTPUT_ROOT, entries = null) {
  const guideRoot = outputRoot || DATA_ROOT;
  const guidePath = path.join(guideRoot, 'index.html');
  fs.mkdirSync(path.dirname(guidePath), { recursive: true });
  fs.writeFileSync(guidePath, buildGuideHtml(entries || collectGuideEntriesFromHtml(outputRoot)));
  return guidePath;
}

function parseGenerateOptions(args) {
  let suffix = '.html';
  let explicitSuffix = false;
  let outRoot = DEFAULT_OUTPUT_ROOT;
  let htmlRoot = DEFAULT_OUTPUT_ROOT;
  const positional = [];
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === '--suffix') {
      suffix = args[i + 1] || '.html';
      explicitSuffix = true;
      i += 1;
    } else if (args[i] === '--out-root') {
      outRoot = path.resolve(ROOT, args[i + 1] || '.');
      i += 1;
    } else if (args[i] === '--html-root') {
      htmlRoot = path.resolve(ROOT, args[i + 1] || '.');
      i += 1;
    } else if (args[i] === '--build-index') {
      positional.push(args[i]);
    } else {
      positional.push(args[i]);
    }
  }
  return { suffix, explicitSuffix, outRoot, htmlRoot, positional };
}

function generateFiles(files, options = {}) {
  const suffix = options.suffix || '.html';
  const explicitSuffix = !!options.explicitSuffix;
  const outRoot = options.outRoot || DEFAULT_OUTPUT_ROOT;
  const outputs = [];
  const entries = [];
  if (files.length === 0) {
    throw new Error('No JSON files were provided.');
  }

  for (const rel of files) {
    const abs = path.resolve(ROOT, rel);
    const out = resolveOutputPath(abs, suffix, explicitSuffix, outRoot);
    const rawData = JSON.parse(fs.readFileSync(abs, 'utf8'));
    const data = enrichMissingAnswers(path.basename(abs), rawData, { answerPagesDir: ANSWER_PAGES_DIR });
    const html = buildHtml(data, path.basename(abs), out, abs);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, html);
    const dirName = path.basename(path.dirname(abs));
    entries.push({
      pageId: repoRelative(out),
      href: toPosixPath(path.relative(outRoot, out)),
      pageTitle: pageTitle(data),
      pageLabel: pageLabel(data.exercises || []),
      unitLabel: dirName,
      unitTitle: data._unit_title || dirName,
      sourceJson: repoRelative(abs)
    });
    outputs.push(out);
  }

  return { outputs, entries, outRoot };
}

function generateFolder(jsonRoot, options = {}) {
  const absRoot = path.resolve(ROOT, jsonRoot);
  const files = walkFiles(absRoot, file => file.endsWith('.json') && !file.includes(`${path.sep}answerPages${path.sep}`))
    .map(file => path.relative(ROOT, file))
    .sort();
  return generateFiles(files, options);
}

function printUsage() {
  console.error('Usage:');
  console.error('  node scripts/json_to_test.js generate [--suffix _codex.html] [--out-root ..\\N3WordsDigital\\exercise] <json-file> [...]');
  console.error('  node scripts/json_to_test.js generate-folder [--suffix _codex.html] [--out-root ..\\N3WordsDigital\\exercise] [--build-index] <json-folder>');
  console.error('  node scripts/json_to_test.js build-index [--html-root ..\\N3WordsDigital\\exercise]');
}

function main(args) {
  const command = args[0] && !args[0].startsWith('--') ? args[0] : 'generate';
  const defaultArgs = command === args[0] ? args.slice(1) : args;
  const parsed = parseGenerateOptions(defaultArgs);

  if (command === 'generate') {
    const { suffix, explicitSuffix, outRoot, positional } = parsed;
    if (positional.length === 0) {
      printUsage();
      process.exit(1);
    }
    const result = generateFiles(positional, { suffix, explicitSuffix, outRoot });
    result.outputs.forEach(out => console.log(out));
    return;
  }

  if (command === 'generate-folder') {
    const buildIndex = parsed.positional.includes('--build-index');
    const positional = parsed.positional.filter(arg => arg !== '--build-index');
    const { suffix, explicitSuffix, outRoot } = parsed;
    if (positional.length !== 1) {
      printUsage();
      process.exit(1);
    }
    const result = generateFolder(positional[0], { suffix, explicitSuffix, outRoot });
    result.outputs.forEach(out => console.log(out));
    if (buildIndex) console.log(writeGuidePage(result.outRoot, result.entries));
    return;
  }

  if (command === 'build-index') {
    console.log(writeGuidePage(parsed.htmlRoot, collectGuideEntriesFromHtml(parsed.htmlRoot)));
    return;
  }

  printUsage();
  process.exit(1);
}

main(process.argv.slice(2));
