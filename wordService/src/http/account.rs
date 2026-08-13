use super::response::{header, parse_local_url, send_json, send_json_with_headers};
use crate::repository::WordRepository;
use crate::scheduler::ReviewGrade;
use crate::user_store::{AuthContext, SESSION_COOKIE, StudyCard, UserStore};
use anyhow::Result;
use serde::Deserialize;
use serde_json::json;
use std::collections::HashMap;
use tiny_http::{Request, StatusCode};

pub(super) fn is_account_path(path: &str) -> bool {
    path.starts_with("/api/auth/")
        || path == "/api/study/state"
        || path == "/api/study/import-guest"
        || path.starts_with("/api/study/cards/")
}

pub(super) fn handle_get(request: Request, users: UserStore) -> Result<()> {
    let path = parse_local_url(request.url())?
        .path()
        .trim_end_matches('/')
        .to_string();
    let Some(auth) = authenticate_request(&request, &users)? else {
        return send_json(
            request,
            StatusCode(401),
            &json!({"error": "authentication required"}),
        );
    };
    match path.as_str() {
        "/api/auth/me" => send_json(
            request,
            StatusCode(200),
            &json!({"user": auth.user, "csrf_token": auth.csrf_token}),
        ),
        "/api/study/state" => send_json(request, StatusCode(200), &users.snapshot(auth.user.id)?),
        _ => send_json(request, StatusCode(404), &json!({"error": "not found"})),
    }
}

pub(super) fn handle_post(
    mut request: Request,
    users: UserStore,
    repository: WordRepository,
) -> Result<()> {
    let path = parse_local_url(request.url())?
        .path()
        .trim_end_matches('/')
        .to_string();
    let body = read_json(&mut request)?;
    if path == "/api/auth/register" || path == "/api/auth/login" {
        #[derive(Deserialize)]
        struct Credentials {
            email: String,
            password: String,
        }
        let credentials: Credentials = match serde_json::from_value(body) {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "email and password are required"}),
                );
            }
        };
        let result = if path.ends_with("register") {
            users.register(&credentials.email, &credentials.password)
        } else {
            users.login(&credentials.email, &credentials.password)
        };
        return match result {
            Ok(session) => send_json_with_headers(
                request,
                StatusCode(200),
                &json!({"user": session.user, "csrf_token": session.csrf_token}),
                vec![session_cookie(&session.token)],
            ),
            Err(error) => {
                let message = error.to_string();
                let status = if message.contains("too many login") {
                    StatusCode(429)
                } else if message.contains("invalid email or password") {
                    StatusCode(401)
                } else {
                    StatusCode(400)
                };
                send_json(request, status, &json!({"error": message}))
            }
        };
    }

    let Some(auth) = authenticate_request(&request, &users)? else {
        return send_json(
            request,
            StatusCode(401),
            &json!({"error": "authentication required"}),
        );
    };
    if !valid_csrf(&request, &auth) {
        return send_json(
            request,
            StatusCode(403),
            &json!({"error": "invalid CSRF token"}),
        );
    }
    if path == "/api/auth/logout" {
        users.logout(&auth.session_token_hash)?;
        return send_json_with_headers(
            request,
            StatusCode(200),
            &json!({"ok": true}),
            vec![clear_session_cookie()],
        );
    }

    if path == "/api/study/import-guest" {
        #[derive(Deserialize)]
        struct GuestImport {
            import_id: String,
            snapshot_checksum: String,
            cards: HashMap<String, StudyCard>,
        }
        let import: GuestImport = match serde_json::from_value(body) {
            Ok(value) => value,
            Err(_) => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "invalid guest snapshot"}),
                );
            }
        };
        if import.snapshot_checksum.len() != 64
            || !import
                .snapshot_checksum
                .bytes()
                .all(|byte| byte.is_ascii_hexdigit())
        {
            return send_json(
                request,
                StatusCode(400),
                &json!({"error": "invalid snapshot checksum"}),
            );
        }
        for (key, card) in &import.cards {
            if key != &card.item_uuid
                || card.good_step > 6
                || card.enrolled_at.is_some() != card.due_at.is_some()
                || !valid_card_timestamps(card)
                || repository
                    .resolve_item_for_review(key, None, None)?
                    .is_none()
            {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": format!("unknown item UUID: {key}")}),
                );
            }
            if let (Some(book), Some(source_index)) =
                (&card.preferred_book_code, card.preferred_source_index)
                && repository
                    .resolve_item_for_review(key, Some(book), Some(source_index))?
                    .is_none()
            {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": format!("invalid preferred source for: {key}")}),
                );
            }
        }
        return match users.import_guest(
            auth.user.id,
            &import.import_id,
            &import.snapshot_checksum,
            import.cards.into_values().collect(),
        ) {
            Ok(snapshot) => send_json(request, StatusCode(200), &snapshot),
            Err(error) if error.to_string().contains("already used") => send_json(
                request,
                StatusCode(409),
                &json!({"error": error.to_string()}),
            ),
            Err(error) => Err(error),
        };
    }

    let Some(rest) = path.strip_prefix("/api/study/cards/") else {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    };
    let parts = rest.split('/').collect::<Vec<_>>();
    if parts.len() != 2 {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    }
    let item_uuid = parts[0];
    if repository
        .resolve_item_for_review(item_uuid, None, None)?
        .is_none()
    {
        return send_json(
            request,
            StatusCode(404),
            &json!({"error": "unknown item UUID"}),
        );
    }
    if parts[1] == "played" {
        let book = body
            .get("preferred_book_code")
            .and_then(|value| value.as_str())
            .unwrap_or("");
        let source_index = body
            .get("preferred_source_index")
            .and_then(|value| value.as_i64())
            .unwrap_or(-1);
        if repository
            .resolve_item_for_review(item_uuid, Some(book), Some(source_index))?
            .is_none()
        {
            return send_json(
                request,
                StatusCode(400),
                &json!({"error": "invalid preferred source"}),
            );
        }
        return send_json(
            request,
            StatusCode(200),
            &json!({"card": users.record_played(auth.user.id, item_uuid, book, source_index)?}),
        );
    }
    if parts[1] == "grade" {
        let grade: ReviewGrade = match body
            .get("grade")
            .cloned()
            .and_then(|value| serde_json::from_value(value).ok())
        {
            Some(value) => value,
            None => {
                return send_json(
                    request,
                    StatusCode(400),
                    &json!({"error": "grade must be again, hard, or good"}),
                );
            }
        };
        return match users.grade(auth.user.id, item_uuid, grade) {
            Ok(card) => send_json(request, StatusCode(200), &json!({"card": card})),
            Err(error)
                if error.to_string().contains("unenrolled")
                    || error.to_string().contains("not found") =>
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
    send_json(request, StatusCode(404), &json!({"error": "not found"}))
}

fn valid_card_timestamps(card: &StudyCard) -> bool {
    [
        card.enrolled_at.as_deref(),
        card.due_at.as_deref(),
        card.last_reviewed_at.as_deref(),
        card.last_played_at.as_deref(),
        Some(card.updated_at.as_str()),
    ]
    .into_iter()
    .flatten()
    .all(|value| chrono::DateTime::parse_from_rfc3339(value).is_ok())
}

pub(super) fn handle_put(
    mut request: Request,
    users: UserStore,
    repository: WordRepository,
) -> Result<()> {
    let path = parse_local_url(request.url())?
        .path()
        .trim_end_matches('/')
        .to_string();
    let Some(auth) = authenticate_request(&request, &users)? else {
        return send_json(
            request,
            StatusCode(401),
            &json!({"error": "authentication required"}),
        );
    };
    if !valid_csrf(&request, &auth) {
        return send_json(
            request,
            StatusCode(403),
            &json!({"error": "invalid CSRF token"}),
        );
    }
    let body = read_json(&mut request)?;
    let Some(rest) = path.strip_prefix("/api/study/cards/") else {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    };
    let parts = rest.split('/').collect::<Vec<_>>();
    if parts.len() != 2 || parts[1] != "marks" {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    }
    if repository
        .resolve_item_for_review(parts[0], None, None)?
        .is_none()
    {
        return send_json(
            request,
            StatusCode(404),
            &json!({"error": "unknown item UUID"}),
        );
    }
    let known = body
        .get("known")
        .and_then(|value| value.as_bool())
        .unwrap_or(false);
    let flagged = body
        .get("flagged")
        .and_then(|value| value.as_bool())
        .unwrap_or(false);
    send_json(
        request,
        StatusCode(200),
        &json!({"card": users.set_marks(auth.user.id, parts[0], known, flagged)?}),
    )
}

fn read_json(request: &mut Request) -> Result<serde_json::Value> {
    let mut body = String::new();
    request.as_reader().read_to_string(&mut body)?;
    Ok(
        serde_json::from_str(if body.trim().is_empty() { "{}" } else { &body })
            .unwrap_or(serde_json::Value::Null),
    )
}

fn authenticate_request(request: &Request, users: &UserStore) -> Result<Option<AuthContext>> {
    let cookie = header_value(request, "Cookie").unwrap_or_default();
    let token = cookie
        .split(';')
        .find_map(|part| {
            let (name, value) = part.trim().split_once('=')?;
            (name == SESSION_COOKIE).then_some(value)
        })
        .unwrap_or("");
    users.authenticate(token)
}

fn valid_csrf(request: &Request, auth: &AuthContext) -> bool {
    header_value(request, "X-CSRF-Token").is_some_and(|value| value == auth.csrf_token)
}

fn header_value<'a>(request: &'a Request, name: &'static str) -> Option<&'a str> {
    request
        .headers()
        .iter()
        .find(|header| header.field.equiv(name))
        .map(|header| header.value.as_str())
}

fn session_cookie(token: &str) -> tiny_http::Header {
    header(
        "Set-Cookie",
        &format!("{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000"),
    )
}

fn clear_session_cookie() -> tiny_http::Header {
    header(
        "Set-Cookie",
        &format!("{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"),
    )
}
