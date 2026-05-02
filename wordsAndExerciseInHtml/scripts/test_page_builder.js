/**
 * Exercise page builder and renderer dispatch.
 *
 * This is the main logic file to read when a test section renders incorrectly.
 * It intentionally depends on explicit render_type tags instead of guessing from
 * instructions at render time. Stable CSS and guide-page code live elsewhere so
 * this file stays focused on JSON -> exercise HTML behavior.
 */
const fs = require('fs');
const path = require('path');
const { normalizeRenderType: normalizeTaggedRenderType } = require('./render_type_rules');
const { CSS, EXTRA_PAGE_CSS, SHARED_PAGE_JS } = require('./test_page_assets');

const ROOT = path.resolve(__dirname, '..');
const DEFAULT_OUTPUT_ROOT = path.join(ROOT, 'exercises', 'n2');
const ANSWER_PAGES_DIR = path.join(ROOT, 'exercise_json', 'answerPages');
const DATA_ROOT = path.join(ROOT, 'exercise_json', 'n2');

// Manual answer patches are intentionally local to page building. They are
// legacy data repair, not render classification, so future render_type work
// should avoid adding to this unless the source answer JSON is incomplete.
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

// Small formatting and schema helpers shared by many renderers. Keeping these
// boring utilities close to the renderers avoids another import layer while the
// larger stable assets and guide page stay out of this file.
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

// Answer filling normalizes old and partially converted JSON before rendering.
// The renderer can then assume each question has the best available answer
// attached, while the original JSON schema remains readable.
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

function normalizeRenderType(type) {
  return normalizeTaggedRenderType(type);
}

/**
 * Detects which renderer should handle an exercise payload.
 *
 * @param {object} ex Exercise JSON block from the source file.
 * @returns {string} Short renderer code used inside buildHtml().
 */
function detectType(ex) {
  const explicitType = normalizeRenderType(ex.render_type || ex.type);
  if (explicitType) return explicitType;
  return 'RAW';
}

// Grouping keeps continuation sections together only when their explicit
// render_type matches. This prevents accidental merging across different UI
// controls and is why tag-first rendering is easier to audit than guessing.
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

// Individual renderers below are intentionally small-ish HTML fragment builders.
// Most future UI fixes should land here or in the dispatch block inside
// buildHtml(), not in json_to_test.js.
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

function renderWriteInQuestion(q, idx, makeId) {
  const text = q.text || q.word || q.phrase || '';
  const answer = q.answer || '';
  if (/\(\s*\)/.test(normalizeText(text))) {
    return renderBlankTextQuestion(q, idx, text, answer, makeId, 'type-a', 10);
  }
  const maxLength = Math.max(10, String(answer).length + 2);
  const prompt = text ? `${esc(text)} → ` : '';
  return `<div class="q-row"${controlAttrs(rowId('write', makeId), 'markable')}><span class="q-num">${esc(questionKey(q, idx))}.</span><span class="q-text">${prompt}${inputHtml('type-a', answer, maxLength, false, makeId('inp'), 'text-input')}</span></div>`;
}

function renderRawExercise(ex, makeId) {
  let html = '';
  const rawRows = [];
  (ex.words || []).forEach(word => rawRows.push(normalizeItem(word)));
  (ex.questions || []).forEach((q, idx) => {
    const label = q.id || q.number || q.index || idx + 1;
    const text = q.text || q.word || q.phrase || [q.left, q.right].filter(Boolean).join(' ');
    if (text) rawRows.push(`${label}. ${text}`);
  });
  if (rawRows.length) {
    html += '    <div class="word-grid">\n';
    rawRows.forEach(row => {
      html += `      <div class="word-item"${controlAttrs(makeId('raw'), 'markable')}>${esc(row)}</div>\n`;
    });
    html += '    </div>\n';
  }
  if (hasAnswerData(ex)) {
    html += '    <div class="hint">This section is tagged raw_text: source data is visible, but no interactive answer controls are generated.</div>\n';
  }
  return html;
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

// These path/metadata helpers are exported for the CLI and guide builder. They
// stay here for now because output paths and page metadata must match the HTML
// builder exactly.
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
 * This is the main dispatch table for render_type -> renderer behavior. Add
 * new render types here only after the JSON tagger knows how to assign them.
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
    } else if (group.type === 'E' || group.type === 'S' || group.type === 'W') {
      first.questions.forEach((q, idx) => {
        html += `    ${renderWriteInQuestion(q, idx, makeId)}\n`;
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
    } else if (group.type === 'RAW') {
      group.items.forEach(item => {
        html += renderRawExercise(item, makeId);
      });
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


module.exports = {
  ANSWER_PAGES_DIR,
  DATA_ROOT,
  DEFAULT_OUTPUT_ROOT,
  ROOT,
  buildHtml,
  pageLabel,
  pageTitle,
  preferredHtmlForJson,
  repoRelative,
  resolveOutputPath,
  toPosixPath,
  walkFiles
};
