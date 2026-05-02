/**
 * Render-type classifier for test JSON.
 *
 * This is the only place that should inspect exercise structure or instruction
 * text to choose a renderer. json_to_test.js and test_page_builder.js consume
 * the resulting render_type tags instead of adding more ad hoc guesses.
 */
const RENDER_TYPE_CODES = {
  particle_fill: 'A',
  checkbox: 'B',
  word_checkbox: 'B',
  single_choice: 'C',
  token_compound: 'D',
  token_fill: 'G',
  table: 'H',
  multi_select: 'I',
  editable_token: 'J',
  letter_choice: 'K',
  synonym_choice: 'L',
  usage_choice: 'M',
  subsection: 'N',
  pair: 'O',
  symbol_fill: 'P',
  bracket_multi: 'Q',
  sectioned_write: 'R',
  short_form: 'S',
  char_fill: 'T',
  categorization: 'U',
  write_in: 'W',
  typed_answer: 'W',
  raw_text: 'RAW',
  unstructured: 'RAW'
};

const CODE_TO_CANONICAL = {
  A: 'particle_fill',
  B: 'checkbox',
  C: 'single_choice',
  D: 'token_compound',
  G: 'token_fill',
  H: 'table',
  I: 'multi_select',
  J: 'editable_token',
  K: 'letter_choice',
  L: 'synonym_choice',
  M: 'usage_choice',
  N: 'subsection',
  O: 'pair',
  P: 'symbol_fill',
  Q: 'bracket_multi',
  R: 'sectioned_write',
  S: 'short_form',
  T: 'char_fill',
  U: 'categorization',
  W: 'write_in',
  RAW: 'raw_text'
};

function normalizeRenderKey(type) {
  return String(type || '').trim().toLowerCase().replace(/[-\s]+/g, '_');
}

function normalizeRenderType(type) {
  const raw = String(type || '').trim();
  const upper = raw.toUpperCase();
  if (CODE_TO_CANONICAL[upper]) return upper;
  return RENDER_TYPE_CODES[normalizeRenderKey(raw)] || null;
}

function canonicalRenderType(type) {
  const code = normalizeRenderType(type);
  return code ? CODE_TO_CANONICAL[code] : null;
}

function normalizeItem(item) {
  if (typeof item === 'string') return item;
  if (!item || typeof item !== 'object') return String(item || '');
  return item.kanji || item.word || item.text || item.reading || item.label || item.value || '';
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

function hasCountHint(text) {
  return /[（(][0-9０-９]+[）)]/.test(String(text || ''));
}

function hasChoiceCountQuestion(questions) {
  return (questions || []).some(q => /〔/.test(String(q.text || '')) && hasCountHint(q.text || ''));
}

function hasBracketPrompt(questions) {
  return (questions || []).some(q => /〔|\[/.test(String(q.text || '')));
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

function hasRenderableQuestionText(questions) {
  return (questions || []).some(q => q && q.answer != null && (q.text || q.word || q.phrase));
}

function hasVisibleRawContent(ex) {
  if (String(ex.instruction || '').trim()) return true;
  if ((ex.words || []).map(normalizeItem).filter(Boolean).length) return true;
  if ((ex.questions || []).some(q => q && (q.text || q.word || q.phrase || q.left || q.right))) return true;
  return false;
}

function inferRenderType(ex) {
  const existing = canonicalRenderType(ex.render_type || ex.type);
  if (existing) return existing;

  const instruction = ex.instruction || '';
  const questions = ex.questions || [];
  const firstQ = questions[0] || {};
  const standaloneWordList = hasStandaloneWordList(ex);
  const choiceCountQuestion = hasChoiceCountQuestion(questions);
  const bracketPrompt = hasBracketPrompt(questions);
  const belowSelectionPrompt = instruction.includes('下から') && (instruction.includes('えら') || instruction.includes('選'));
  const circlePrompt = /[◯〇○]/.test(instruction);
  const inlineOptionList = Array.isArray(firstQ.options) && !firstQ.text && !firstQ.phrase;

  if (isCategorizationExercise(ex)) return 'categorization';
  if (isSubSectionExercise(ex)) return 'subsection';
  if (isTableExercise(ex)) return 'table';
  if (isEditableSectionTokenExercise(ex)) return 'editable_token';
  if (isSectionedExercise(ex)) return 'sectioned_write';
  if (isPairExercise(ex, firstQ)) return 'pair';
  if (isTokenCompositionExercise(ex, firstQ)) return 'token_compound';
  if (isConjugationExercise(ex) && (Array.isArray(ex.options) || Array.isArray(ex.word_bank))) return 'editable_token';
  if (isUsagePromptExercise(ex, firstQ)) return 'usage_choice';
  if (instruction.includes('意味が最も近い')) return 'synonym_choice';
  if (choiceCountQuestion) return 'multi_select';
  if (bracketPrompt && hasAnswerData(ex) && !isSingleChoiceExercise(questions)) return 'bracket_multi';
  if (circlePrompt && (standaloneWordList || inlineOptionList)) return 'checkbox';
  if (hasLetteredOptions(firstQ.options)) return 'letter_choice';
  if (isSingleChoiceExercise(questions)) return 'single_choice';
  if (belowSelectionPrompt && standaloneWordList) return 'token_fill';
  if (instruction.includes('助詞')) return 'particle_fill';
  if (instruction.includes('短い形')) return 'short_form';
  if (instruction.includes('「的」のつくことば')) return 'short_form';
  if (instruction.includes('ひらがなを1字ずつ')) return 'char_fill';
  if (instruction.includes('「ー」が一つ入ります')) return 'subsection';
  if (instruction.includes('答えは一つとはかぎりません')) return 'bracket_multi';
  if (instruction.includes('記号を書きなさい')) return 'symbol_fill';
  if (instruction.includes('対義語') || instruction.includes('反対')) return 'write_in';
  if (hasRenderableQuestionText(questions) && !isSingleChoiceExercise(questions)) return 'write_in';
  if (instruction.includes('適当な形にして') && (hasStandaloneWordList(ex) || hasSectionWordBanks(ex))) return 'editable_token';
  if (instruction.includes('正しいことば')) return 'single_choice';
  if (hasVisibleRawContent(ex)) return 'raw_text';
  return 'raw_text';
}

module.exports = {
  canonicalRenderType,
  inferRenderType,
  normalizeRenderType,
  RENDER_TYPE_CODES,
  CODE_TO_CANONICAL
};
