use anyhow::{Context, Result};
use serde::Serialize;
use serde_json::json;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use tiny_http::{Header, Method, Request, Response, StatusCode};
use url::Url;

pub(super) fn static_asset_path(static_dir: &Path, request_path: &str) -> Option<PathBuf> {
    match request_path {
        "/styles.css" | "/favicon.svg" | "/app.js" | "/audio-review.html" | "/audio-review.css"
        | "/audio-review.js" => Some(static_dir.join(request_path.trim_start_matches('/'))),
        _ => {
            if let Some(asset_name) = request_path
                .strip_prefix("/assets/")
                .or_else(|| request_path.strip_prefix("/study-wall-react/assets/"))
            {
                // Vite emits one-level hashed JS/CSS assets. Keep both the
                // root deployment path and the former React path narrow so the
                // bundle cannot expose arbitrary files.
                if asset_name.is_empty()
                    || asset_name.contains('/')
                    || asset_name.contains('\\')
                    || asset_name.contains("..")
                    || !(asset_name.ends_with(".js") || asset_name.ends_with(".css"))
                {
                    return None;
                }
                return Some(
                    static_dir
                        .join("react-rail")
                        .join("assets")
                        .join(asset_name),
                );
            }
            let module_name = request_path.strip_prefix("/js/")?;
            // ES module imports only need direct files in static/js. Keeping the
            // route flat avoids accidentally exposing arbitrary static subtrees.
            if module_name.is_empty()
                || module_name.contains('/')
                || module_name.contains('\\')
                || module_name.contains("..")
                || !module_name.ends_with(".js")
            {
                return None;
            }
            Some(static_dir.join("js").join(module_name))
        }
    }
}

pub(super) fn send_json<T: Serialize>(
    request: Request,
    status: StatusCode,
    payload: &T,
) -> Result<()> {
    let data = serde_json::to_vec(payload)?;
    let mut headers = cors_headers();
    headers.push(header("Cache-Control", "no-store"));
    headers.push(header("Content-Type", "application/json; charset=utf-8"));

    // HEAD should return the same status/headers as GET without a response
    // body. This helper centralizes that rule for every JSON endpoint.
    if request.method() == &Method::Head {
        request.respond(add_headers(Response::empty(status), headers))?;
    } else {
        request.respond(add_headers(
            Response::from_data(data).with_status_code(status),
            headers,
        ))?;
    }
    Ok(())
}

pub(super) fn send_file(request: Request, path: &Path, content_type: &str) -> Result<()> {
    if !path.exists() || !path.is_file() {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    }
    let ctype = if content_type.is_empty() {
        // Let mime_guess handle static assets where the type is obvious from
        // the extension. Audio routes pass an explicit content type above.
        mime_guess::from_path(path)
            .first_or_octet_stream()
            .essence_str()
            .to_string()
    } else {
        content_type.to_string()
    };
    let mut headers = vec![
        header("Cache-Control", "no-store"),
        header("Content-Type", &ctype),
    ];
    headers.extend(cors_headers());

    if request.method() == &Method::Head {
        request.respond(add_headers(Response::empty(StatusCode(200)), headers))?;
    } else {
        request.respond(add_headers(
            Response::from_data(fs::read(path)?).with_status_code(StatusCode(200)),
            headers,
        ))?;
    }
    Ok(())
}

fn add_headers<R: Read>(mut response: Response<R>, headers: Vec<Header>) -> Response<R> {
    for header in headers {
        response.add_header(header);
    }
    response
}

pub(super) fn parse_local_url(raw: &str) -> Result<Url> {
    // tiny_http exposes only the path/query part for normal requests. Prefixing
    // a dummy host lets the `url` crate parse query strings with standard URL
    // rules instead of hand-splitting on `?` and `&`.
    Url::parse(&format!("http://localhost{raw}")).context("parse request URL")
}

pub(super) fn query_map(url: &Url) -> std::collections::HashMap<String, String> {
    url.query_pairs()
        .map(|(key, value)| (key.into_owned(), value.into_owned()))
        .collect()
}

pub(super) fn cors_headers() -> Vec<Header> {
    vec![
        header("Access-Control-Allow-Origin", "*"),
        header(
            "Access-Control-Allow-Methods",
            "GET, PUT, POST, DELETE, OPTIONS",
        ),
        header("Access-Control-Allow-Headers", "Content-Type"),
    ]
}

fn header(name: &str, value: &str) -> Header {
    Header::from_bytes(name.as_bytes(), value.as_bytes()).expect("static header should be valid")
}

pub(super) fn send_options(request: Request) -> Result<()> {
    let response = add_headers(Response::empty(StatusCode(204)), cors_headers());
    request.respond(response)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::static_asset_path;
    use std::path::Path;

    #[test]
    fn static_asset_path_allows_known_static_files_and_js_modules() {
        let root = Path::new("static");
        assert_eq!(
            static_asset_path(root, "/styles.css").as_deref(),
            Some(Path::new("static/styles.css"))
        );
        assert_eq!(
            static_asset_path(root, "/favicon.svg").as_deref(),
            Some(Path::new("static/favicon.svg"))
        );
        assert_eq!(
            static_asset_path(root, "/js/main.js").as_deref(),
            Some(Path::new("static/js/main.js"))
        );
        assert_eq!(
            static_asset_path(root, "/audio-review.html").as_deref(),
            Some(Path::new("static/audio-review.html"))
        );
        assert_eq!(
            static_asset_path(root, "/audio-review.js").as_deref(),
            Some(Path::new("static/audio-review.js"))
        );
        assert_eq!(
            static_asset_path(root, "/study-wall-react/assets/index-abc123.js").as_deref(),
            Some(Path::new("static/react-rail/assets/index-abc123.js"))
        );
        assert_eq!(
            static_asset_path(root, "/assets/index-abc123.js").as_deref(),
            Some(Path::new("static/react-rail/assets/index-abc123.js"))
        );
    }

    #[test]
    fn static_asset_path_rejects_nested_or_non_js_module_paths() {
        let root = Path::new("static");
        assert!(static_asset_path(root, "/js/../app.js").is_none());
        assert!(static_asset_path(root, "/js/nested/main.js").is_none());
        assert!(static_asset_path(root, "/js/main.css").is_none());
        assert!(static_asset_path(root, "/api/summary").is_none());
        assert!(static_asset_path(root, "/study-wall-rail.html").is_none());
        assert!(static_asset_path(root, "/study-wall-rail.css").is_none());
        assert!(static_asset_path(root, "/study-wall-react/assets/../index.js").is_none());
        assert!(static_asset_path(root, "/study-wall-react/assets/index.html").is_none());
    }
}
