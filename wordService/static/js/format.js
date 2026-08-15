export function escapeHTML(value) {
  return String(value || "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function inlineMarkdown(value) {
  // Keep Markdown rendering deliberately small and safe. We escape first, then
  // add only the formatting patterns the generated explanations commonly use.
  return escapeHTML(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

export function markdownToHTML(value) {
  const blocks = [];
  let paragraph = [];
  let list = [];
  let listTag = "ul";

  function flushParagraph() {
    if (!paragraph.length) return;
    blocks.push(`<p>${paragraph.map(inlineMarkdown).join("<br>")}</p>`);
    paragraph = [];
  }

  function flushList() {
    if (!list.length) return;
    blocks.push(`<${listTag}>${list.map(item => `<li>${inlineMarkdown(item)}</li>`).join("")}</${listTag}>`);
    list = [];
    listTag = "ul";
  }

  String(value || "").replace(/\r\n/g, "\n").split("\n").forEach(rawLine => {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      return;
    }

    if (/^---+$/.test(line)) {
      flushParagraph();
      flushList();
      blocks.push("<hr>");
      return;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push(`<h${heading[1].length}>${inlineMarkdown(heading[2])}</h${heading[1].length}>`);
      return;
    }

    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      flushParagraph();
      if (listTag !== "ul") flushList();
      listTag = "ul";
      list.push(bullet[1]);
      return;
    }

    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    if (numbered) {
      flushParagraph();
      if (listTag !== "ol") flushList();
      listTag = "ol";
      list.push(numbered[1]);
      return;
    }

    flushList();
    paragraph.push(line);
  });

  flushParagraph();
  flushList();
  return blocks.join("");
}

export function rubyOrPlain(kanji, reading) {
  if (!reading || reading === kanji) return escapeHTML(kanji);
  return `<ruby><rb>${escapeHTML(kanji)}</rb><rt>${escapeHTML(reading)}</rt></ruby>`;
}

export function meaningHTML(entry) {
  const parts = [];
  if (entry.meaning_en) parts.push(`<span class="en">${escapeHTML(entry.meaning_en)}</span>`);
  if (entry.meaning_zh) parts.push(`<span class="zh">${escapeHTML(entry.meaning_zh)}</span>`);
  return parts.join(" · ");
}

export function cardMeaningHTML(entry) {
  const parts = [];
  if (entry.meaning_en) parts.push(`<span class="en">${escapeHTML(entry.meaning_en)}</span>`);
  if (entry.meaning_zh) parts.push(`<span class="zh">${escapeHTML(entry.meaning_zh)}</span>`);
  return parts.join(" · ");
}

export function sourceReferenceHTML(note) {
  const title = note.source_title || note.source_book_code || "Source";
  const parts = [escapeHTML(title)];
  if (note.source_page !== undefined && note.source_page !== null) {
    parts.push(`page ${escapeHTML(note.source_page)}`);
  }
  if (note.source_cd_track) {
    parts.push(`CD ${escapeHTML(note.source_cd_track)}`);
  }
  return `${parts.join(", ")} <span class="source-reference-code">(${escapeHTML(note.source_book_code)} #${escapeHTML(note.source_index)})</span>`;
}

function hasVisibleSourceNote(note) {
  return Boolean(
    note.source_title
      || note.source_page !== undefined && note.source_page !== null
      || note.source_cd_track
      || note.notes_md
  );
}

export function sourceMetadataHTML(entry) {
  const sections = [];
  (entry.source_notes || []).forEach(note => {
    if (!hasVisibleSourceNote(note)) return;
    const details = [];
    if (note.reading && note.reading !== entry.reading) {
      details.push(`<div><strong>Reading:</strong> ${escapeHTML(note.reading)}</div>`);
    }
    if (note.meaning_en && note.meaning_en !== entry.meaning_en) {
      details.push(`<div><strong>Meaning:</strong> ${escapeHTML(note.meaning_en)}</div>`);
    }
    if (note.meaning_zh && note.meaning_zh !== entry.meaning_zh) {
      details.push(`<div><strong>中文释义:</strong> ${escapeHTML(note.meaning_zh)}</div>`);
    }
    const source = sourceReferenceHTML(note);
    const notes = note.notes_md ? markdownToHTML(note.notes_md) : "";
    sections.push(`
      <article class="source-note">
        <div class="source-reference-line">${source}</div>
        ${details.join("")}
        ${notes ? `<div class="source-notes-label">Source notes</div>${notes}` : ""}
      </article>
    `);
  });
  return sections.join("");
}

export function detailExplanationHTML(entry) {
  if (!entry.explanation_md) return "";
  const heading = entry.book_code === "GWB_N2" ? "Study notes" : "Sentence explanation";
  return `<section class="explanation-section"><h4>${heading}</h4>${markdownToHTML(entry.explanation_md)}</section>`;
}

export function translationHTML(entry) {
  const parts = [];
  if (entry.sentence_translation_en) {
    parts.push(`<span class="en">${escapeHTML(entry.sentence_translation_en)}</span>`);
  }
  if (entry.sentence_translation_zh) {
    parts.push(`<span class="zh">${escapeHTML(entry.sentence_translation_zh)}</span>`);
  }
  return parts.join(" / ");
}

export function exampleTranslationHTML(item) {
  const parts = [];
  if (item.translation_en) parts.push(`<span class="en">${escapeHTML(item.translation_en)}</span>`);
  if (item.translation_zh) parts.push(`<span class="zh">${escapeHTML(item.translation_zh)}</span>`);
  return parts.join(" / ");
}

export function exampleBadgeHTML(item) {
  if (item.category) {
    return exampleCategoryBadgeHTML(item);
  }
  return item.position === 0
    ? '<span class="badge">main</span>'
    : `<span class="badge">example ${item.position}</span>`;
}

export function exampleCategoryBadgeHTML(item) {
  if (!item.category) return "";
  const categories = {
    "連": { label: "Collocation", css: "collocation" },
    "合": { label: "Compound", css: "compound" },
    "対": { label: "Antonym", css: "antonym" },
    "類": { label: "Synonym", css: "synonym" },
    "慣": { label: "Idiom", css: "idiom" },
    "関連": { label: "Related", css: "related" },
    collocation: { label: "Collocation", css: "collocation" },
    compound: { label: "Compound", css: "compound" },
    antonym: { label: "Antonym", css: "antonym" },
    synonym: { label: "Synonym", css: "synonym" },
    idiom: { label: "Idiom", css: "idiom" },
    related: { label: "Related", css: "related" },
  };
  const category = categories[item.category] || { label: item.category, css: "related" };
  return `<span class="badge category-${escapeHTML(category.css)}">${escapeHTML(category.label)}</span>`;
}

export function exampleKey(entryId, position) {
  return `${entryId}:${position}`;
}

export function unitLabel(unit) {
  if (!unit) return "Section";
  return unit.title || unit.header || `Section ${String(unit.number).padStart(2, "0")}`;
}

export function exampleSourceLabel(item) {
  return `from ${item.word || ""} · ${unitLabel(item.unit)} · #${item.source_index}`;
}
