#!/usr/bin/env python3
"""Generate a self-contained offline review page for audio/text mismatches."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVIDENCE = (
    ROOT / "work" / "vocabulary_audio_audit" / "n2_all_both" / "source_evidence.json"
)
DEFAULT_OUTPUT = (
    ROOT / "work" / "vocabulary_audio_audit" / "n2_all_both" / "review.html"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build an offline audio/text decision page from source evidence."
    )
    parser.add_argument("--evidence-json", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def prepare_rows(rows: list[dict[str, Any]], output_path: Path) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        audio_path = ROOT / str(row.get("audio_clip", "")).replace("/", os.sep)
        row["audio_url"] = os.path.relpath(audio_path, output_path.parent).replace(os.sep, "/")
        row["suggested_text"] = row.get("raw_line") or row.get("transcript") or row.get("expected", "")
        prepared.append(row)
    return prepared


def safe_json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def build_review_html(
    rows: list[dict[str, Any]],
    source_sha256: str,
    output_path: Path,
) -> str:
    payload = safe_json_for_script(prepare_rows(rows, output_path))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>N2 vocabulary audio review</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17212b;
      --muted: #617080;
      --line: #d7dee6;
      --paper: #ffffff;
      --wash: #f3f6f8;
      --accent: #145c72;
      --accent-soft: #dff1f5;
      --good: #20744a;
      --good-soft: #e2f4e9;
      --warn: #9a5a00;
      --warn-soft: #fff1d6;
      --keep: #5a4779;
      --keep-soft: #eee8f7;
      --shadow: 0 18px 50px rgba(23, 33, 43, .10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: linear-gradient(145deg, #eef4f5 0%, #f8f5ef 100%);
      color: var(--ink);
      font-family: Inter, "Yu Gothic UI", "Hiragino Sans", Meiryo, sans-serif;
    }}
    button, select, textarea, input {{ font: inherit; }}
    button {{ cursor: pointer; }}
    .shell {{ width: min(1040px, calc(100% - 28px)); margin: 0 auto; padding: 24px 0 50px; }}
    header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 16px;
    }}
    h1 {{ margin: 0 0 5px; font-size: clamp(1.45rem, 3vw, 2.05rem); letter-spacing: -.025em; }}
    .subtitle {{ margin: 0; color: var(--muted); }}
    .toolbar, .filters, .nav, .decision-buttons {{ display: flex; flex-wrap: wrap; gap: 9px; }}
    .toolbar {{ justify-content: flex-end; }}
    button, select, .file-label {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: var(--paper);
      color: var(--ink);
      padding: 9px 12px;
      min-height: 40px;
    }}
    button:hover, .file-label:hover {{ border-color: var(--accent); }}
    button:focus-visible, select:focus-visible, textarea:focus-visible, input:focus-visible {{
      outline: 3px solid rgba(20, 92, 114, .22);
      outline-offset: 2px;
    }}
    .file-label {{ display: inline-flex; align-items: center; cursor: pointer; }}
    .file-label input {{ display: none; }}
    .summary {{
      background: rgba(255,255,255,.72);
      border: 1px solid rgba(215,222,230,.9);
      border-radius: 14px;
      padding: 13px 15px;
      margin-bottom: 14px;
      backdrop-filter: blur(8px);
    }}
    .summary-row {{ display: flex; align-items: center; justify-content: space-between; gap: 14px; }}
    .counts {{ font-weight: 700; font-variant-numeric: tabular-nums; }}
    .progress {{ height: 8px; border-radius: 999px; overflow: hidden; background: #dfe6e9; margin-top: 11px; }}
    .progress > span {{ display: block; height: 100%; width: 0; background: var(--accent); transition: width .2s ease; }}
    .filters {{ margin-bottom: 14px; }}
    .card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .card-head {{ padding: 20px 22px 16px; border-bottom: 1px solid var(--line); }}
    .eyebrow {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; color: var(--muted); font-size: .9rem; }}
    .chip {{ border-radius: 999px; padding: 4px 9px; font-weight: 700; background: var(--wash); }}
    .chip.confirmed {{ color: var(--good); background: var(--good-soft); }}
    .chip.ambiguous {{ color: var(--warn); background: var(--warn-soft); }}
    .chip.supports {{ color: var(--keep); background: var(--keep-soft); }}
    h2 {{ margin: 12px 0 0; font-size: clamp(1.45rem, 4vw, 2.15rem); }}
    .content {{ padding: 20px 22px 24px; }}
    .audio-row {{ display: grid; grid-template-columns: auto 1fr; gap: 12px; align-items: center; margin-bottom: 18px; }}
    .play {{
      min-width: 92px;
      border-color: var(--accent);
      background: var(--accent);
      color: white;
      font-weight: 800;
    }}
    audio {{ width: 100%; min-width: 0; }}
    .comparison {{ display: grid; gap: 12px; grid-template-columns: 1fr 1fr; }}
    .text-box {{ border: 1px solid var(--line); border-radius: 14px; padding: 14px 15px; background: #fbfcfd; }}
    .text-box.suggested {{ border-color: #9dccd5; background: #f0fafb; }}
    .label {{ display: block; color: var(--muted); font-size: .78rem; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; margin-bottom: 7px; }}
    .jp {{ font-size: 1.17rem; line-height: 1.65; overflow-wrap: anywhere; }}
    details {{ margin-top: 12px; color: var(--muted); }}
    details .text-box {{ margin-top: 10px; color: var(--ink); }}
    .custom {{ margin-top: 18px; }}
    textarea {{
      width: 100%;
      min-height: 95px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px 13px;
      line-height: 1.55;
    }}
    .note {{ width: 100%; margin-top: 9px; border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; }}
    .decision-buttons {{ margin-top: 13px; }}
    .decision-buttons button {{ font-weight: 800; flex: 1 1 180px; }}
    .accept {{ border-color: var(--good); color: var(--good); background: var(--good-soft); }}
    .keep {{ border-color: var(--keep); color: var(--keep); background: var(--keep-soft); }}
    .save-custom {{ border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }}
    .decision-state {{ margin-top: 12px; min-height: 24px; color: var(--muted); font-weight: 700; }}
    .nav {{ justify-content: space-between; margin-top: 14px; }}
    .nav button {{ min-width: 130px; }}
    .empty {{ padding: 55px 24px; text-align: center; color: var(--muted); }}
    .shortcuts {{ margin-top: 16px; color: var(--muted); text-align: center; font-size: .86rem; }}
    kbd {{ border: 1px solid #cbd3da; border-bottom-width: 2px; border-radius: 5px; background: white; padding: 1px 5px; }}
    @media (max-width: 720px) {{
      header {{ display: block; }}
      .toolbar {{ justify-content: flex-start; margin-top: 14px; }}
      .summary-row, .audio-row {{ display: block; }}
      .filters select {{ flex: 1 1 150px; }}
      .comparison {{ grid-template-columns: 1fr; }}
      audio {{ margin-top: 10px; }}
      .card-head, .content {{ padding-left: 16px; padding-right: 16px; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>N2 vocabulary audio review</h1>
        <p class="subtitle">Listen, choose the canonical text, and export your decisions.</p>
      </div>
      <div class="toolbar">
        <button id="exportJson">Export JSON</button>
        <button id="exportCsv">Export CSV</button>
        <label class="file-label">Import JSON<input id="importJson" type="file" accept="application/json"></label>
      </div>
    </header>

    <section class="summary" aria-label="Review progress">
      <div class="summary-row">
        <div class="counts" id="counts">0 reviewed</div>
        <div id="position">0 / 0</div>
      </div>
      <div class="progress"><span id="progressBar"></span></div>
    </section>

    <section class="filters" aria-label="Review filters">
      <select id="classificationFilter" aria-label="Evidence classification">
        <option value="all">All evidence</option>
        <option value="source_confirmed">Source-confirmed</option>
        <option value="ambiguous">Ambiguous</option>
        <option value="source_supports_db">Source supports original</option>
      </select>
      <select id="decisionFilter" aria-label="Decision status">
        <option value="pending">Pending first</option>
        <option value="all">All decisions</option>
        <option value="decided">Decided only</option>
        <option value="replace">Accepted replacement</option>
        <option value="keep">Kept original</option>
        <option value="custom">Custom text</option>
      </select>
      <select id="unitFilter" aria-label="Unit"><option value="all">All units</option></select>
    </section>

    <article class="card" id="card">
      <div class="card-head">
        <div class="eyebrow">
          <span id="indexLabel"></span><span id="unitLabel"></span>
          <span class="chip" id="classificationChip"></span>
          <span id="scoreLabel"></span>
        </div>
        <h2 id="headword"></h2>
      </div>
      <div class="content">
        <div class="audio-row">
          <button class="play" id="playButton">▶ Play</button>
          <audio id="audio" controls preload="metadata"></audio>
        </div>
        <div class="comparison">
          <div class="text-box">
            <span class="label">Current original</span>
            <div class="jp" id="originalText"></div>
          </div>
          <div class="text-box suggested">
            <span class="label">Suggested replacement</span>
            <div class="jp" id="suggestedText"></div>
          </div>
        </div>
        <details>
          <summary>ASR and evidence details</summary>
          <div class="text-box"><span class="label">ASR transcript</span><div class="jp" id="asrText"></div></div>
          <div class="text-box"><span class="label">Raw OCR</span><div class="jp" id="rawText"></div></div>
          <div class="text-box"><span class="label">Evidence</span><div id="evidenceText"></div></div>
        </details>
        <div class="custom">
          <label class="label" for="customText">Custom replacement</label>
          <textarea id="customText" lang="ja" placeholder="Type the exact sentence you want to keep…"></textarea>
          <input class="note" id="reviewNote" placeholder="Optional review note">
        </div>
        <div class="decision-buttons">
          <button class="accept" id="acceptButton">✓ Accept replacement</button>
          <button class="keep" id="keepButton">Keep original</button>
          <button class="save-custom" id="customButton">Save custom text</button>
        </div>
        <div class="decision-state" id="decisionState" aria-live="polite"></div>
      </div>
    </article>
    <div class="empty" id="emptyState" hidden>No entries match the current filters.</div>
    <div class="nav">
      <button id="previousButton">← Previous</button>
      <button id="nextButton">Next →</button>
    </div>
    <p class="shortcuts"><kbd>Space</kbd> play · <kbd>A</kbd> accept · <kbd>K</kbd> keep · <kbd>C</kbd> custom · <kbd>←</kbd>/<kbd>→</kbd> navigate</p>
  </main>

  <script>
    const ITEMS = {payload};
    const SOURCE_SHA256 = "{source_sha256}";
    const STORAGE_KEY = "n2VocabularyAudioReview:v1:" + SOURCE_SHA256.slice(0, 12);
    const DECISION_LABELS = {{ replace: "Accepted replacement", keep: "Kept original", custom: "Custom replacement" }};
    let decisions = loadDecisions();
    let visibleItems = [];
    let cursor = 0;

    const $ = (id) => document.getElementById(id);
    const elements = Object.fromEntries([
      "counts","position","progressBar","classificationFilter","decisionFilter","unitFilter",
      "card","indexLabel","unitLabel","classificationChip","scoreLabel","headword","audio",
      "playButton","originalText","suggestedText","asrText","rawText","evidenceText","customText",
      "reviewNote","acceptButton","keepButton","customButton","decisionState","previousButton","nextButton",
      "emptyState"
    ].map(id => [id, $(id)]));

    function loadDecisions() {{
      try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{{}}"); }}
      catch {{ return {{}}; }}
    }}

    function saveDecisions() {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(decisions)); }}
    function keyFor(item) {{ return String(item.source_index) + ":sentence"; }}
    function currentItem() {{ return visibleItems[cursor] || null; }}
    function decisionFor(item) {{ return decisions[keyFor(item)] || null; }}

    function buildUnitFilter() {{
      const units = [...new Set(ITEMS.map(item => item.unit))].sort((a,b) => a-b);
      for (const unit of units) {{
        const option = document.createElement("option");
        option.value = String(unit); option.textContent = "Unit " + unit;
        elements.unitFilter.append(option);
      }}
    }}

    function applyFilters(preferredKey = null) {{
      const classification = elements.classificationFilter.value;
      const decisionFilter = elements.decisionFilter.value;
      const unit = elements.unitFilter.value;
      const priorKey = preferredKey || (currentItem() ? keyFor(currentItem()) : null);
      visibleItems = ITEMS.filter(item => {{
        const decision = decisionFor(item);
        if (classification !== "all" && item.classification !== classification) return false;
        if (unit !== "all" && String(item.unit) !== unit) return false;
        if (decisionFilter === "pending" && decision) return false;
        if (decisionFilter === "decided" && !decision) return false;
        if (["replace","keep","custom"].includes(decisionFilter) && decision?.decision !== decisionFilter) return false;
        return true;
      }});
      cursor = Math.max(0, visibleItems.findIndex(item => keyFor(item) === priorKey));
      if (cursor < 0) cursor = 0;
      render();
    }}

    function render() {{
      const reviewed = Object.keys(decisions).length;
      elements.counts.textContent = `${{reviewed}} reviewed · ${{ITEMS.length - reviewed}} pending`;
      elements.progressBar.style.width = `${{ITEMS.length ? reviewed / ITEMS.length * 100 : 0}}%`;
      const item = currentItem();
      if (!item) {{
        elements.card.hidden = true;
        elements.emptyState.hidden = false;
        elements.position.textContent = "0 / 0";
        elements.previousButton.disabled = elements.nextButton.disabled = true;
        return;
      }}
      elements.card.hidden = false;
      elements.emptyState.hidden = true;
      elements.position.textContent = `${{cursor + 1}} / ${{visibleItems.length}}`;
      elements.indexLabel.textContent = `#${{item.source_index}}`;
      elements.unitLabel.textContent = `Unit ${{item.unit}}`;
      const classLabels = {{source_confirmed:"Source-confirmed",ambiguous:"Ambiguous",source_supports_db:"Source supports original"}};
      elements.classificationChip.textContent = classLabels[item.classification] || item.classification;
      elements.classificationChip.className = "chip " + (item.classification === "source_confirmed" ? "confirmed" : item.classification === "ambiguous" ? "ambiguous" : "supports");
      elements.scoreLabel.textContent = `Audio score ${{Number(item.audit_score).toFixed(3)}}`;
      elements.headword.textContent = item.headword;
      elements.originalText.textContent = item.expected;
      elements.suggestedText.textContent = item.suggested_text;
      elements.asrText.textContent = item.transcript;
      elements.rawText.textContent = item.raw_line || "No raw OCR block extracted";
      elements.evidenceText.textContent = `ASR/raw ${{item.asr_vs_raw}} · DB/raw ${{item.db_vs_raw}} · margin ${{item.evidence_margin}} · ${{item.raw_page}}`;
      elements.audio.src = item.audio_url;
      const decision = decisionFor(item);
      elements.customText.value = decision?.decision === "custom" ? decision.replacement_text : item.suggested_text;
      elements.reviewNote.value = decision?.note || "";
      elements.decisionState.textContent = decision ? `Saved: ${{DECISION_LABELS[decision.decision]}}` : "Pending review";
      elements.previousButton.disabled = cursor === 0;
      elements.nextButton.disabled = cursor >= visibleItems.length - 1;
    }}

    function decide(kind, replacementText) {{
      const item = currentItem(); if (!item) return;
      decisions[keyFor(item)] = {{
        source_index: item.source_index,
        unit: item.unit,
        headword: item.headword,
        decision: kind,
        original_text: item.expected,
        replacement_text: replacementText,
        audio_clip: item.audio_clip,
        note: elements.reviewNote.value.trim(),
        updated_at: new Date().toISOString()
      }};
      saveDecisions();
      const key = keyFor(item);
      if (elements.decisionFilter.value === "pending") applyFilters(key);
      else {{ render(); if (cursor < visibleItems.length - 1) {{ cursor++; render(); }} }}
    }}

    function playCurrent() {{
      if (!currentItem()) return;
      if (elements.audio.paused) elements.audio.play(); else elements.audio.pause();
    }}
    function move(delta) {{
      cursor = Math.max(0, Math.min(visibleItems.length - 1, cursor + delta)); render();
    }}
    function download(name, type, text) {{
      const url = URL.createObjectURL(new Blob([text], {{type}}));
      const link = document.createElement("a"); link.href = url; link.download = name; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }}
    function exportPayload() {{
      return {{version:1, source_sha256:SOURCE_SHA256, exported_at:new Date().toISOString(), decisions:Object.values(decisions).sort((a,b)=>a.source_index-b.source_index)}};
    }}
    function csvCell(value) {{ return '"' + String(value ?? "").replaceAll('"','""') + '"'; }}

    elements.playButton.addEventListener("click", playCurrent);
    elements.acceptButton.addEventListener("click", () => {{ const item=currentItem(); if(item) decide("replace", item.suggested_text); }});
    elements.keepButton.addEventListener("click", () => {{ const item=currentItem(); if(item) decide("keep", item.expected); }});
    elements.customButton.addEventListener("click", () => {{
      const text = elements.customText.value.trim();
      if (!text) {{ elements.decisionState.textContent = "Enter custom text before saving."; elements.customText.focus(); return; }}
      decide("custom", text);
    }});
    elements.previousButton.addEventListener("click", () => move(-1));
    elements.nextButton.addEventListener("click", () => move(1));
    [elements.classificationFilter,elements.decisionFilter,elements.unitFilter].forEach(el => el.addEventListener("change", () => applyFilters()));
    $("exportJson").addEventListener("click", () => download("n2-audio-review-decisions.json", "application/json", JSON.stringify(exportPayload(), null, 2)));
    $("exportCsv").addEventListener("click", () => {{
      const fields=["source_index","unit","headword","decision","original_text","replacement_text","audio_clip","note","updated_at"];
      const lines=[fields.join(","), ...exportPayload().decisions.map(row => fields.map(field => csvCell(row[field])).join(","))];
      download("n2-audio-review-decisions.csv", "text/csv;charset=utf-8", "\\ufeff" + lines.join("\\r\\n"));
    }});
    $("importJson").addEventListener("change", async event => {{
      const file=event.target.files[0]; if(!file) return;
      try {{
        const payload=JSON.parse(await file.text());
        if(payload.source_sha256 && payload.source_sha256 !== SOURCE_SHA256 && !confirm("This decision file was made for a different audit source. Import anyway?")) return;
        decisions=Object.fromEntries((payload.decisions || []).map(row => [String(row.source_index)+":sentence", row]));
        saveDecisions(); applyFilters();
      }} catch(error) {{ alert("Could not import decisions: " + error.message); }}
      event.target.value="";
    }});
    document.addEventListener("keydown", event => {{
      if (["TEXTAREA","INPUT","SELECT"].includes(event.target.tagName)) return;
      if (event.code === "Space") {{ event.preventDefault(); playCurrent(); }}
      else if (event.key === "ArrowLeft") move(-1);
      else if (event.key === "ArrowRight") move(1);
      else if (event.key.toLowerCase() === "a") elements.acceptButton.click();
      else if (event.key.toLowerCase() === "k") elements.keepButton.click();
      else if (event.key.toLowerCase() === "c") elements.customText.focus();
    }});

    buildUnitFilter();
    applyFilters();
  </script>
</body>
</html>
"""


def main() -> int:
    args = build_parser().parse_args()
    source_bytes = args.evidence_json.read_bytes()
    rows = json.loads(source_bytes.decode("utf-8"))
    if not isinstance(rows, list):
        raise ValueError("evidence JSON must contain a list")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        build_review_html(rows, hashlib.sha256(source_bytes).hexdigest(), args.output),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"rows": len(rows), "output": str(args.output), "audio_links": len(rows)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
