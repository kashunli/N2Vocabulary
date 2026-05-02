/**
 * Stable exercise-page assets.
 *
 * This file keeps the large CSS strings and shared browser runtime loading out
 * of the renderer. These blocks are rarely edited compared with the exercise
 * rendering logic, so isolating them keeps future code-reading focused.
 */
const fs = require('fs');
const path = require('path');

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

.pill.correct-ans .pill-label {
  border-color: #2a9d4a !important;
  background: #eafaf0 !important;
  color: #1a6e35 !important;
  font-weight: 700;
}

.pill.wrong-sel .pill-label {
  border-color: #d94040 !important;
  background: #fdf0f0 !important;
  color: #d94040 !important;
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


module.exports = { CSS, EXTRA_PAGE_CSS, SHARED_PAGE_JS };
