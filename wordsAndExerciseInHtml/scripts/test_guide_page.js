/**
 * Exercise index-page builder.
 *
 * The index/guide page is mostly stable UI glue: it scans generated pages,
 * reads embedded page metadata, and writes exercises/n2/index.html. Keeping it
 * away from the section renderers saves context when debugging individual tests.
 */
const fs = require('fs');
const path = require('path');
const {
  DATA_ROOT,
  DEFAULT_OUTPUT_ROOT,
  pageLabel,
  pageTitle,
  preferredHtmlForJson,
  repoRelative,
  toPosixPath,
  walkFiles
} = require('./test_page_builder');

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


module.exports = {
  collectGuideEntriesFromHtml,
  collectGuideEntriesFromJson,
  writeGuidePage
};
