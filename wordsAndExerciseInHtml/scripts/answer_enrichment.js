const fs = require('fs');
const path = require('path');

/**
 * Loads answer-page entries from `data/answerPages`.
 *
 * The folder is optional. An empty folder simply yields no page-derived data.
 * Answer pages are stored as structured JSON exports keyed by `reference_page`,
 * exercise type, section number, and optional subsection letter.
 *
 * @param {string} answerPagesDir Absolute path to the answer-page directory.
 * @returns {Map<string, object[]>} Parsed answer-page records by `page|type`.
 */
function loadAnswerPageEntries(answerPagesDir) {
  const records = new Map();
  if (!answerPagesDir || !fs.existsSync(answerPagesDir)) return records;
  const files = walkFiles(answerPagesDir);
  for (const file of files) {
    if (path.extname(file).toLowerCase() !== '.json') continue;
    mergePageIndex(records, parseAnswerPageFile(file));
  }
  return records;
}

/**
 * Applies answer-page data and built-in recoveries to a JSON payload.
 *
 * This is intentionally separate from renderer/type logic. It only enriches
 * answer fields so the existing generator can continue to render normally.
 *
 * @param {string} filename Basename of the JSON file being processed.
 * @param {object} data Parsed JSON object.
 * @param {{answerPagesDir?: string}} [options] Enrichment options.
 * @returns {object} Enriched clone of the input JSON.
 */
function enrichMissingAnswers(filename, data, options = {}) {
  const clone = JSON.parse(JSON.stringify(data || {}));
  const pageEntries = loadAnswerPageEntries(options.answerPagesDir || '');
  applyAnswerPageEntries(filename, clone, pageEntries);
  applyBuiltInRecoveries(filename, clone);
  return clone;
}

/**
 * Walks a directory recursively and returns file paths.
 *
 * @param {string} dir Root directory to scan.
 * @returns {string[]} Absolute file paths.
 */
function walkFiles(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walkFiles(full));
    else out.push(full);
  }
  return out;
}

/**
 * Parses one answer-page JSON file into normalized page/type records.
 *
 * @param {string} file Absolute file path.
 * @returns {Map<string, object[]>} Parsed records.
 */
function parseAnswerPageFile(file) {
  const raw = JSON.parse(fs.readFileSync(file, 'utf8'));
  const records = new Map();
  for (const unit of raw.units || []) {
    for (const exercise of unit.exercises || []) {
      const refPage = exercise.reference_page != null ? Number(exercise.reference_page) : null;
      if (!refPage) continue;
      const key = pageTypeKey(refPage, exercise.type);
      if (!records.has(key)) records.set(key, []);
      records.get(key).push(exercise);
    }
  }
  return records;
}

/**
 * Merges one page index into another.
 *
 * @param {Map<string, object[]>} target Destination index.
 * @param {Map<string, object[]>} source Source index.
 */
function mergePageIndex(target, source) {
  for (const [key, list] of source.entries()) {
    if (!target.has(key)) target.set(key, []);
    target.get(key).push(...list);
  }
}

/**
 * Builds a stable lookup key from reference page and exercise type.
 *
 * @param {number|string} pageNum Reference page number.
 * @param {string} exerciseType Exercise label from the answer pages.
 * @returns {string} Composite lookup key.
 */
function pageTypeKey(pageNum, exerciseType) {
  return `${Number(pageNum)}|${normalizeExerciseType(exerciseType)}`;
}

/**
 * Applies parsed answer-page records to a JSON payload.
 *
  * @param {string} filename Source JSON basename.
  * @param {object} data Mutable JSON payload clone.
 * @param {Map<string, object[]>} pageEntries Page/type index.
 */
function applyAnswerPageEntries(filename, data, pageEntries) {
  const exercises = Array.isArray(data.exercises) ? data.exercises : [];
  for (const ex of exercises) {
    const refPage = Number(ex && ex._source_page_num);
    if (!refPage) continue;
    const key = pageTypeKey(refPage, detectExerciseType(filename, data, ex));
    const records = pageEntries.get(key) || [];
    if (records.length === 0) continue;
    applyExerciseRecords(ex, records);
  }
}

/**
 * Applies answer-page records to one source exercise.
 *
 * @param {object} exercise Mutable source exercise.
 * @param {object[]} records Matching answer-page exercise records.
 */
function applyExerciseRecords(exercise, records) {
  const idInfo = parseExerciseId(exercise.id);
  for (const record of records) {
    const section = (record.sections || []).find(item => normalizeSectionNum(item.section_num) === idInfo.section);
    if (!section) continue;

    if (idInfo.letter) {
      const subsection = (section.subsections || []).find(item => String(item.letter || '').toUpperCase() === idInfo.letter);
      if (!subsection) continue;
      applyAnswerListToExercise(exercise, subsection.answers || [], { forceAnswerKey: true });
      return;
    }

    if (Array.isArray(section.subsections) && section.subsections.length > 0) {
      if (Array.isArray(exercise.sections) || Array.isArray(exercise.sub_sections)) {
        const answerKey = Object.assign({}, exercise.answer_key || {});
        section.subsections.forEach(sub => {
          answerKey[String(sub.letter || '').toUpperCase()] = normalizeAnswerList(sub.answers || []);
        });
        exercise.answer_key = answerKey;
        return;
      }
      continue;
    }

    applyAnswerListToExercise(exercise, section.answers || []);
    return;
  }
}

/**
 * Applies a normalized answer list to an exercise.
 *
 * @param {object} exercise Mutable source exercise.
 * @param {Array<string|object>} answers Raw answer list.
 * @param {{forceAnswerKey?: boolean}} [options] Application options.
 */
function applyAnswerListToExercise(exercise, answers, options = {}) {
  const normalized = normalizeAnswerList(answers);
  if (normalized.length === 0) return;

  if (Array.isArray(exercise.questions) && exercise.questions.length > 0 && !options.forceAnswerKey) {
    normalized.forEach((item, idx) => {
      if (item == null) return;
      if (typeof item === 'object' && item.qNum != null) {
        const qIndex = Number(item.qNum) - 1;
        if (exercise.questions[qIndex] && exercise.questions[qIndex].answer == null) {
          exercise.questions[qIndex].answer = item.answer;
        }
        return;
      }
      if (exercise.questions[idx] && exercise.questions[idx].answer == null) {
        exercise.questions[idx].answer = item;
      }
    });
    if (!exercise.answer_key && shouldStoreAnswerKey(exercise)) {
      exercise.answer_key = normalized.filter(item => typeof item === 'string');
    }
    return;
  }

  if (!exercise.answer_key) {
    exercise.answer_key = normalized.map(item => typeof item === 'object' ? item.answer : item);
  }
}

/**
 * Applies built-in recoveries for known missing-answer patterns.
 *
 * @param {string} filename Source JSON basename.
 * @param {object} data Mutable JSON payload clone.
 */
function applyBuiltInRecoveries(filename, data) {
  if (!Array.isArray(data.exercises)) return;

  if (filename === 'unit09_with_answers_1.json') {
    reassignUnit09AnswerKeys(data);
  }
  if (filename === 'unit09_with_answers_2.json') {
    reassignUnit09AnswerKeys(data);
  }
  if (filename === 'unit03_with_answers.json') {
    const ex = data.exercises.find(item => item.id === 'V');
    if (ex && !hasAnswerData(ex)) {
      ex.answer_key = {
        A: ['うらやましい', 'とうぜん', 'へんな', 'めんどうな', 'けっこう', 'まし', 'ふしぎな', 'むり', 'かゆい'],
        B: ['らくに', 'むりに', 'いがいに', 'じゆうに', 'ふあんに'],
        C: ['せっきょくせい', 'わがまま', 'ふちゅうい', 'むだ', 'くやしさ', 'おしゃれ']
      };
    }
  }
  if (filename === 'cross_unit_with_answers_1.json') {
    populateContinuationAnswer(data, 'II', 5, 'a');
    const ex = data.exercises.find(item => item.id === 'III');
    if (ex && !Array.isArray(ex.answer_key)) {
      ex.answer_key = ['c', 'b', 'd', 'a', 'c'];
    }
  }
}

/**
 * Detects the answer-book exercise type for a source exercise.
 *
 * @param {string} filename Source JSON basename.
 * @param {object} data Full JSON payload.
 * @param {object} exercise Current exercise.
 * @returns {string} Normalized exercise type label.
 */
function detectExerciseType(filename, data, exercise) {
  if (exercise && exercise._exercise_title) return exercise._exercise_title;
  const pageNum = Number(exercise && exercise._source_page_num);
  if ([30, 52, 88, 110, 130, 158, 180, 190, 204].includes(pageNum)) return '練習問題Ⅱ';
  return '練習問題Ⅰ';
}

/**
 * Parses source exercise ids such as `II`, `II-A`, or `V`.
 *
 * @param {string} rawId Source exercise id.
 * @returns {{section: string, letter: string}} Parsed id information.
 */
function parseExerciseId(rawId) {
  const text = String(rawId || '').trim().toUpperCase();
  const parts = text.split('-');
  return {
    section: normalizeSectionNum(parts[0]),
    letter: parts[1] ? parts[1].toUpperCase() : ''
  };
}

/**
 * Normalizes a practice label such as `練習問題 I` to `練習問題Ⅰ`.
 *
 * @param {string} text Raw exercise type.
 * @returns {string} Normalized type string.
 */
function normalizeExerciseType(text) {
  return String(text || '')
    .replace(/\s+/g, '')
    .replace(/III/g, 'Ⅲ')
    .replace(/II/g, 'Ⅱ')
    .replace(/IV/g, 'Ⅳ')
    .replace(/I/g, 'Ⅰ');
}

/**
 * Normalizes section numerals from source JSON or answer pages.
 *
 * @param {string} text Raw section number.
 * @returns {string} Normalized section numeral.
 */
function normalizeSectionNum(text) {
  return String(text || '')
    .trim()
    .toUpperCase()
    .replace(/III/g, 'Ⅲ')
    .replace(/II/g, 'Ⅱ')
    .replace(/IV/g, 'Ⅳ')
    .replace(/I/g, 'Ⅰ');
}

/**
 * Normalizes raw answer-page arrays into flat answer values.
 *
 * @param {Array<string|object>} answers Raw answer list.
 * @returns {Array<string|{qNum:number,answer:string}>} Normalized answers.
 */
function normalizeAnswerList(answers) {
  return (answers || []).map(item => {
    if (item && typeof item === 'object' && item.q_num != null) {
      return { qNum: Number(item.q_num), answer: String(item.answer || '').trim() };
    }
    return String(item || '').trim();
  }).filter(item => {
    if (typeof item === 'object') return item.answer;
    return item;
  });
}

/**
 * Determines whether an exercise should also keep an `answer_key` list.
 *
 * @param {object} exercise Source exercise.
 * @returns {boolean} True when the renderer uses `answer_key`.
 */
function shouldStoreAnswerKey(exercise) {
  return Array.isArray(exercise.options) || Array.isArray(exercise.word_bank) || String(exercise.instruction || '').includes('○をつけ');
}

/**
 * Reassigns misplaced answer-key lists on the unit 9 pages.
 *
 * The source JSON stores the II-A answers on exercise I and the II-B answers
 * on exercise II-A. This helper moves both lists to the exercises they
 * actually belong to.
 *
 * @param {object} data Mutable JSON payload clone.
 */
function reassignUnit09AnswerKeys(data) {
  const exerciseI = data.exercises.find(ex => ex.id === 'I');
  const sectionA = data.exercises.find(ex => ex.id === 'II-A');
  const sectionB = data.exercises.find(ex => ex.id === 'II-B');
  if (!exerciseI || !sectionA || !sectionB) return;

  const sectionAAnswers = Array.isArray(exerciseI.answer_key) ? splitDelimitedList(exerciseI.answer_key) : [];
  const sectionBAnswers = Array.isArray(sectionA.answer_key) ? splitDelimitedList(sectionA.answer_key) : [];

  if (sectionAAnswers.length > 0) sectionA.answer_key = sectionAAnswers;
  if (sectionBAnswers.length > 0) sectionB.answer_key = sectionBAnswers;
  delete exerciseI.answer_key;
}

/**
 * Moves an answer-key list from one exercise to another when the target is
 * missing answers.
 *
 * @param {object} data Mutable JSON payload clone.
 * @param {string} fromId Source exercise id.
 * @param {string} toId Target exercise id.
 */
function relayAnswerKey(data, fromId, toId) {
  const source = data.exercises.find(ex => ex.id === fromId);
  const target = data.exercises.find(ex => ex.id === toId);
  if (!source || !target) return;
  if (!Array.isArray(source.answer_key) || source.answer_key.length === 0) return;
  if (hasAnswerData(target)) return;
  target.answer_key = source.answer_key.slice();
  delete source.answer_key;
}

/**
 * Fills a specific question in a continued exercise block.
 *
 * @param {object} data Mutable JSON payload clone.
 * @param {string} exerciseId Target exercise id.
 * @param {number} questionNumber 1-based question number within the merged id.
 * @param {string} answer Missing answer to set.
 */
function populateContinuationAnswer(data, exerciseId, questionNumber, answer) {
  const siblings = data.exercises.filter(ex => ex.id === exerciseId);
  if (siblings.length === 0) return;
  let seen = 0;
  for (const ex of siblings) {
    const questions = Array.isArray(ex.questions) ? ex.questions : [];
    for (const question of questions) {
      seen += 1;
      if (seen !== questionNumber) continue;
      if (question.answer == null) question.answer = answer;
      return;
    }
  }
}

/**
 * Checks whether an exercise already carries answer data.
 *
 * @param {object} ex Exercise record.
 * @returns {boolean} True when answer content is already present.
 */
function hasAnswerData(ex) {
  if (!ex || typeof ex !== 'object') return false;
  if (Array.isArray(ex.answer_key) && ex.answer_key.length > 0) return true;
  if (ex.answer_key && typeof ex.answer_key === 'object' && Object.keys(ex.answer_key).length > 0) return true;
  return (ex.questions || []).some(q => q && q.answer != null);
}

/**
 * Flattens a list of delimited answer entries into discrete answer strings.
 *
 * @param {Array<string>} list Raw answer-key list.
 * @returns {string[]} Split answer values.
 */
function splitDelimitedList(list) {
  const out = [];
  for (const item of list || []) {
    String(item || '')
      .split(/[、,]/)
      .map(part => part.trim())
      .filter(Boolean)
      .forEach(part => out.push(part));
  }
  return out;
}

module.exports = {
  enrichMissingAnswers,
  loadAnswerPageEntries
};
