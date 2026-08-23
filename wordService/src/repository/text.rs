pub(super) fn word_text_for_tts(word: &str, reading: Option<&str>) -> String {
    let display = word.trim();
    let reading = reading.unwrap_or("").trim();
    if display.is_empty()
        || display.is_ascii()
        || display.chars().any(|ch| ch.is_ascii_alphabetic())
    {
        return reading.to_string();
    }
    display.to_string()
}

/// Normalize OCR/study notation into a sentence Edge TTS can read naturally.
///
/// The database often keeps textbook shorthand such as `｛な／の｝`, leading
/// sense indexes like `②`, and furigana in parentheses. Those are useful for a
/// human reader, but the TTS request should contain one plain pronounceable
/// sentence. The rule is intentionally conservative and local: when the book
/// offers alternatives, choose the first option instead of trying to invent a
/// new sentence.
pub fn clean_sentence_text_for_tts(raw: &str) -> String {
    let mut text = raw
        .replace('｛', "{")
        .replace('｝', "}")
        .replace('（', "(")
        .replace('）', ")")
        .replace('\u{3000}', " ");

    text = strip_leading_noise(&text);
    text = replace_choice_groups(&text, '{', '}', true);
    text = strip_leading_noise(&text);
    text = strip_leading_example_marker(&text);
    text = replace_choice_groups(&text, '(', ')', false);
    text = collapse_slash_ellipsis_lists(&text);
    text = text
        .replace("……", "")
        .replace('…', "")
        .replace("...", "")
        .replace('※', "")
        .replace("。 ・", "。")
        .replace("」 ・", "」");
    text = text.chars().filter(|ch| !is_circled_number(*ch)).collect();
    text = collapse_sentence_spaces(&text);

    // Some rows become empty after removing pure index markers. Keeping this as
    // a final pass lets the normal empty-sentence guard report them cleanly.
    strip_leading_noise(&text)
}

fn replace_choice_groups(text: &str, open: char, close: char, keep_plain_group: bool) -> String {
    let mut output = String::new();
    let mut rest = text;

    while let Some(open_at) = rest.find(open) {
        output.push_str(&rest[..open_at]);
        let after_open = &rest[open_at + open.len_utf8()..];
        let Some(close_at) = find_matching_close(after_open, open, close) else {
            output.push(open);
            rest = after_open;
            continue;
        };

        let group = &after_open[..close_at];
        let replacement = if group_has_choice(group) {
            first_choice(group)
        } else if keep_plain_group {
            clean_choice_fragment(group)
        } else {
            String::new()
        };
        if !replacement.is_empty() && output.ends_with(char::is_whitespace) {
            output.pop();
        }
        output.push_str(&replacement);
        rest = &after_open[close_at + close.len_utf8()..];
        if !replacement.is_empty() {
            rest = rest.trim_start();
        }
    }

    output.push_str(rest);
    output
}

fn find_matching_close(text: &str, open: char, close: char) -> Option<usize> {
    let mut depth = 0usize;
    for (index, ch) in text.char_indices() {
        if ch == open {
            depth += 1;
        } else if ch == close {
            if depth == 0 {
                return Some(index);
            }
            depth -= 1;
        }
    }
    None
}

fn group_has_choice(value: &str) -> bool {
    value.contains('/') || value.contains('／') || value.contains('…')
}

fn first_choice(value: &str) -> String {
    let first = value.split(['/', '／']).next().unwrap_or(value);
    clean_choice_fragment(first)
}

fn clean_choice_fragment(value: &str) -> String {
    value
        .replace("……", "")
        .replace('…', "")
        .replace("...", "")
        .trim()
        .to_string()
}

fn collapse_slash_ellipsis_lists(text: &str) -> String {
    let mut output = text.to_string();
    for ellipsis in ["……", "…", "..."] {
        while let Some(ellipsis_at) = output.find(ellipsis) {
            let before = &output[..ellipsis_at];
            let Some(slash_at) = before.rfind(['/', '／']) else {
                break;
            };
            let list_start = find_choice_list_start(before, slash_at);
            let remove_start = before[list_start..]
                .find(['/', '／'])
                .map(|offset| list_start + offset)
                .unwrap_or(slash_at);
            output.replace_range(remove_start..ellipsis_at + ellipsis.len(), "");
        }
    }
    output
}

fn find_choice_list_start(text: &str, slash_at: usize) -> usize {
    text[..slash_at]
        .char_indices()
        .rev()
        .find(|(_, ch)| {
            matches!(
                ch,
                '。' | '、' | '「' | '」' | ' ' | '\t' | '\n' | '・' | '(' | ')' | '[' | ']'
            )
        })
        .map(|(index, ch)| index + ch.len_utf8())
        .unwrap_or(0)
}

fn strip_leading_noise(raw: &str) -> String {
    let mut text = raw.trim_start().to_string();

    loop {
        let before = text.clone();
        text = strip_leading_square_metadata(&text);
        text = strip_leading_label_colon(&text);
        text = text
            .trim_start_matches(|ch: char| {
                ch.is_whitespace()
                    || is_circled_number(ch)
                    || matches!(ch, '・' | '･' | '-' | 'ー' | '※')
            })
            .trim_start()
            .to_string();
        if text == before {
            break;
        }
    }

    text.trim().to_string()
}

fn strip_leading_square_metadata(raw: &str) -> String {
    let text = raw.trim_start();
    if !text.starts_with('[') {
        return text.to_string();
    }

    let metadata_end = text
        .find('・')
        .and_then(|bullet_at| text[..bullet_at].rfind(']'))
        .or_else(|| text.find(']').filter(|end| *end <= 24));

    match metadata_end {
        Some(end) => text[end + 1..].trim_start().to_string(),
        None => text.to_string(),
    }
}

fn strip_leading_label_colon(raw: &str) -> String {
    let text = raw.trim_start();
    let Some(colon_at) = text.find(':') else {
        return text.to_string();
    };
    if colon_at <= 18 {
        return text[colon_at + 1..].trim_start().to_string();
    }
    text.to_string()
}

fn strip_leading_example_marker(raw: &str) -> String {
    let text = raw.trim_start();
    for marker in ["(例.", "(例:", "(例)"] {
        if let Some(rest) = text.strip_prefix(marker) {
            return rest.trim().trim_end_matches(')').trim().to_string();
        }
    }
    text.to_string()
}

fn is_circled_number(ch: char) -> bool {
    matches!(
        ch,
        '①' | '②'
            | '③'
            | '④'
            | '⑤'
            | '⑥'
            | '⑦'
            | '⑧'
            | '⑨'
            | '⑩'
            | '⑪'
            | '⑫'
            | '⑬'
            | '⑭'
            | '⑮'
            | '⑯'
            | '⑰'
            | '⑱'
            | '⑲'
            | '⑳'
    )
}

fn collapse_sentence_spaces(raw: &str) -> String {
    let mut text = raw.split_whitespace().collect::<Vec<_>>().join(" ");
    for particle in [
        "を", "が", "に", "の", "へ", "と", "で", "は", "も", "から", "まで", "より",
    ] {
        text = text.replace(&format!(" {particle}"), particle);
    }
    for punctuation in ["。", "、", "」", "』", "）", ")", "！", "？"] {
        text = text.replace(&format!(" {punctuation}"), punctuation);
    }
    for punctuation in ["「", "『", "（", "("] {
        text = text.replace(&format!("{punctuation} "), punctuation);
    }
    text.trim().to_string()
}
