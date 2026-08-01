use crate::models::EntryExample;

pub(super) fn search_matches(
    examples: Option<&Vec<EntryExample>>,
    search_terms: &[String],
) -> Option<Vec<EntryExample>> {
    if search_terms.is_empty() {
        return None;
    }

    let matches = examples
        .map(Vec::as_slice)
        .unwrap_or(&[])
        .iter()
        .filter(|example| {
            example_matches_all_fields(example, &search_terms[0])
                || search_terms
                    .iter()
                    .skip(1)
                    .any(|term| example_matches_text(example, term))
        })
        .cloned()
        .collect::<Vec<_>>();

    if matches.is_empty() {
        None
    } else {
        Some(matches)
    }
}

pub(super) fn search_terms(search: &str) -> Vec<String> {
    let trimmed = search.trim();
    if trimmed.is_empty() {
        return Vec::new();
    }

    let mut terms = vec![trimmed.to_lowercase()];
    if let Some(stem) = trailing_u_stem(trimmed) {
        let stem = stem.to_lowercase();
        if !terms.contains(&stem) {
            terms.push(stem);
        }
    }
    terms
}

fn trailing_u_stem(search: &str) -> Option<String> {
    let mut chars = search.chars().collect::<Vec<_>>();
    if chars.len() <= 1 || chars.last() != Some(&'う') {
        return None;
    }
    chars.pop();
    Some(chars.into_iter().collect())
}

fn example_matches_all_fields(example: &EntryExample, needle: &str) -> bool {
    [
        example.text.as_str(),
        example.reading.as_str(),
        example.translation_en.as_str(),
        example.translation_zh.as_str(),
    ]
    .iter()
    .any(|value| value.to_lowercase().contains(needle))
}

fn example_matches_text(example: &EntryExample, needle: &str) -> bool {
    example.text.to_lowercase().contains(needle)
}
