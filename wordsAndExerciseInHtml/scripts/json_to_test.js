/**
 * Thin CLI entry point for generating N2 exercise HTML.
 *
 * Design: keep command-line parsing and filesystem orchestration here, while
 * rendering, page assets, tagging, and guide-page generation live in smaller
 * modules. That lets future agents inspect only the file matching their task.
 */
const fs = require('fs');
const path = require('path');
const { enrichMissingAnswers } = require('./answer_enrichment');
const {
  ANSWER_PAGES_DIR,
  DEFAULT_OUTPUT_ROOT,
  ROOT,
  buildHtml,
  pageLabel,
  pageTitle,
  repoRelative,
  resolveOutputPath,
  toPosixPath,
  walkFiles
} = require('./test_page_builder');
const { collectGuideEntriesFromHtml, writeGuidePage } = require('./test_guide_page');

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
  const answerPagesSegment = `${path.sep}answerPages${path.sep}`;
  const files = walkFiles(absRoot, file => file.endsWith('.json') && !file.includes(answerPagesSegment))
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

if (require.main === module) {
  main(process.argv.slice(2));
}

module.exports = { generateFiles, generateFolder, main, parseGenerateOptions };
