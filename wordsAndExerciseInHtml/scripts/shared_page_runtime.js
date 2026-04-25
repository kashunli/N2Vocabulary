var STORAGE_PAGE_PREFIX = 'n3-tests/page/v1/';
var STORAGE_INDEX_KEY = 'n3-tests/index/v1';
var PAGE_META = window.TEST_PAGE_META || {};
var activeBlank = null;
var isRestoringState = false;
var __latestScore = null;
var __checkedAt = null;
var __isChecked = false;

function loadJsonValue(key, fallback) {
  try {
    var raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (err) {
    return fallback;
  }
}

function saveJsonValue(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch (err) {}
}

function pageStorageKey() {
  return STORAGE_PAGE_PREFIX + PAGE_META.pageId;
}

function acceptableAnswers(ans) {
  return String(ans || '').split('／').map(function(x) { return x.trim(); }).filter(Boolean);
}

function isCorrectValue(val, ans) {
  var clean = String(val || '').trim();
  return acceptableAnswers(ans).indexOf(clean) !== -1;
}

function setBlankWidth(inp) {
  if (!inp || (!inp.classList.contains('blank-inp') && !inp.classList.contains('blank-inp-j'))) return;
  var val = String(inp.value || '').trim();
  var minWidth = inp.classList.contains('blank-inp-j') ? 100 : 80;
  inp.style.width = val ? Math.max(minWidth, val.length * 16 + (inp.classList.contains('blank-inp-j') ? 20 : 10)) + 'px' : minWidth + 'px';
}

function setActiveBlank(blank) {
  document.querySelectorAll('.blank-inp, .blank-inp-j').forEach(function(b) { b.classList.remove('active'); });
  if (blank) {
    blank.classList.add('active');
    activeBlank = blank;
  } else {
    activeBlank = null;
  }
}

function bankForBlank(blank) {
  if (!blank || !blank.dataset.bankId) return null;
  return document.getElementById(blank.dataset.bankId);
}

function releaseEditableToken(blank) {
  if (!blank) return;
  var tokenBase = blank.dataset.tokenBase || '';
  var bank = bankForBlank(blank);
  if (tokenBase && bank) {
    bank.querySelectorAll('.token').forEach(function(token) {
      if (token.dataset.val === tokenBase) token.classList.remove('used');
    });
  }
  blank.dataset.tokenBase = '';
}

function clearEditableBlank(blank) {
  if (!blank) return;
  releaseEditableToken(blank);
  blank.value = '';
  setBlankWidth(blank);
}

function resetCheckedState() {
  document.querySelectorAll('.correct,.wrong,.correct-ans,.wrong-sel,.correct-cb,.wrong-cb').forEach(function(el) {
    el.classList.remove('correct', 'wrong', 'correct-ans', 'wrong-sel', 'correct-cb', 'wrong-cb');
  });
  document.querySelectorAll('.answer-reveal').forEach(function(el) { el.remove(); });
  document.querySelectorAll('input.type-a, .blank-inp-j').forEach(function(inp) { inp.disabled = false; });
  document.querySelectorAll('.blank-inp').forEach(function(inp) { inp.classList.remove('locked'); });
  document.querySelectorAll('.token, .pill').forEach(function(el) { el.classList.remove('locked'); });
  document.querySelectorAll('.word-item').forEach(function(item) { item.classList.remove('locked'); });
  document.querySelectorAll('.word-grid input[type="checkbox"]').forEach(function(cb) { cb.disabled = false; });
  var checkBtn = document.querySelector('.btn-check');
  if (checkBtn) {
    checkBtn.disabled = false;
    checkBtn.style.opacity = '';
  }
}

function hideScoreBar() {
  var bar = document.getElementById('score-bar');
  if (bar) bar.style.display = 'none';
}

function leaveCheckedMode() {
  if (!__isChecked) return false;
  resetCheckedState();
  hideScoreBar();
  __isChecked = false;
  __checkedAt = null;
  __latestScore = null;
  return true;
}

function revealAnswer(afterEl, ans) {
  var span = document.createElement('span');
  span.className = 'answer-reveal';
  span.textContent = '→ ' + ans;
  afterEl.parentNode.insertBefore(span, afterEl.nextSibling);
}

/**
 * Returns element text without UI-only controls such as star buttons.
 *
 * @param {Element|null} el - Element to read.
 * @return {string} Visible text for export and answer matching.
 */
function plainText(el) {
  if (!el) return '';
  var clone = el.cloneNode(true);
  clone.querySelectorAll('.mark-toggle, .answer-reveal').forEach(function(node) { node.remove(); });
  return clone.textContent.trim();
}

function collectControls() {
  var controls = {};
  document.querySelectorAll('[data-control-id]').forEach(function(el) {
    var id = el.dataset.controlId;
    var kind = el.dataset.controlKind || '';
  if (kind === 'text-input' || kind === 'token-input' || kind === 'editable-token-input') {
      controls[id] = { kind: kind, value: el.value || '' };
      if (kind === 'editable-token-input' && el.dataset.tokenBase) controls[id].tokenBase = el.dataset.tokenBase;
      if (kind === 'text-input' && el.dataset.tokenValue) controls[id].tokenValue = el.dataset.tokenValue;
    } else if (kind === 'checkbox-item') {
      var cb = el.querySelector('input[type="checkbox"]');
      controls[id] = { kind: kind, checked: !!(cb && cb.checked), optionMarked: el.classList.contains('option-marked') };
    } else if (kind === 'pill') {
      controls[id] = { kind: kind, selected: el.classList.contains('selected'), optionMarked: el.classList.contains('option-marked') };
    } else if (kind === 'token') {
      controls[id] = { kind: kind, used: el.classList.contains('used'), optionMarked: el.classList.contains('option-marked') };
    } else if (kind === 'markable') {
      controls[id] = { kind: kind, marked: el.classList.contains('marked') };
    }
  });
  return controls;
}

function controlHasProgress(state) {
  if (!state) return false;
  if (typeof state.value === 'string' && state.value.trim()) return true;
  if (state.checked) return true;
  if (state.selected) return true;
  if (state.used) return true;
  if (state.marked) return true;
  if (state.optionMarked) return true;
  return false;
}

function currentExportText() {
  var box = document.getElementById('export-box');
  var ta = document.getElementById('export-text');
  if (!box || !ta || box.style.display === 'none') return '';
  return ta.value || '';
}

function currentStatus(controls, checked) {
  if (checked) return 'Checked';
  return Object.keys(controls || {}).some(function(id) { return controlHasProgress(controls[id]); }) ? 'In progress' : 'Not started';
}

function updateIndexSummary(snapshot) {
  var index = loadJsonValue(STORAGE_INDEX_KEY, {});
  index[PAGE_META.pageId] = {
    version: snapshot.version,
    pageId: snapshot.pageId,
    pageTitle: snapshot.pageTitle,
    unitLabel: snapshot.unitLabel,
    sourceJson: snapshot.sourceJson,
    status: snapshot.status,
    updatedAt: snapshot.updatedAt,
    checkedAt: snapshot.checkedAt,
    score: snapshot.score
  };
  saveJsonValue(STORAGE_INDEX_KEY, index);
}

function savePageState() {
  if (isRestoringState) return;
  var controls = collectControls();
  var checked = __isChecked;
  var snapshot = {
    version: 1,
    pageId: PAGE_META.pageId,
    pageTitle: PAGE_META.pageTitle,
    unitLabel: PAGE_META.unitLabel,
    sourceJson: PAGE_META.sourceJson,
    status: currentStatus(controls, checked),
    updatedAt: new Date().toISOString(),
    checkedAt: checked ? (__checkedAt || new Date().toISOString()) : null,
    score: __latestScore,
    exportText: currentExportText(),
    controls: controls
  };
  saveJsonValue(pageStorageKey(), snapshot);
  updateIndexSummary(snapshot);
}

function applyControlState(el, state) {
  if (!el || !state) return;
  var kind = el.dataset.controlKind || state.kind || '';
  if (kind === 'text-input' || kind === 'token-input' || kind === 'editable-token-input') {
    el.value = state.value || '';
    if (kind === 'editable-token-input') el.dataset.tokenBase = state.tokenBase || '';
    if (kind === 'text-input') el.dataset.tokenValue = state.tokenValue || '';
    setBlankWidth(el);
  } else if (kind === 'checkbox-item') {
    var cb = el.querySelector('input[type="checkbox"]');
    if (cb) cb.checked = !!state.checked;
    el.classList.toggle('option-marked', !!state.optionMarked);
  } else if (kind === 'pill') {
    el.classList.toggle('selected', !!state.selected);
    el.classList.toggle('option-marked', !!state.optionMarked);
  } else if (kind === 'token') {
    el.classList.toggle('used', !!state.used);
    el.classList.toggle('option-marked', !!state.optionMarked);
  } else if (kind === 'markable') {
    el.classList.toggle('marked', !!state.marked);
  }
  syncEmbeddedMarkButton(el);
}

/**
 * Updates the visible state of an embedded mark button from its host element.
 *
 * @param {Element|null} host - Row or option element that owns the mark button.
 */
function ownMarkButton(host) {
  if (!host || !host.children) return null;
  for (var i = 0; i < host.children.length; i += 1) {
    var child = host.children[i];
    if (child.classList && child.classList.contains('mark-toggle')) return child;
  }
  return null;
}

/**
 * Updates the visible state of an embedded mark button from its host element.
 *
 * @param {Element|null} host - Row or option element that owns the mark button.
 */
function syncEmbeddedMarkButton(host) {
  if (!host) return;
  var btn = ownMarkButton(host);
  if (!btn) return;
  var isOption = host.classList.contains('pill') || host.classList.contains('token') || host.classList.contains('word-item');
  var marked = isOption ? host.classList.contains('option-marked') : host.classList.contains('marked');
  btn.classList.toggle('active', !!marked);
  btn.setAttribute('aria-pressed', marked ? 'true' : 'false');
  btn.title = marked ? 'Unmark' : 'Mark';
  btn.textContent = marked ? '★' : '☆';
}

/**
 * Toggles mark state without triggering the element's normal selection behavior.
 *
 * @param {Element} host - Row or option element to toggle.
 */
function toggleHostMark(host) {
  if (!host) return;
  if (host.classList.contains('pill') || host.classList.contains('token') || host.classList.contains('word-item')) {
    host.classList.toggle('option-marked');
  } else {
    host.classList.toggle('marked');
  }
  syncEmbeddedMarkButton(host);
  savePageState();
}

/**
 * Appends explicit star buttons to markable rows and options.
 */
function installMarkButtons() {
  document.querySelectorAll('[data-control-kind="markable"], .pill[data-control-id], .token[data-control-id], .word-item[data-control-id]').forEach(function(host) {
    if (ownMarkButton(host)) {
      syncEmbeddedMarkButton(host);
      return;
    }
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'mark-toggle';
    btn.setAttribute('aria-label', 'Toggle mark');
    btn.addEventListener('mousedown', function(e) {
      e.preventDefault();
      e.stopPropagation();
    });
    btn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      leaveCheckedMode();
      toggleHostMark(host);
    });
    host.appendChild(btn);
    host.classList.add('has-mark-toggle');
    syncEmbeddedMarkButton(host);
  });
}

function showExportText(text, noScroll) {
  var box = document.getElementById('export-box');
  var ta = document.getElementById('export-text');
  if (!box || !ta) return;
  ta.value = text || '';
  box.style.display = text ? 'block' : 'none';
  if (text && !noScroll) box.scrollIntoView({ behavior: 'smooth' });
}

function restorePageState() {
  var snapshot = loadJsonValue(pageStorageKey(), null);
  if (!snapshot || !snapshot.controls) return;
  isRestoringState = true;
  try {
    Object.keys(snapshot.controls).forEach(function(id) {
      var safeId = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(id) : id.replace(/"/g, '\\"');
      applyControlState(document.querySelector('[data-control-id="' + safeId + '"]'), snapshot.controls[id]);
    });
    __latestScore = snapshot.score || null;
    __checkedAt = snapshot.checkedAt || null;
    __isChecked = snapshot.status === 'Checked';
    if (snapshot.status === 'Checked') {
      checkAnswers({ skipSave: true, noScroll: true, checkedAt: snapshot.checkedAt, score: snapshot.score });
    }
    if (snapshot.exportText) showExportText(snapshot.exportText, true);
  } finally {
    isRestoringState = false;
  }
}

function initPersistence() {
  document.querySelectorAll('input.type-a, .blank-inp, .blank-inp-j').forEach(function(inp) {
    inp.addEventListener('input', function() {
      leaveCheckedMode();
      if (inp.classList.contains('blank-inp-j') && !String(inp.value || '').trim()) {
        releaseEditableToken(inp);
      }
      setBlankWidth(inp);
      savePageState();
    });
  });
  document.querySelectorAll('.word-grid input[type="checkbox"]').forEach(function(cb) {
    cb.addEventListener('change', function() {
      leaveCheckedMode();
      savePageState();
    });
  });
  window.addEventListener('beforeunload', savePageState);
}

document.querySelectorAll('.pill-group:not(.multi)').forEach(function(group) {
  group.querySelectorAll('.pill').forEach(function(pill) {
    pill.addEventListener('click', function(e) {
      if (e.target && e.target.closest && e.target.closest('.mark-toggle')) return;
      leaveCheckedMode();
      var already = pill.classList.contains('selected');
      group.querySelectorAll('.pill').forEach(function(p) { p.classList.remove('selected'); });
      if (!already) pill.classList.add('selected');
      savePageState();
    });
  });
});

document.querySelectorAll('.pill-group.multi .pill').forEach(function(pill) {
  pill.addEventListener('click', function(e) {
    if (e.target && e.target.closest && e.target.closest('.mark-toggle')) return;
    leaveCheckedMode();
    pill.classList.toggle('selected');
    savePageState();
  });
});

installMarkButtons();

function initTokenSection(blankClass, bankId) {
  var bank = document.getElementById(bankId);
  var reusable = bank && bank.dataset.reusable === 'true';
  document.querySelectorAll('.' + blankClass).forEach(function(blank) {
    blank.addEventListener('click', function() {
      leaveCheckedMode();
      if (blank.classList.contains('locked')) return;
      if (blank.value) {
        var oldVal = blank.value;
        blank.value = '';
        setBlankWidth(blank);
        blank.classList.remove('active');
        if (!reusable && bank) {
          bank.querySelectorAll('.token').forEach(function(t) { if (t.dataset.val === oldVal) t.classList.remove('used'); });
        }
        setActiveBlank(blank);
        savePageState();
        return;
      }
      setActiveBlank(blank);
    });
  });
  if (!bank) return;
  bank.querySelectorAll('.token').forEach(function(token) {
    token.addEventListener('click', function() {
      leaveCheckedMode();
      if (token.classList.contains('locked')) return;
      if (!reusable && token.classList.contains('used')) return;
      if (!activeBlank || !activeBlank.classList.contains('active')) return;
      var oldVal = activeBlank.value;
      if (oldVal && !reusable) {
        bank.querySelectorAll('.token').forEach(function(t) { if (t.dataset.val === oldVal) t.classList.remove('used'); });
      }
      activeBlank.value = token.dataset.val;
      setBlankWidth(activeBlank);
      if (!reusable) token.classList.add('used');
      activeBlank.classList.remove('active');
      activeBlank = null;
      savePageState();
    });
  });
}

function initTokenAssistSection(inputSelector, bankId) {
  var bank = document.getElementById(bankId);
  if (!bank) return;
  var inputs = document.querySelectorAll(inputSelector);
  function releaseTokenValue(tokenValue) {
    if (!tokenValue) return;
    bank.querySelectorAll('.token').forEach(function(token) {
      if (token.dataset.val === tokenValue) token.classList.remove('used');
    });
  }
  inputs.forEach(function(inp) {
    inp.dataset.bankId = bankId;
    inp.addEventListener('click', function() {
      leaveCheckedMode();
      if (inp.disabled) return;
      setActiveBlank(inp);
      inp.focus();
    });
    inp.addEventListener('input', function() {
      var tracked = inp.dataset.tokenValue || '';
      if (tracked && String(inp.value || '').trim() !== tracked) {
        releaseTokenValue(tracked);
        inp.dataset.tokenValue = '';
      }
    });
  });
  bank.querySelectorAll('.token').forEach(function(token) {
    token.addEventListener('click', function(e) {
      if (e.target && e.target.closest && e.target.closest('.mark-toggle')) return;
      leaveCheckedMode();
      if (token.classList.contains('locked')) return;
      if (token.classList.contains('used')) return;
      if (!activeBlank || activeBlank.disabled || !activeBlank.matches(inputSelector)) return;
      var oldTokenValue = activeBlank.dataset.tokenValue || '';
      if (oldTokenValue) releaseTokenValue(oldTokenValue);
      activeBlank.value = token.dataset.val;
      activeBlank.dataset.tokenValue = token.dataset.val;
      setBlankWidth(activeBlank);
      token.classList.add('used');
      activeBlank.focus();
      savePageState();
    });
  });
}

function initTokenSectionJ(blankClass, bankId) {
  var bank = document.getElementById(bankId);
  document.querySelectorAll('.' + blankClass).forEach(function(blank) {
    blank.dataset.bankId = bankId;
    blank.addEventListener('click', function() {
      leaveCheckedMode();
      if (blank.disabled) return;
      setActiveBlank(blank);
      blank.focus();
    });
  });
  if (!bank) return;
  bank.querySelectorAll('.token').forEach(function(token) {
    token.addEventListener('mousedown', function(e) {
      if (e.button !== 0) return;
      leaveCheckedMode();
      e.preventDefault();
      if (token.classList.contains('locked')) return;
      if (token.classList.contains('used')) {
        var assignedBlank = null;
        document.querySelectorAll('.' + blankClass).forEach(function(blank) {
          if (!assignedBlank && blank.dataset.tokenBase === token.dataset.val) assignedBlank = blank;
        });
        if (!assignedBlank || assignedBlank.disabled) return;
        clearEditableBlank(assignedBlank);
        setActiveBlank(assignedBlank);
        assignedBlank.focus();
        savePageState();
        return;
      }
      if (!activeBlank) return;
      releaseEditableToken(activeBlank);
      activeBlank.value = token.dataset.val;
      activeBlank.dataset.tokenBase = token.dataset.val;
      setBlankWidth(activeBlank);
      token.classList.add('used');
      activeBlank.focus();
      savePageState();
    });
  });
}

document.addEventListener('click', function(e) {
  if (
    !e.target.classList.contains('blank-inp') &&
    !e.target.classList.contains('blank-inp-j') &&
    !e.target.classList.contains('type-a') &&
    !e.target.classList.contains('token')
  ) {
    setActiveBlank(null);
  }
});

function checkAnswers(options) {
  options = options || {};
  var correct = 0;
  var total = 0;
  resetCheckedState();
  document.querySelectorAll('input.type-a[data-ans]').forEach(function(inp) {
    total += 1;
    if (isCorrectValue(inp.value, inp.dataset.ans)) {
      inp.classList.add('correct');
      correct += 1;
    } else {
      inp.classList.add('wrong');
      revealAnswer(inp, inp.dataset.ans);
    }
  });
  document.querySelectorAll('.word-item[data-ans]').forEach(function(label) {
    total += 1;
    var cb = label.querySelector('input[type="checkbox"]');
    var ok = (label.dataset.ans === 'true') === (cb && cb.checked);
    label.classList.add(ok ? 'correct-cb' : 'wrong-cb');
    if (ok) {
      correct += 1;
    } else {
      var hint = document.createElement('span');
      hint.className = 'answer-reveal';
      hint.textContent = label.dataset.ans === 'true' ? '→ ◯' : '→ ✕';
      label.appendChild(hint);
    }
  });
  document.querySelectorAll('.s3-row[data-ans]').forEach(function(row) {
    total += 1;
    var ans = row.dataset.ans;
    var selected = row.querySelector('.pill.selected');
    var selectedKey = selected ? (selected.dataset.letter || plainText(selected)) : null;
    if (selectedKey === ans) {
      if (selected) selected.classList.add('correct-ans');
      correct += 1;
    } else {
      if (selected) selected.classList.add('wrong-sel');
      row.querySelectorAll('.pill').forEach(function(p) {
        if ((p.dataset.letter || plainText(p)) === ans) p.classList.add('correct-ans');
      });
    }
  });
  document.querySelectorAll('.inline-choice[data-ans]').forEach(function(group) {
    total += 1;
    var ans = group.dataset.ans;
    var correctSet = acceptableAnswers(ans);
    if (group.classList.contains('multi')) {
      var selectedPills = Array.from(group.querySelectorAll('.pill.selected'));
      var selectedKeys = selectedPills.map(function(p) { return plainText(p); });
      var isCorrect = correctSet.length === selectedKeys.length &&
        correctSet.every(function(a) { return selectedKeys.indexOf(a) !== -1; });
      if (isCorrect) {
        selectedPills.forEach(function(p) { p.classList.add('correct-ans'); });
        correct += 1;
      } else {
        group.querySelectorAll('.pill').forEach(function(p) {
          var key = plainText(p);
          var inCorrect = correctSet.indexOf(key) !== -1;
          var isSel = p.classList.contains('selected');
          if (isSel && inCorrect) p.classList.add('correct-ans');
          else if (isSel && !inCorrect) p.classList.add('wrong-sel');
          else if (!isSel && inCorrect) p.classList.add('correct-ans');
        });
      }
    } else {
      var selected = group.querySelector('.pill.selected');
      var selectedKey = selected ? plainText(selected) : null;
      if (correctSet.indexOf(selectedKey) !== -1) {
        if (selected) selected.classList.add('correct-ans');
        correct += 1;
      } else {
        if (selected) selected.classList.add('wrong-sel');
        group.querySelectorAll('.pill').forEach(function(p) {
          if (correctSet.indexOf(plainText(p)) !== -1) p.classList.add('correct-ans');
        });
      }
    }
  });
  document.querySelectorAll('.mi-row[data-ans]').forEach(function(miRow) {
    var ans = JSON.parse(miRow.dataset.ans);
    total += ans.length;
    miRow.querySelectorAll('.pill').forEach(function(p) {
      var txt = plainText(p);
      var inAns = ans.indexOf(txt) !== -1;
      var isSelected = p.classList.contains('selected');
      if (inAns && isSelected) {
        p.classList.add('correct-ans');
        correct += 1;
      } else if (inAns && !isSelected) {
        p.classList.add('correct-ans');
      } else if (!inAns && isSelected) {
        p.classList.add('wrong-sel');
      }
    });
  });
  document.querySelectorAll('.blank-inp[data-ans]').forEach(function(inp) {
    total += 1;
    if (isCorrectValue(inp.value, inp.dataset.ans)) {
      inp.classList.add('correct');
      correct += 1;
    } else {
      inp.classList.add('wrong');
      revealAnswer(inp, inp.dataset.ans);
    }
  });
  document.querySelectorAll('.blank-inp-j[data-ans]').forEach(function(inp) {
    total += 1;
    if (isCorrectValue(inp.value, inp.dataset.ans)) {
      inp.classList.add('correct');
      correct += 1;
    } else {
      inp.classList.add('wrong');
      revealAnswer(inp, inp.dataset.ans);
    }
  });
  var wrong = total - correct;
  var bar = document.getElementById('score-bar');
  if (bar) {
    bar.textContent = '✓ ' + correct + ' correct  ✗ ' + wrong + ' wrong  (out of ' + total + ')';
    bar.className = 'score-bar ' + (wrong === 0 ? 'good' : 'bad');
    bar.style.display = 'block';
    if (!options.noScroll) bar.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  __latestScore = options.score || { correct: correct, total: total };
  __checkedAt = options.checkedAt || __checkedAt || new Date().toISOString();
  __isChecked = true;
  if (!options.skipSave) savePageState();
}

function clearAll(options) {
  options = options || {};
  resetCheckedState();
  document.querySelectorAll('input.type-a, .blank-inp, .blank-inp-j').forEach(function(inp) {
    inp.value = '';
    if (inp.classList.contains('blank-inp-j')) inp.dataset.tokenBase = '';
    if (inp.classList.contains('type-a')) inp.dataset.tokenValue = '';
    inp.classList.remove('active', 'locked');
    setBlankWidth(inp);
  });
  document.querySelectorAll('.word-grid input[type="checkbox"]').forEach(function(cb) { cb.checked = false; });
  document.querySelectorAll('.pill').forEach(function(p) { p.classList.remove('selected'); });
  document.querySelectorAll('.token').forEach(function(t) { t.classList.remove('used'); });
  document.querySelectorAll('.marked').forEach(function(el) { el.classList.remove('marked'); });
  document.querySelectorAll('.option-marked').forEach(function(el) { el.classList.remove('option-marked'); });
  document.querySelectorAll('[data-control-kind="markable"], .pill[data-control-id], .token[data-control-id], .word-item[data-control-id]').forEach(syncEmbeddedMarkButton);
  showExportText('', true);
  var scoreBar = document.getElementById('score-bar');
  if (scoreBar) scoreBar.style.display = 'none';
  setActiveBlank(null);
  __isChecked = false;
  __latestScore = null;
  __checkedAt = null;
  if (!options.skipSave) savePageState();
}

function fmtInp(inp) {
  var val = inp.value.trim() || '___';
  var ans = inp.dataset.ans ? inp.dataset.ans.trim() : null;
  return '（' + val + '）';
}

function yesNo(flag) {
  return flag ? 'Yes' : 'No';
}

function joinOrNone(items) {
  return items && items.length ? items.join(' | ') : '-';
}

function pushQuestionBlock(lines, fields) {
  lines.push(fields.header || 'Question');
  if (fields.prompt != null) lines.push('  Prompt: ' + fields.prompt);
  if (fields.marked != null) lines.push('  Marked: ' + yesNo(fields.marked));
  if (fields.myAnswer != null) lines.push('  My answer: ' + fields.myAnswer);
  if (fields.correctAnswer != null) lines.push('  Correct answer: ' + fields.correctAnswer);
  if (fields.markedOptions != null) lines.push('  Marked options: ' + fields.markedOptions);
  if (fields.availableOptions != null) lines.push('  Available options: ' + fields.availableOptions);
  if (fields.bankState != null) lines.push('  Word bank state: ' + fields.bankState);
  lines.push('');
}

function buildExportText() {
  var lines = [];
  var pageTitle = document.querySelector('h1') ? document.querySelector('h1').textContent.trim().replace(/\s+/g, ' ') : 'Test';
  lines.push('=== ' + pageTitle + ' — My Answers ===\n');
  document.querySelectorAll('.section').forEach(function(sec) {
    var secNum = sec.querySelector('.section-title') ? sec.querySelector('.section-title').textContent.trim() : '?';
    var secLabel = sec.querySelector('.section-q') ? sec.querySelector('.section-q').textContent.trim() : '';
    lines.push('【' + secNum + ' ' + secLabel + '】');
    var verbTable = sec.querySelector('.verb-table');
    if (verbTable) {
      verbTable.querySelectorAll('tbody tr').forEach(function(tr, i) {
        var cells = tr.querySelectorAll('td');
        var row = [];
        cells.forEach(function(td) {
          var inp = td.querySelector('input');
          row.push(inp ? fmtInp(inp) : td.textContent.trim());
        });
        pushQuestionBlock(lines, {
          header: (i + 1) + '.',
          prompt: row.join(' ／ ')
        });
      });
    } else if (sec.querySelectorAll('input.type-a').length > 0) {
      sec.querySelectorAll('.q-row').forEach(function(row) {
        var num = row.querySelector('.q-num') ? row.querySelector('.q-num').textContent.trim() : '';
        var textEl = row.querySelector('.q-text') || row;
        var sentence = '';
        var answers = [];
        var mine = [];
        textEl.childNodes.forEach(function(node) {
          if (node.nodeType === 3) sentence += node.textContent;
          else if (node.nodeName === 'INPUT') {
            sentence += fmtInp(node);
            mine.push(node.value.trim() || '___');
            answers.push(node.dataset.ans ? node.dataset.ans.trim() : '-');
          }
          else if (node.classList && node.classList.contains('answer-reveal')) {}
          else if (node.classList && node.classList.contains('mark-toggle')) {}
          else sentence += node.textContent;
        });
        pushQuestionBlock(lines, {
          header: num,
          prompt: sentence.trim(),
          marked: row.classList.contains('marked'),
          myAnswer: joinOrNone(mine),
          correctAnswer: joinOrNone(answers)
        });
      });
    }
    var cbGrid = sec.querySelector('.word-grid');
    if (cbGrid) {
      var selectedWords = [];
      var markedWords = [];
      var correctWords = [];
      cbGrid.querySelectorAll('.word-item').forEach(function(item) {
        var cb = item.querySelector('input[type="checkbox"]');
        var word = plainText(item).replace(/[→◯✕]/g, '').trim();
        var ans = item.dataset.ans;
        if (cb && cb.checked) selectedWords.push(word);
        if (item.classList.contains('option-marked')) markedWords.push(word);
        if (ans === 'true') correctWords.push(word);
      });
      pushQuestionBlock(lines, {
        header: 'Checkbox set',
        marked: false,
        myAnswer: joinOrNone(selectedWords),
        correctAnswer: joinOrNone(correctWords),
        markedOptions: joinOrNone(markedWords)
      });
    }
    if (sec.querySelectorAll('.s3-row .pill-group:not(.multi)').length > 0) {
      var currentSub = '';
      sec.querySelectorAll('.section-sub, .s3-row').forEach(function(el) {
        if (el.classList.contains('section-sub')) { currentSub = el.textContent.trim(); return; }
        if (!el.querySelector('.pill-group:not(.multi)')) return;
        var label = el.querySelector('.s3-label') ? el.querySelector('.s3-label').textContent.trim() : '';
        var phrase = el.querySelector('.s3-phrase') ? plainText(el.querySelector('.s3-phrase')) : '';
        var ans = el.dataset.ans || null;
        var availableOptions = [];
        var markedOptions = [];
        var selectedKey = null;
        var selectedText = null;
        var correctText = ans || '-';
        el.querySelectorAll('.pill').forEach(function(p) {
          var clean = plainText(p);
          var key = p.dataset.letter || clean;
          var word = (p.dataset.letter ? p.dataset.letter + ' ' : '') + clean;
          var sel = p.classList.contains('selected');
          var opt = p.classList.contains('option-marked');
          if (sel) selectedKey = key;
          if (sel) selectedText = word;
          if (opt) markedOptions.push(word);
          if (ans && key === ans) correctText = word;
          availableOptions.push(word);
        });
        var prefix = currentSub ? '[' + currentSub + '] ' : '';
        pushQuestionBlock(lines, {
          header: prefix + label,
          prompt: phrase,
          marked: el.classList.contains('marked'),
          myAnswer: selectedText || '-',
          correctAnswer: correctText,
          markedOptions: joinOrNone(markedOptions),
          availableOptions: joinOrNone(availableOptions)
        });
      });
    }
    if (sec.querySelectorAll('.inline-choice').length > 0) {
      sec.querySelectorAll('.q-row').forEach(function(row) {
        if (!row.querySelector('.inline-choice')) return;
        var num = row.querySelector('.q-num') ? row.querySelector('.q-num').textContent.trim() : '';
        var prompt = row.querySelector('.q-text') ? plainText(row.querySelector('.q-text')) : '';
        var groups = row.querySelectorAll('.inline-choice');
        groups.forEach(function(group, index) {
          var markedOptions = [];
          var availableOptions = [];
          var selectedAnswers = [];
          group.querySelectorAll('.pill').forEach(function(p) {
            var word = plainText(p);
            if (p.classList.contains('option-marked')) markedOptions.push(word);
            if (p.classList.contains('selected')) selectedAnswers.push(word);
            availableOptions.push(word);
          });
          pushQuestionBlock(lines, {
            header: groups.length > 1 ? num + ' (' + (index + 1) + ')' : num,
            prompt: prompt,
            marked: row.classList.contains('marked'),
            myAnswer: selectedAnswers.length ? selectedAnswers.join('／') : '-',
            correctAnswer: joinOrNone(acceptableAnswers(group.dataset.ans || '')),
            markedOptions: joinOrNone(markedOptions),
            availableOptions: joinOrNone(availableOptions)
          });
        });
      });
    }
    sec.querySelectorAll('.mi-row').forEach(function(miRow) {
      var qNum = miRow.querySelector('.q-num') ? miRow.querySelector('.q-num').textContent.trim() : '';
      var qText = miRow.querySelector('.q-text') ? plainText(miRow.querySelector('.q-text')) : '';
      var ans = miRow.dataset.ans ? JSON.parse(miRow.dataset.ans) : null;
      var selectedOptions = [];
      var markedOptions = [];
      var availableOptions = [];
      miRow.querySelectorAll('.pill').forEach(function(p) {
        var word = plainText(p);
        var sel = p.classList.contains('selected');
        var opt = p.classList.contains('option-marked');
        if (sel) selectedOptions.push(word);
        if (opt) markedOptions.push(word);
        availableOptions.push(word);
      });
      pushQuestionBlock(lines, {
        header: qNum,
        prompt: qText,
        marked: miRow.classList.contains('marked'),
        myAnswer: joinOrNone(selectedOptions),
        correctAnswer: ans ? joinOrNone(ans) : '-',
        markedOptions: joinOrNone(markedOptions),
        availableOptions: joinOrNone(availableOptions)
      });
    });
    var blanks = sec.querySelectorAll('.blank-inp');
    if (blanks.length > 0) {
      var inQRow = sec.querySelector('.q-row .blank-inp');
      if (inQRow) {
        sec.querySelectorAll('.q-row').forEach(function(row) {
          var num = row.querySelector('.q-num') ? row.querySelector('.q-num').textContent.trim() : '';
          var textEl = row.querySelector('.q-text') || row;
          var sentence = '';
          var mine = [];
          var answers = [];
          textEl.childNodes.forEach(function(node) {
            if (node.nodeType === 3) sentence += node.textContent;
            else if (node.nodeName === 'INPUT') {
              sentence += fmtInp(node);
              mine.push(node.value.trim() || '___');
              answers.push(node.dataset.ans ? node.dataset.ans.trim() : '-');
            }
            else if (node.classList && node.classList.contains('answer-reveal')) {}
            else if (node.classList && node.classList.contains('mark-toggle')) {}
            else if (node.nodeName === 'BR') sentence += '\n   ';
            else sentence += node.textContent;
          });
          pushQuestionBlock(lines, {
            header: num,
            prompt: sentence.trim(),
            marked: row.classList.contains('marked'),
            myAnswer: joinOrNone(mine),
            correctAnswer: joinOrNone(answers)
          });
        });
      } else {
        sec.querySelectorAll('.compound-item').forEach(function(item) {
          var text = '';
          var mine = [];
          var answers = [];
          item.childNodes.forEach(function(node) {
            if (node.nodeType === 3) text += node.textContent;
            else if (node.nodeName === 'INPUT') {
              text += fmtInp(node);
              mine.push(node.value.trim() || '___');
              answers.push(node.dataset.ans ? node.dataset.ans.trim() : '-');
            }
            else if (node.classList && node.classList.contains('mark-toggle')) {}
            else if (node.nodeName === 'SPAN') text += plainText(node);
          });
          pushQuestionBlock(lines, {
            header: 'Compound item',
            prompt: text.trim(),
            marked: item.classList.contains('marked'),
            myAnswer: joinOrNone(mine),
            correctAnswer: joinOrNone(answers)
          });
        });
      }
      var bank = sec.querySelector('.token-bank');
      if (bank) {
        var usedTokens = [];
        var markedTokens = [];
        var allTokens = [];
        bank.querySelectorAll('.token').forEach(function(t) {
          var word = t.dataset.val || plainText(t);
          var used = t.classList.contains('used');
          var opt = t.classList.contains('option-marked');
          if (used) usedTokens.push(word);
          if (opt) markedTokens.push(word);
          allTokens.push(word);
        });
        lines.push('Word bank');
        lines.push('  Used: ' + joinOrNone(usedTokens));
        lines.push('  Marked: ' + joinOrNone(markedTokens));
        lines.push('  Available: ' + joinOrNone(allTokens));
        lines.push('');
      }
    }
    var jBlanks = sec.querySelectorAll('.blank-inp-j');
    if (jBlanks.length > 0) {
      sec.querySelectorAll('.q-row').forEach(function(row) {
        var num = row.querySelector('.q-num') ? row.querySelector('.q-num').textContent.trim() : '';
        var textEl = row.querySelector('.q-text') || row;
        var sentence = '';
        var mine = [];
        var answers = [];
        textEl.childNodes.forEach(function(node) {
          if (node.nodeType === 3) sentence += node.textContent;
          else if (node.nodeName === 'INPUT') {
            sentence += fmtInp(node);
            mine.push(node.value.trim() || '___');
            answers.push(node.dataset.ans ? node.dataset.ans.trim() : '-');
          }
          else if (node.classList && node.classList.contains('answer-reveal')) {}
          else if (node.classList && node.classList.contains('mark-toggle')) {}
          else if (node.nodeName === 'BR') sentence += '\n   ';
          else sentence += node.textContent;
        });
        pushQuestionBlock(lines, {
          header: num,
          prompt: sentence.trim(),
          marked: row.classList.contains('marked'),
          myAnswer: joinOrNone(mine),
          correctAnswer: joinOrNone(answers)
        });
      });
      var jBank = sec.querySelector('.token-bank');
      if (jBank) {
        var allTokens = [];
        var markedTokens = [];
        jBank.querySelectorAll('.token').forEach(function(t) {
          var word = plainText(t);
          allTokens.push(word);
          if (t.classList.contains('option-marked')) markedTokens.push(word);
        });
        lines.push('Word bank');
        lines.push('  Marked: ' + joinOrNone(markedTokens));
        lines.push('  Available: ' + joinOrNone(allTokens));
        lines.push('');
      }
    }
  });
  return lines.join('\n').trim() + '\n';
}

function exportAnswers(options) {
  options = options || {};
  showExportText(buildExportText(), !!options.noScroll);
  if (!options.skipSave) savePageState();
}

function copyExport() {
  var ta = document.getElementById('export-text');
  if (!ta) return;
  ta.select();
  document.execCommand('copy');
  if (window.event && window.event.target) {
    window.event.target.textContent = 'Copied!';
    setTimeout(function() { window.event.target.textContent = 'Copy to clipboard'; }, 1500);
  }
}
