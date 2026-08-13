use super::response::{parse_local_url, query_map, send_json};
use crate::audio_review::{AudioReviewStore, AudioReviewUpdate};
use crate::config::AppConfig;
use crate::repository::WordRepository;
use crate::tts::TtsService;
use anyhow::Result;
use serde::Deserialize;
use serde_json::json;
use std::collections::HashMap;
use tiny_http::{Request, StatusCode};

pub(super) fn handle_post(
    mut request: Request,
    config: AppConfig,
    repository: WordRepository,
    tts_service: TtsService,
) -> Result<()> {
    let parsed = parse_local_url(request.url())?;
    let path = parsed.path().trim_end_matches('/').to_string();
    let params = query_map(&parsed);
    let repository = repository_for_params(&repository, &params);
    if path == "/api/study/resolve" {
        #[derive(Deserialize)]
        struct ResolveItem {
            item_uuid: String,
            preferred_book_code: Option<String>,
            preferred_source_index: Option<i64>,
        }
        #[derive(Deserialize)]
        struct ResolveRequest {
            items: Vec<ResolveItem>,
        }

        let mut body = String::new();
        request.as_reader().read_to_string(&mut body)?;
        let payload: ResolveRequest = match serde_json::from_str::<ResolveRequest>(&body) {
            Ok(value) if value.items.len() <= 100 => value,
            Ok(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "at most 100 items may be resolved"}),
                );
            }
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "invalid review resolution payload"}),
                );
            }
        };
        let mut items = Vec::new();
        for item in payload.items {
            if let Some(entry) = repository.resolve_item_for_review(
                &item.item_uuid,
                item.preferred_book_code.as_deref(),
                item.preferred_source_index,
            )? {
                items.push(entry);
            }
        }
        return send_json(request, StatusCode(200), &json!({"items": items}));
    }
    if let Some(rest) = path.strip_prefix("/api/units/") {
        let parts = rest.split('/').collect::<Vec<_>>();
        if parts.len() == 2 && parts[1] == "flagged-audio" {
            let unit_number = match parts[0].parse::<i64>() {
                Ok(value) => value,
                Err(_) => {
                    return send_json(
                        request,
                        StatusCode(400),
                        &json!({"error": "unit must be an integer"}),
                    );
                }
            };
            return match repository.export_unit_flagged_audio(unit_number) {
                Ok(payload) => send_json(request, StatusCode(200), &payload),
                Err(error)
                    if error.to_string().contains("no flagged words")
                        || error.to_string().contains("missing audio clips")
                        || error.to_string().contains("unit must be") =>
                {
                    send_json(
                        request,
                        StatusCode(400),
                        &json!({"error": error.to_string()}),
                    )
                }
                Err(error) => send_json(
                    request,
                    StatusCode(500),
                    &json!({"error": error.to_string()}),
                ),
            };
        }
    }

    let Some(rest) = path.strip_prefix("/api/entries/") else {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    };
    // Expected shapes:
    // /api/entries/{entry_id}/audio
    // /api/entries/{entry_id}/examples/{position}/audio
    // Splitting after the fixed prefix keeps parsing straightforward and makes
    // invalid routes return 404 instead of accidentally matching a partial path.
    let parts = rest.split('/').collect::<Vec<_>>();
    if parts.len() == 2 && parts[1] == "audio" {
        let entry_id = match parts[0].parse::<i64>() {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "invalid entry id"}),
                );
            }
        };
        return match repository.ensure_word_audio(entry_id, &config.tts.generated_dir, |word| {
            tts_service.synthesize_sentence(word)
        }) {
            Ok(payload) => send_json(request, StatusCode(200), &payload),
            Err(error)
                if error.to_string().contains("unknown entry")
                    || error.to_string().contains("empty word") =>
            {
                send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": error.to_string()}),
                )
            }
            Err(error) => send_json(
                request,
                StatusCode(500),
                &json!({"error": error.to_string()}),
            ),
        };
    }
    if parts.len() != 4 || parts[1] != "examples" || parts[3] != "audio" {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    }
    let entry_id = match parts[0].parse::<i64>() {
        Ok(value) => value,
        Err(_) => {
            return send_json(
                request,
                StatusCode(400),
                &json!({"error": "invalid entry id"}),
            );
        }
    };
    let position = match parts[2].parse::<i64>() {
        Ok(value) => value,
        Err(_) => {
            return send_json(
                request,
                StatusCode(400),
                &json!({"error": "invalid sentence index"}),
            );
        }
    };

    let result = repository.ensure_example_audio(
        entry_id,
        position,
        &config.tts.generated_dir,
        |sentence| tts_service.synthesize_sentence(sentence),
    );
    // The repository returns domain errors as anyhow messages. Mapping the
    // known ones here keeps HTTP status choices in the HTTP layer.
    match result {
        Ok(payload) => send_json(request, StatusCode(200), &payload),
        Err(error) if error.to_string().contains("unknown example") => send_json(
            request,
            StatusCode(404),
            &json!({"error": "unknown example"}),
        ),
        Err(error) if error.to_string().contains("empty sentence") => send_json(
            request,
            StatusCode(400),
            &json!({"error": "empty sentence"}),
        ),
        Err(error) => send_json(
            request,
            StatusCode(500),
            &json!({"error": error.to_string()}),
        ),
    }
}

pub(super) fn handle_put(
    mut request: Request,
    repository: WordRepository,
    audio_review: AudioReviewStore,
) -> Result<()> {
    let parsed = parse_local_url(request.url())?;
    let path = parsed.path().trim_end_matches('/').to_string();
    let params = query_map(&parsed);
    let repository = repository_for_params(&repository, &params);
    let mut body = String::new();
    request.as_reader().read_to_string(&mut body)?;
    // An empty PUT body means "clear both flags". That matches the frontend's
    // simple mark contract and avoids requiring `{}` for a no-state mark.
    let body: serde_json::Value =
        match serde_json::from_str(if body.trim().is_empty() { "{}" } else { &body }) {
            Ok(value) => value,
            Err(_) => {
                return send_json(request, StatusCode(400), &json!({"error": "invalid JSON"}));
            }
        };

    if let Some(id_text) = path.strip_prefix("/api/audio-review/") {
        let source_index = match id_text.parse::<i64>() {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "source index must be integer"}),
                );
            }
        };
        let update = match serde_json::from_value::<AudioReviewUpdate>(body.clone()) {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "invalid audio review payload"}),
                );
            }
        };
        return match audio_review.set_decision(source_index, update) {
            Ok(decision) => send_json(request, StatusCode(200), &decision),
            Err(error) if error.to_string().contains("unknown audio review item") => send_json(
                request,
                StatusCode(404),
                &json!({"error": "unknown audio review item"}),
            ),
            Err(error)
                if error.to_string().contains("invalid audio review decision")
                    || error.to_string().contains("cannot be empty")
                    || error.to_string().contains("equivalent to the original") =>
            {
                send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": error.to_string()}),
                )
            }
            Err(error) => Err(error),
        };
    }

    if let Some(id_text) = path.strip_prefix("/api/marks/") {
        let entry_id = match id_text.parse::<i64>() {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "entry id must be integer"}),
                );
            }
        };

        let known = body
            .get("known")
            .and_then(|value| value.as_bool())
            .unwrap_or(false);
        let flagged = body
            .get("flagged")
            .and_then(|value| value.as_bool())
            .unwrap_or(false);

        return match repository.set_mark(entry_id, known, flagged) {
            Ok(()) => send_json(request, StatusCode(200), &json!({"ok": true})),
            Err(error) if error.to_string().contains("unknown entry_id") => send_json(
                request,
                StatusCode(404),
                &json!({"error": "unknown entry_id"}),
            ),
            Err(error) => Err(error),
        };
    }

    if let Some(rest) = path.strip_prefix("/api/entries/") {
        let parts = rest.split('/').collect::<Vec<_>>();
        if parts.len() == 4 && parts[1] == "examples" && parts[3] == "star" {
            let entry_id = match parts[0].parse::<i64>() {
                Ok(value) => value,
                Err(_) => {
                    return send_json(
                        request,
                        StatusCode(400),
                        &json!({"error": "entry id must be integer"}),
                    );
                }
            };
            let position = match parts[2].parse::<i64>() {
                Ok(value) => value,
                Err(_) => {
                    return send_json(
                        request,
                        StatusCode(400),
                        &json!({"error": "sentence index must be integer"}),
                    );
                }
            };
            let starred = body
                .get("starred")
                .and_then(|value| value.as_bool())
                .unwrap_or(false);
            return match repository.set_sentence_star(entry_id, position, starred) {
                Ok(()) => send_json(
                    request,
                    StatusCode(200),
                    &json!({"ok": true, "starred": starred}),
                ),
                Err(error) if error.to_string().contains("unknown example") => send_json(
                    request,
                    StatusCode(404),
                    &json!({"error": "unknown example"}),
                ),
                Err(error) => Err(error),
            };
        }
    }

    send_json(request, StatusCode(404), &json!({"error": "not found"}))
}

pub(super) fn handle_delete(request: Request, audio_review: AudioReviewStore) -> Result<()> {
    let parsed = parse_local_url(request.url())?;
    let path = parsed.path().trim_end_matches('/').to_string();
    let Some(id_text) = path.strip_prefix("/api/audio-review/") else {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    };
    let source_index = match id_text.parse::<i64>() {
        Ok(value) => value,
        Err(_) => {
            return send_json(
                request,
                StatusCode(400),
                &json!({"error": "source index must be integer"}),
            );
        }
    };
    match audio_review.clear_decision(source_index) {
        Ok(cleared) => send_json(
            request,
            StatusCode(200),
            &json!({"ok": true, "cleared": cleared}),
        ),
        Err(error) if error.to_string().contains("unknown audio review item") => send_json(
            request,
            StatusCode(404),
            &json!({"error": "unknown audio review item"}),
        ),
        Err(error) => Err(error),
    }
}

pub(super) fn repository_for_params(
    repository: &WordRepository,
    params: &HashMap<String, String>,
) -> WordRepository {
    match params.get("book").filter(|value| !value.trim().is_empty()) {
        Some(book_code) => repository.for_book(book_code),
        None => repository.clone(),
    }
}
