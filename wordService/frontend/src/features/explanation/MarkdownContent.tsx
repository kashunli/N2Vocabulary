import type { ReactNode } from "react";

import { isDuplicateMarkdownParagraph } from "./markdownText.mjs";

type MarkdownBlock =
  | {kind: "paragraph"; lines: string[]}
  | {kind: "heading"; level: 1 | 2 | 3; text: string}
  | {kind: "list"; ordered: boolean; items: string[]}
  | {kind: "rule"};

function renderInlineMarkdown(value: string): ReactNode[] {
  const tokens = value.split(/(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g).filter(Boolean);
  return tokens.map((token, index) => {
    if (token.startsWith("**") && token.endsWith("**")) {
      return <strong key={index}>{token.slice(2, -2)}</strong>;
    }
    if (token.startsWith("*") && token.endsWith("*")) {
      return <em key={index}>{token.slice(1, -1)}</em>;
    }
    if (token.startsWith("`") && token.endsWith("`")) {
      return <code key={index}>{token.slice(1, -1)}</code>;
    }
    return <span key={index}>{token}</span>;
  });
}

function parseMarkdown(value: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listOrdered = false;

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({kind: "paragraph", lines: paragraph});
    paragraph = [];
  };
  const flushList = () => {
    if (listItems.length) blocks.push({kind: "list", ordered: listOrdered, items: listItems});
    listItems = [];
  };

  value.replace(/\r\n/g, "\n").split("\n").forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      return;
    }
    if (/^---+$/.test(line)) {
      flushParagraph();
      flushList();
      blocks.push({kind: "rule"});
      return;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({kind: "heading", level: heading[1].length as 1 | 2 | 3, text: heading[2]});
      return;
    }
    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      flushParagraph();
      if (listItems.length && listOrdered) flushList();
      listOrdered = false;
      listItems.push(bullet[1]);
      return;
    }
    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    if (numbered) {
      flushParagraph();
      if (listItems.length && !listOrdered) flushList();
      listOrdered = true;
      listItems.push(numbered[1]);
      return;
    }
    flushList();
    paragraph.push(line);
  });

  flushParagraph();
  flushList();
  return blocks;
}

export function MarkdownContent({value, omitParagraph}: {value: string; omitParagraph?: string}) {
  const blocks = parseMarkdown(value).filter((block) => block.kind !== "paragraph" || !isDuplicateMarkdownParagraph(block.lines, omitParagraph));
  return <div className="react-explanation react-markdown">
    {blocks.map((block, index) => {
      if (block.kind === "rule") return <hr key={index} />;
      if (block.kind === "heading") {
        if (block.level === 1) return <h3 key={index}>{renderInlineMarkdown(block.text)}</h3>;
        if (block.level === 2) return <h4 key={index}>{renderInlineMarkdown(block.text)}</h4>;
        return <h5 key={index}>{renderInlineMarkdown(block.text)}</h5>;
      }
      if (block.kind === "list") {
        const ListTag = block.ordered ? "ol" : "ul";
        return <ListTag key={index}>{block.items.map((item, itemIndex) => <li key={itemIndex}>{renderInlineMarkdown(item)}</li>)}</ListTag>;
      }
      return <p key={index}>{block.lines.map((line, lineIndex) => <span key={lineIndex}>{lineIndex ? <br /> : null}{renderInlineMarkdown(line)}</span>)}</p>;
    })}
  </div>;
}
