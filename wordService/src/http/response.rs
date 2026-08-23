use anyhow::{Context, Result};
use serde::Serialize;
use serde_json::json;
use sha2::{Digest, Sha256};
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use tiny_http::{Header, Method, Request, Response, StatusCode};
use url::Url;

const VERSIONED_AUDIO_CACHE_CONTROL: &str = "public, max-age=31536000, immutable";
const LEGACY_AUDIO_REDIRECT_CACHE_CONTROL: &str = "no-store";

pub(super) fn static_asset_path(static_dir: &Path, request_path: &str) -> Option<PathBuf> {
    match request_path {
        "/favicon.svg" | "/audio-review.html" | "/audio-review.css" | "/audio-review.js" => {
            Some(static_dir.join(request_path.trim_start_matches('/')))
        }
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
            None
        }
    }
}

pub(super) fn send_json<T: Serialize>(
    request: Request,
    status: StatusCode,
    payload: &T,
) -> Result<()> {
    let data = serde_json::to_vec(payload)?;
    let headers = vec![
        header("Cache-Control", "no-store"),
        header("Content-Type", "application/json; charset=utf-8"),
    ];

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

pub(super) fn send_json_with_headers<T: Serialize>(
    request: Request,
    status: StatusCode,
    payload: &T,
    extra_headers: Vec<Header>,
) -> Result<()> {
    let data = serde_json::to_vec(payload)?;
    let mut headers = vec![
        header("Cache-Control", "no-store"),
        header("Content-Type", "application/json; charset=utf-8"),
    ];
    headers.extend(extra_headers);
    request.respond(add_headers(
        Response::from_data(data).with_status_code(status),
        headers,
    ))?;
    Ok(())
}

pub(super) fn send_file(request: Request, path: &Path, content_type: &str) -> Result<()> {
    serve_file(request, path, content_type, "no-store")
}

/// Serve only the exact bytes named by a versioned URL. Hash through the same
/// open handle that is sent to the client so a concurrent replacement cannot
/// put changed bytes behind an already-immutable cache key.
pub(super) fn send_audio(request: Request, path: &Path, expected_version: &str) -> Result<()> {
    let Ok(mut file) = File::open(path) else {
        return send_json(
            request,
            StatusCode(404),
            &json!({"error": "audio not found"}),
        );
    };
    let metadata = file.metadata()?;
    if !metadata.is_file() {
        return send_json(
            request,
            StatusCode(404),
            &json!({"error": "audio not found"}),
        );
    }

    let actual_version = sha256_open_file(&mut file)?;
    if actual_version != expected_version {
        return send_json(
            request,
            StatusCode(404),
            &json!({"error": "audio version not found"}),
        );
    }
    file.seek(SeekFrom::Start(0))?;
    let headers = vec![
        header("Cache-Control", VERSIONED_AUDIO_CACHE_CONTROL),
        header("Content-Type", "audio/mpeg"),
        header("Content-Length", &metadata.len().to_string()),
    ];

    if request.method() == &Method::Head {
        request.respond(add_headers(Response::empty(StatusCode(200)), headers))?;
    } else {
        request.respond(add_headers(
            Response::from_file(file).with_status_code(StatusCode(200)),
            headers,
        ))?;
    }
    Ok(())
}

/// Old links remain valid without reusing their cache key for changed bytes.
/// Browsers and native players follow this redirect to the hash-versioned URL.
pub(super) fn redirect_to_versioned_audio(request: Request, location: &str) -> Result<()> {
    request.respond(add_headers(
        Response::empty(StatusCode(307)),
        vec![
            header("Location", location),
            header("Cache-Control", LEGACY_AUDIO_REDIRECT_CACHE_CONTROL),
        ],
    ))?;
    Ok(())
}

fn serve_file(
    request: Request,
    path: &Path,
    content_type: &str,
    cache_control: &str,
) -> Result<()> {
    if !path.exists() || !path.is_file() {
        return send_json(request, StatusCode(404), &json!({"error": "not found"}));
    }
    let ctype = if content_type.is_empty() {
        // Let mime_guess handle static assets where the type is obvious from
        // the extension. send_audio passes an explicit content type above.
        mime_guess::from_path(path)
            .first_or_octet_stream()
            .essence_str()
            .to_string()
    } else {
        content_type.to_string()
    };
    let file_size = path.metadata()?.len();
    let headers = vec![
        header("Cache-Control", cache_control),
        header("Content-Type", &ctype),
        header("Content-Length", &file_size.to_string()),
    ];

    if request.method() == &Method::Head {
        request.respond(add_headers(Response::empty(StatusCode(200)), headers))?;
    } else {
        request.respond(add_headers(
            Response::from_file(File::open(path)?).with_status_code(StatusCode(200)),
            headers,
        ))?;
    }
    Ok(())
}

fn sha256_open_file(file: &mut File) -> Result<String> {
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 32 * 1024];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
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

pub(super) fn header(name: &str, value: &str) -> Header {
    Header::from_bytes(name.as_bytes(), value.as_bytes()).expect("static header should be valid")
}

#[cfg(test)]
mod tests {
    use super::{
        LEGACY_AUDIO_REDIRECT_CACHE_CONTROL, VERSIONED_AUDIO_CACHE_CONTROL, static_asset_path,
    };
    use std::path::Path;

    #[test]
    fn static_asset_path_allows_current_static_files_and_react_assets() {
        let root = Path::new("static");
        assert_eq!(
            static_asset_path(root, "/favicon.svg").as_deref(),
            Some(Path::new("static/favicon.svg"))
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
    fn static_asset_path_rejects_removed_assets_and_invalid_react_paths() {
        let root = Path::new("static");
        assert!(static_asset_path(root, "/styles.css").is_none());
        assert!(static_asset_path(root, "/app.js").is_none());
        assert!(static_asset_path(root, "/js/main.js").is_none());
        assert!(static_asset_path(root, "/api/summary").is_none());
        assert!(static_asset_path(root, "/study-wall-react/assets/../index.js").is_none());
        assert!(static_asset_path(root, "/study-wall-react/assets/index.html").is_none());
    }

    #[test]
    fn audio_cache_contract_separates_versioned_and_legacy_urls() {
        assert_eq!(
            VERSIONED_AUDIO_CACHE_CONTROL,
            "public, max-age=31536000, immutable"
        );
        assert_eq!(LEGACY_AUDIO_REDIRECT_CACHE_CONTROL, "no-store");
    }
}
