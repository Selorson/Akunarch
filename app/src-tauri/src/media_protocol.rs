use crate::cowriter_bridge::{concepts_dir, cowriter_data_dir};
use crate::db::akunarch_projects_root;
use base64::Engine;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};
use tauri::http::{header, Request, Response, StatusCode};

const ALLOWED_MEDIA_EXTS: &[&str] = &[
    "jpg", "jpeg", "png", "webp", "gif", "svg", "glb", "gltf", "bin", "spz", "splat", "ply",
    "obj", "mp4", "webm", "ogg", "wav", "mp3", "flac", "m4a", "aac", "opus", "hdr", "exr", "ktx2",
    "zip", "srt", "vtt",
];

fn allowed_media_roots() -> Vec<PathBuf> {
    let cw = cowriter_data_dir();
    vec![
        cw.join("sketches"),
        cw.join("manga"),
        concepts_dir(),
        PathBuf::from(r"E:\Tools-3D\polyhaven"),
        PathBuf::from(r"E:\Tools-3D\ai_meshes"),
        akunarch_projects_root(),
    ]
}

fn is_allowed_media_extension(path: &Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_ascii_lowercase())
        .is_some_and(|ext| ALLOWED_MEDIA_EXTS.contains(&ext.as_str()))
}

fn canonical_within_root(file: &Path, root: &Path) -> bool {
    let mut file_comps = file.components();
    for root_comp in root.components() {
        let Some(fc) = file_comps.next() else {
            return false;
        };
        #[cfg(windows)]
        {
            let a = fc.as_os_str().to_string_lossy();
            let b = root_comp.as_os_str().to_string_lossy();
            if !a.eq_ignore_ascii_case(&b) {
                return false;
            }
        }
        #[cfg(not(windows))]
        {
            if fc != root_comp {
                return false;
            }
        }
    }
    true
}

/// Strictly verifies that `raw_path` exists as a regular media file with an allowlisted extension
/// inside one of Akunarch's allowlisted media roots (preventing arbitrary file read, `.db`/`.exe`
/// exfiltration, or path traversal).
pub fn resolve_allowed_media_file(raw_path: &str) -> Result<PathBuf, String> {
    let trimmed = raw_path.trim();
    if trimmed.is_empty() {
        return Err("Đường dẫn media trống.".to_string());
    }
    let canonical = std::fs::canonicalize(trimmed)
        .map_err(|e| format!("Không tìm thấy tệp media '{trimmed}': {e}"))?;
    if !canonical.is_file() {
        return Err("Đường dẫn không phải là tệp hợp lệ.".to_string());
    }
    if !is_allowed_media_extension(&canonical) {
        return Err(format!(
            "Từ chối truy cập định dạng tệp không phải media 2D/3D/Audio/Video: {}",
            canonical.display()
        ));
    }

    for root in allowed_media_roots() {
        if let Ok(canon_root) = std::fs::canonicalize(&root) {
            if canonical_within_root(&canonical, &canon_root) {
                return Ok(canonical);
            }
        }
    }

    Err(format!(
        "Từ chối truy cập tệp nằm ngoài danh sách thư mục media cho phép: {}",
        canonical.display()
    ))
}

pub fn mime_for_path(path: &Path) -> &'static str {
    match path
        .extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_ascii_lowercase())
        .as_deref()
    {
        Some("jpg") | Some("jpeg") => "image/jpeg",
        Some("png") => "image/png",
        Some("webp") => "image/webp",
        Some("gif") => "image/gif",
        Some("svg") => "image/svg+xml",
        Some("glb") => "model/gltf-binary",
        Some("gltf") => "model/gltf+json",
        Some("mp4") => "video/mp4",
        Some("webm") => "video/webm",
        Some("ogg") => "audio/ogg",
        Some("mp3") => "audio/mpeg",
        Some("wav") => "audio/wav",
        Some("flac") => "audio/flac",
        Some("m4a") => "audio/mp4",
        Some("aac") => "audio/aac",
        Some("opus") => "audio/opus",
        Some("hdr") => "image/vnd.radiance",
        Some("exr") => "image/x-exr",
        Some("ktx2") => "image/ktx2",
        Some("zip") => "application/zip",
        Some("json") => "application/json; charset=utf-8",
        Some("srt") => "application/x-subrip; charset=utf-8",
        Some("vtt") => "text/vtt; charset=utf-8",
        _ => "application/octet-stream",
    }
}

fn allowed_cors_origin<B>(req: &Request<B>) -> &'static str {
    let origin = req
        .headers()
        .get(header::ORIGIN)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    match origin {
        "http://tauri.localhost" => "http://tauri.localhost",
        "https://tauri.localhost" => "https://tauri.localhost",
        "tauri://localhost" => "tauri://localhost",
        "http://localhost:5190" => "http://localhost:5190",
        "http://127.0.0.1:5190" => "http://127.0.0.1:5190",
        _ => "http://tauri.localhost",
    }
}

/// Parses a single HTTP `Range: bytes=...` header into inclusive `(start, end)` bounds.
pub fn parse_http_byte_range(range_header: &str, total_len: u64) -> Option<(u64, u64)> {
    if total_len == 0 {
        return None;
    }
    let spec = range_header.trim().strip_prefix("bytes=")?;
    let first_range = spec.split(',').next()?.trim();
    let (start_s, end_s) = first_range.split_once('-')?;
    let start_s = start_s.trim();
    let end_s = end_s.trim();

    if start_s.is_empty() {
        // Suffix byte-range-spec: `bytes=-500`
        let suffix_len = end_s.parse::<u64>().ok()?;
        if suffix_len == 0 {
            return None;
        }
        let start = total_len.saturating_sub(suffix_len);
        Some((start, total_len - 1))
    } else {
        let start = start_s.parse::<u64>().ok()?;
        if start >= total_len {
            return None;
        }
        let end = if end_s.is_empty() {
            total_len - 1
        } else {
            let parsed_end = end_s.parse::<u64>().ok()?;
            if parsed_end < start {
                return None;
            }
            parsed_end.min(total_len - 1)
        };
        Some((start, end))
    }
}

pub fn handle_akunmedia_request(req: Request<Vec<u8>>) -> Response<Vec<u8>> {
    let cors_origin = allowed_cors_origin(&req);
    let uri = req.uri();
    let query = uri.query().unwrap_or("");
    let mut target_path = String::new();
    for pair in query.split('&') {
        if let Some(val) = pair.strip_prefix("path=") {
            if let Ok(decoded) = urlencoding::decode(val) {
                target_path = decoded.into_owned();
                break;
            }
        }
    }

    if target_path.is_empty() {
        return Response::builder()
            .status(StatusCode::BAD_REQUEST)
            .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, cors_origin)
            .body(b"Missing ?path= parameter".to_vec())
            .unwrap();
    }

    let range_hdr = req
        .headers()
        .get(header::RANGE)
        .and_then(|v| v.to_str().ok())
        .map(str::to_string);

    match resolve_allowed_media_file(&target_path) {
        Ok(canon_file) => {
            let mime = mime_for_path(&canon_file);
            let mut file = match std::fs::File::open(&canon_file) {
                Ok(f) => f,
                Err(e) => {
                    return Response::builder()
                        .status(StatusCode::INTERNAL_SERVER_ERROR)
                        .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, cors_origin)
                        .body(format!("Open error: {e}").into_bytes())
                        .unwrap();
                }
            };
            let total_len = match file.metadata() {
                Ok(m) => m.len(),
                Err(e) => {
                    return Response::builder()
                        .status(StatusCode::INTERNAL_SERVER_ERROR)
                        .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, cors_origin)
                        .body(format!("Metadata error: {e}").into_bytes())
                        .unwrap();
                }
            };

            if let Some(raw_range) = range_hdr {
                if let Some((start, end)) = parse_http_byte_range(&raw_range, total_len) {
                    let chunk_len = (end - start + 1) as usize;
                    if file.seek(SeekFrom::Start(start)).is_err() {
                        return Response::builder()
                            .status(StatusCode::INTERNAL_SERVER_ERROR)
                            .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, cors_origin)
                            .body(b"Seek error".to_vec())
                            .unwrap();
                    }
                    let mut buf = Vec::with_capacity(chunk_len);
                    if file.take(chunk_len as u64).read_to_end(&mut buf).is_err() {
                        return Response::builder()
                            .status(StatusCode::INTERNAL_SERVER_ERROR)
                            .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, cors_origin)
                            .body(b"Read range error".to_vec())
                            .unwrap();
                    }
                    return Response::builder()
                        .status(StatusCode::PARTIAL_CONTENT)
                        .header(header::CONTENT_TYPE, mime)
                        .header(header::ACCEPT_RANGES, "bytes")
                        .header(
                            header::CONTENT_RANGE,
                            format!("bytes {start}-{end}/{total_len}"),
                        )
                        .header(header::CONTENT_LENGTH, buf.len().to_string())
                        .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, cors_origin)
                        .body(buf)
                        .unwrap();
                } else {
                    return Response::builder()
                        .status(StatusCode::RANGE_NOT_SATISFIABLE)
                        .header(header::ACCEPT_RANGES, "bytes")
                        .header(header::CONTENT_RANGE, format!("bytes */{total_len}"))
                        .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, cors_origin)
                        .body(Vec::new())
                        .unwrap();
                }
            }

            let mut bytes = Vec::with_capacity(total_len as usize);
            match file.read_to_end(&mut bytes) {
                Ok(_) => Response::builder()
                    .status(StatusCode::OK)
                    .header(header::CONTENT_TYPE, mime)
                    .header(header::ACCEPT_RANGES, "bytes")
                    .header(header::CONTENT_LENGTH, bytes.len().to_string())
                    .header(header::CACHE_CONTROL, "public, max-age=3600")
                    .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, cors_origin)
                    .body(bytes)
                    .unwrap(),
                Err(e) => Response::builder()
                    .status(StatusCode::INTERNAL_SERVER_ERROR)
                    .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, cors_origin)
                    .body(format!("Read error: {e}").into_bytes())
                    .unwrap(),
            }
        }
        Err(err) => Response::builder()
            .status(StatusCode::FORBIDDEN)
            .header(header::ACCESS_CONTROL_ALLOW_ORIGIN, cors_origin)
            .body(err.into_bytes())
            .unwrap(),
    }
}

/// Fallback helper returning a `data:image/...;base64,...` URI when running UI in standalone Vite browser mode.
pub fn read_media_data_uri(raw_path: &str) -> Result<String, String> {
    let canon = resolve_allowed_media_file(raw_path)?;
    let bytes = std::fs::read(&canon).map_err(|e| format!("Lỗi đọc tệp ảnh: {e}"))?;
    let mime = mime_for_path(&canon);
    let b64 = base64::engine::general_purpose::STANDARD.encode(&bytes);
    Ok(format!("data:{mime};base64,{b64}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::{akunarch_db_path, open_akunarch_db};

    #[test]
    fn media_allowlist_blocks_system_files_db_and_json_and_serves_unicode_plus_range() {
        // 1. Arbitrary system file must fail
        let forbidden = resolve_allowed_media_file(r"C:\Windows\win.ini");
        assert!(
            forbidden.is_err(),
            "system file outside allowlist must be blocked"
        );

        // 2. akunarch.db inside %LOCALAPPDATA%\Akunarch MUST be blocked (protects admin JWTs!)
        let _ = open_akunarch_db();
        let db_file = akunarch_db_path();
        if db_file.is_file() {
            let db_attempt = resolve_allowed_media_file(&db_file.to_string_lossy());
            assert!(
                db_attempt.is_err(),
                "akunarch.db must NEVER be readable via akunmedia protocol!"
            );
        }

        // 3. Allowed concept image works
        let sample_concept = r"E:\Tools-3D\concepts\concept_eldarin_lifestream_tree.jpg";
        if Path::new(sample_concept).is_file() {
            let allowed = resolve_allowed_media_file(sample_concept);
            assert!(allowed.is_ok(), "concept file must be allowed");
        }

        // 4. Unicode Vietnamese + `+`, `&`, `#` characters in project media path + HTTP 206 Range
        let proj_root = akunarch_projects_root();
        let test_dir = proj_root.join("_test_media_edge");
        std::fs::create_dir_all(&test_dir).unwrap();

        let non_media_json = test_dir.join("project.akun.json");
        std::fs::write(&non_media_json, b"{}").unwrap();
        assert!(
            resolve_allowed_media_file(&non_media_json.to_string_lossy()).is_err(),
            "non-media .json must be blocked by extension allowlist"
        );

        let tricky_file = test_dir.join("Đền_Ngũ_Giác+v1&2#preview.mp4");
        let payload = b"0123456789ABCDEF_AKUNARCH_MP4";
        std::fs::write(&tricky_file, payload).unwrap();

        let encoded = urlencoding::encode(&tricky_file.to_string_lossy()).into_owned();
        let uri = format!("http://akunmedia.localhost/file?path={encoded}");

        // Full 200 OK request
        let req_full = Request::builder()
            .uri(&uri)
            .header(header::ORIGIN, "http://evil.example")
            .body(Vec::new())
            .unwrap();
        let resp_full = handle_akunmedia_request(req_full);
        assert_eq!(resp_full.status(), StatusCode::OK);
        assert_eq!(resp_full.body().as_slice(), payload);
        assert_eq!(
            resp_full
                .headers()
                .get(header::ACCESS_CONTROL_ALLOW_ORIGIN)
                .unwrap(),
            "http://tauri.localhost",
            "CORS must never reflect untrusted origins or '*'"
        );

        // Byte-range 206 Partial Content request
        let req_range = Request::builder()
            .uri(&uri)
            .header(header::RANGE, "bytes=4-9")
            .body(Vec::new())
            .unwrap();
        let resp_range = handle_akunmedia_request(req_range);
        assert_eq!(resp_range.status(), StatusCode::PARTIAL_CONTENT);
        assert_eq!(resp_range.body().as_slice(), b"456789");
        assert_eq!(
            resp_range
                .headers()
                .get(header::CONTENT_RANGE)
                .unwrap()
                .to_str()
                .unwrap(),
            format!("bytes 4-9/{}", payload.len())
        );

        // Out-of-bounds range -> 416
        let req_bad_range = Request::builder()
            .uri(&uri)
            .header(header::RANGE, "bytes=9999-10000")
            .body(Vec::new())
            .unwrap();
        let resp_bad_range = handle_akunmedia_request(req_bad_range);
        assert_eq!(resp_bad_range.status(), StatusCode::RANGE_NOT_SATISFIABLE);

        let _ = std::fs::remove_dir_all(&test_dir);
    }
}
