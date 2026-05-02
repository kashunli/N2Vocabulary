/**
 * CLI for applying explicit render_type tags to exercise JSON.
 *
 * Run this before regenerating pages when source JSON changes. It keeps the
 * render-time path simple: classify once in JSON, then render by tag.
 */
const fs = require('fs');
const path = require('path');
const { inferRenderType, canonicalRenderType } = require('./render_type_rules');

const ROOT = path.resolve(__dirname, '..');

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

function parseArgs(argv) {
  const opts = { write: false, force: false, root: path.join(ROOT, 'exercise_json', 'n2') };
  const positional = [];
  argv.forEach(arg => {
    if (arg === '--write') opts.write = true;
    else if (arg === '--force') opts.force = true;
    else positional.push(arg);
  });
  if (positional[0]) opts.root = path.resolve(ROOT, positional[0]);
  return opts;
}

function analyzeFile(file, opts) {
  const raw = fs.readFileSync(file, 'utf8');
  const data = JSON.parse(raw);
  let changed = false;
  const counts = new Map();
  const sections = [];

  (data.exercises || []).forEach(ex => {
    const before = canonicalRenderType(ex.render_type || ex.type);
    const inferred = inferRenderType(ex);
    const finalType = opts.force || !before ? inferred : before;
    counts.set(finalType, (counts.get(finalType) || 0) + 1);
    sections.push({ id: ex.id || '?', before: before || '', render_type: finalType });
    if ((opts.force || !before) && ex.render_type !== finalType) {
      ex.render_type = finalType;
      changed = true;
    }
  });

  if (opts.write && changed) {
    fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n');
  }

  return { file, changed, counts, sections };
}

function mergeCounts(target, source) {
  for (const [key, value] of source.entries()) {
    target.set(key, (target.get(key) || 0) + value);
  }
}

function main(argv) {
  const opts = parseArgs(argv);
  const files = walkFiles(opts.root, file => file.endsWith('.json') && !file.includes(`${path.sep}answerPages${path.sep}`));
  const totalCounts = new Map();
  let changedFiles = 0;
  let sectionCount = 0;

  files.forEach(file => {
    const result = analyzeFile(file, opts);
    if (result.changed) changedFiles += 1;
    sectionCount += result.sections.length;
    mergeCounts(totalCounts, result.counts);
  });

  console.log(`files=${files.length}`);
  console.log(`sections=${sectionCount}`);
  console.log(`changed_files=${changedFiles}`);
  console.log('render_types=' + JSON.stringify(Object.fromEntries([...totalCounts.entries()].sort()), null, 2));
  if (!opts.write) console.log('dry_run=true; pass --write to update JSON render_type tags');
}

main(process.argv.slice(2));
