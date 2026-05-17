#!/usr/bin/env python3
"""Batch-generate Japanese sentence explanations with DeepSeek.

The script never edits vocabulary.json directly. It writes reviewable JSON files
that can be inspected and merged later.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROMPT_STYLE = """你是一位日语句子讲解老师，学习者是中文母语者，目标水平为 JLPT N2-N3，汉字能力较强，但需要掌握日语里的真实用法、搭配、语感和中日差异。

每个输入项目会包含 index、target_word、reading、kanji、verb_pattern 和 sentence。target_word 是这个句子主要想学习的词，请优先围绕它解释。

请为每个日语句子生成一个 Markdown 格式的中文讲解。

每个 explanation 必须包含：
1. 加粗的自然中文翻译
2. 一条分隔线 `---`
3. 项目符号列表，不要添加标题

项目符号格式：
- **词语（よみ）** - 核心义；语感、搭配或中日差异 [JLPT Nx]
- **动词（よみ）** - 核心义；他動詞/自動詞、对象助词或对应词 [JLPT Nx]
- **~语法** - 语气、逻辑关系或误解点 [JLPT Nx]
- **固定搭配/表达** - 直译 => 自然理解；场景/限制

风格要求：
- 默认使用中文解释；如果某个词、语法标签或细微差别用英文更清楚、更自然，可以夹用简短英文。
- 中文翻译要自然，不要逐字硬翻。
- 讲解要短而准，优先解释本句真正影响理解的点。
- 优先讲语感和辨析，不要堆列表；宁可少讲，也要讲准。
- 每条笔记都必须紧扣这个句子，不要写泛泛的词典说明。
- 长项目符号要在 `=>`、`↔`、`；` 等自然边界处分开，避免一条过长。
- 不要写“在本句中表示/这里的用法是/这个语法的功能是”等模板话；直接讲结论。
- 需要时使用符号：`=>` 表示结果/引申，`↔` 表示对比/对应词，`≈` 表示近似，`≠` 表示不同/误解，`→` 表示方向/变化，`+` 表示构词/搭配组成，`〇/×/△` 表示自然/错误/勉强可用。
- 重要日语词语加粗；必要时用斜体标出直译。
- 对有汉字的关键词标注假名读音；纯假名词只有在有助于理解时才说明。
- 如果一个常写假名的词有对应汉字，也要简短标出汉字形；如果现代日语通常写假名，请标注“常写假名/汉字少用”。
- 如果是和语，要说明字面感觉和语义引申。
- 如果构词透明，可以写：`A + B => 词义`。
- 如果是汉语词，只在日语用法和中文明显不同时解释。
- 如果语法形包住了固定搭配或复合表达，先解释底层表达，再解释语法变化：例如 `声をかける` => `声をかけられる`。
- 如果日语词或语法点有直接的中文或英文对应表达，请简短标出：中文≈... / English≈...；如果只是接近但不完全等同，用 `≈`，不要假装完全相同。
- 明确指出中文母语者容易误解的表达，例如：のに、らしい、そうだ、ようだ、わけ、ものだ、受身、使役、自动词/他动词等。
- 如果出现 迷惑の受身，必须明确标注。

跳过：
- N5 内容通常跳过；但如果它有非基础用法，或会影响更高阶语法理解，可以简短说明。
- 汉字部件拆解。
- 和中文意思完全相同、用法也没有差异的汉语词。
- 表格、长篇总结、多个替代表达、完整活用表。

输出要求：
只返回合法 JSON。
不要返回解释 JSON 以外的文字。
不要添加额外字段。
"""


SENTENCE_KEYS = ("sentence", "sentence_text", "text", "japanese", "ja")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch Japanese sentence explanations via DeepSeek API."
    )
    parser.add_argument("--input", required=True, help="Input JSON file.")
    parser.add_argument("--output", help="Optional combined output JSON file.")
    parser.add_argument("--output-dir", help="Folder for per-batch JSON files and a manifest.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip records with a non-empty explanation field.")
    parser.add_argument("--start-index", type=int, help="Only include records with index >= this value.")
    parser.add_argument("--end-index", type=int, help="Only include records with index <= this value.")
    parser.add_argument("--limit", type=int, help="Maximum number of selected records.")
    parser.add_argument("--batch-size", type=int, default=15, help="Sentences per DeepSeek request.")
    parser.add_argument("--model", default="deepseek-v4-flash", help="DeepSeek model id.")
    parser.add_argument("--base-url", default="https://api.deepseek.com", help="DeepSeek OpenAI-format base URL.")
    parser.add_argument("--thinking", choices=("enabled", "disabled"), default="disabled", help="DeepSeek thinking mode.")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument("--max-tokens", type=int, default=8192, help="Maximum output tokens per request. Use 0 to omit max_tokens.")
    parser.add_argument("--timeout", type=int, default=120, help="HTTP timeout seconds.")
    parser.add_argument("--sleep", type=float, default=0.5, help="Seconds to sleep between batches.")
    parser.add_argument("--retries", type=int, default=2, help="Retries when the model returns invalid JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Write selected records without calling the API.")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_windows_environment_variable(name: str) -> str | None:
    """Read persistent Windows User/Machine env vars that may not be in this shell."""
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None

    locations = [
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ]
    for root, subkey in locations:
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _value_type = winreg.QueryValueEx(key, name)
        except OSError:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def get_api_key() -> str | None:
    return os.environ.get("DEEPSEEK_API_KEY") or get_windows_environment_variable("DEEPSEEK_API_KEY")


def first_sentence_value(item: dict[str, Any]) -> str:
    for key in SENTENCE_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def normalize_records(data: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("sentences"), list):
        raw_items = data["sentences"]
    elif isinstance(data, list):
        raw_items = data
    else:
        raise SystemExit("Input must be a JSON array or an object with a 'sentences' array.")

    records: list[dict[str, Any]] = []
    for position, item in enumerate(raw_items, start=1):
        if isinstance(item, str):
            record = {"index": position, "sentence": item.strip()}
        elif isinstance(item, dict):
            sentence = first_sentence_value(item)
            record = {
                "index": item.get("index", item.get("id", position)),
                "sentence": sentence,
            }
            for key in ("headword_text", "reading", "kanji", "verb_pattern"):
                if item.get(key):
                    record[key] = item[key]
            if "id" in item:
                record["id"] = item["id"]
            if args.skip_existing and item.get("explanation"):
                continue
        else:
            continue

        if not record["sentence"]:
            continue
        if isinstance(record["index"], int):
            if args.start_index is not None and record["index"] < args.start_index:
                continue
            if args.end_index is not None and record["index"] > args.end_index:
                continue
        records.append(record)
        if args.limit is not None and len(records) >= args.limit:
            break
    return records


def chunks(records: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    if size <= 0:
        raise SystemExit("--batch-size must be greater than 0.")
    return [records[i : i + size] for i in range(0, len(records), size)]


def require_output_target(args: argparse.Namespace) -> None:
    if not args.output and not args.output_dir:
        raise SystemExit("Provide --output-dir for monitored batch files, or --output for one combined JSON file.")


def output_dir_path(args: argparse.Namespace) -> Path | None:
    return Path(args.output_dir) if args.output_dir else None


def write_batch_artifacts(
    out_dir: Path | None,
    batch_number: int,
    batch_results: list[dict[str, Any]],
    all_results: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    if out_dir is None:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / f"batch_{batch_number:04d}.json", batch_results)
    write_json(out_dir / "all_explanations.json", all_results)
    write_json(out_dir / "manifest.json", manifest)


def build_user_prompt(batch: list[dict[str, Any]]) -> str:
    payload = []
    for item in batch:
        payload_item = {
            "index": item["index"],
            "target_word": item.get("headword_text", ""),
            "reading": item.get("reading", ""),
            "kanji": item.get("kanji", ""),
            "verb_pattern": item.get("verb_pattern", ""),
            "sentence": item["sentence"],
        }
        payload.append(payload_item)
    return (
        "请讲解下面的日语句子。\n"
        "只返回一个合法 JSON object，格式必须是：\n"
        '{"items":[{"index":1,"explanation":"**自然中文翻译**\\n\\n---\\n\\n- ..."}]}\n'
        "每个 explanation 使用 Markdown，并严格遵守 system prompt 的中文讲解风格。不要添加额外字段。\n\n"
        f"Sentences:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def call_deepseek(batch: list[dict[str, Any]], args: argparse.Namespace, api_key: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = args.base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": PROMPT_STYLE + "\nReturn valid JSON only."},
            {"role": "user", "content": build_user_prompt(batch)},
        ],
        "thinking": {"type": args.thinking},
        "response_format": {"type": "json_object"},
        "temperature": args.temperature,
    }
    if args.max_tokens:
        body["max_tokens"] = args.max_tokens
    last_json_error: json.JSONDecodeError | None = None
    attempts = max(1, args.retries + 1)
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"DeepSeek HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SystemExit(f"DeepSeek request failed: {exc}") from exc

        response_data = json.loads(raw)
        content = response_data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            last_json_error = exc
            if attempt < attempts:
                print(f"Invalid JSON from DeepSeek, retrying {attempt}/{args.retries}...", flush=True)
                time.sleep(args.sleep or 0.5)
                continue
            raise SystemExit(f"DeepSeek JSON response was invalid after {attempts} attempt(s): {exc}") from exc
        items = parsed.get("items")
        if not isinstance(items, list):
            if attempt < attempts:
                print(f"DeepSeek response missing items array, retrying {attempt}/{args.retries}...", flush=True)
                time.sleep(args.sleep or 0.5)
                continue
            raise SystemExit(f"DeepSeek JSON response did not contain an items array: {content[:500]}")
        return items, response_data.get("usage", {})

    raise SystemExit(f"DeepSeek JSON response was invalid: {last_json_error}")


def index_lookup(batch: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
    lookup: dict[Any, dict[str, Any]] = {}
    for item in batch:
        lookup[item["index"]] = item
        lookup[str(item["index"])] = item
    return lookup


def normalize_output_items(batch: list[dict[str, Any]], generated: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_by_index = index_lookup(batch)
    results: list[dict[str, Any]] = []
    for item in generated:
        idx = item.get("index")
        explanation = item.get("explanation")
        source = source_by_index.get(idx, source_by_index.get(str(idx)))
        if source is None or not isinstance(explanation, str) or not explanation.strip():
            continue
        out = {
            "index": source["index"],
            "sentence": source["sentence"],
            "explanation": explanation.strip(),
        }
        if "id" in source:
            out["id"] = source["id"]
        results.append(out)
    return results


def main() -> int:
    args = parse_args()
    require_output_target(args)
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None
    out_dir = output_dir_path(args)
    records = normalize_records(load_json(input_path), args)

    if args.dry_run:
        selected = [{"index": r["index"], "sentence": r["sentence"], "explanation": None} for r in records]
        if out_dir is not None:
            write_json(out_dir / "selected_records.json", selected)
            print(f"Dry run selected {len(records)} records -> {out_dir / 'selected_records.json'}")
        if output_path is not None:
            write_json(output_path, selected)
            print(f"Dry run selected {len(records)} records -> {output_path}")
        return 0

    api_key = get_api_key()
    if not api_key:
        raise SystemExit(
            "DEEPSEEK_API_KEY was not found in the current process env, Windows User env, or Windows Machine env."
        )

    all_results: list[dict[str, Any]] = []
    total_usage: dict[str, int] = {}
    batches = chunks(records, args.batch_size)
    manifest: dict[str, Any] = {
        "input": str(input_path),
        "model": args.model,
        "thinking": args.thinking,
        "selected_records": len(records),
        "batch_size": args.batch_size,
        "completed_batches": 0,
        "completed_explanations": 0,
        "usage": total_usage,
    }
    for number, batch in enumerate(batches, start=1):
        print(f"Batch {number}/{len(batches)}: {len(batch)} sentence(s)", flush=True)
        generated, usage = call_deepseek(batch, args, api_key)
        batch_results = normalize_output_items(batch, generated)
        all_results.extend(batch_results)
        for key, value in usage.items():
            if isinstance(value, int):
                total_usage[key] = total_usage.get(key, 0) + value
        manifest["completed_batches"] = number
        manifest["completed_explanations"] = len(all_results)
        manifest["usage"] = total_usage
        write_batch_artifacts(out_dir, number, batch_results, all_results, manifest)
        if output_path is not None:
            write_json(output_path, all_results)
        if args.sleep and number < len(batches):
            time.sleep(args.sleep)

    if out_dir is not None:
        print(f"Wrote {len(all_results)} explanations -> {out_dir}")
    if output_path is not None:
        print(f"Wrote combined explanations -> {output_path}")
    if total_usage:
        print("Usage:", json.dumps(total_usage, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
