//! Windows-friendly process launcher for the local WordService.
//!
//! The web service remains a separate process. This module only coordinates
//! the user-facing workflow: reuse a ready local service, start the compiled
//! service when necessary, wait for an actual HTTP response, and open the
//! default browser. Keeping those responsibilities here makes the startup
//! contract visible without adding desktop-app behavior to the HTTP server.

use anyhow::{Context, Result, bail};
use std::env;
use std::fs::OpenOptions;
use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

const DEFAULT_HOST: &str = "127.0.0.1";
const DEFAULT_PORT: u16 = 8767;
const DEFAULT_READY_TIMEOUT_SECONDS: u64 = 30;
const READY_POLL_INTERVAL: Duration = Duration::from_millis(200);
const SERVICE_EXECUTABLE_NAME: &str = "n2-word-service-rust.exe";
const START_PAGE: &str = "/";

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

/// The address used both for the readiness probe and for the browser URL.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ServiceEndpoint {
    pub host: String,
    pub port: u16,
}

impl ServiceEndpoint {
    pub fn from_environment() -> Result<Self> {
        let host = env::var("N2_WORD_SERVICE_HOST").unwrap_or_else(|_| DEFAULT_HOST.to_string());
        let port = env::var("N2_WORD_SERVICE_PORT")
            .unwrap_or_else(|_| DEFAULT_PORT.to_string())
            .parse::<u16>()
            .context("N2_WORD_SERVICE_PORT must be an integer from 0 to 65535")?;

        // A server may bind to all interfaces, but a browser should connect
        // through loopback. This keeps the launcher local even if the service
        // is configured with N2_WORD_SERVICE_HOST=0.0.0.0 or ::.
        let browser_host = match host.as_str() {
            "0.0.0.0" | "::" | "[::]" => DEFAULT_HOST.to_string(),
            _ => host,
        };

        Ok(Self {
            host: browser_host,
            port,
        })
    }

    pub fn browser_url(&self) -> String {
        format!(
            "http://{}:{}{}",
            format_host(&self.host),
            self.port,
            START_PAGE
        )
    }

    fn socket_address(&self) -> String {
        format!("{}:{}", format_host(&self.host), self.port)
    }
}

/// All paths and timing used by one launcher run.
#[derive(Clone, Debug)]
pub struct LauncherConfig {
    pub service_executable: PathBuf,
    pub service_working_directory: PathBuf,
    pub endpoint: ServiceEndpoint,
    pub ready_timeout: Duration,
    pub poll_interval: Duration,
    pub log_path: PathBuf,
}

impl LauncherConfig {
    pub fn from_current_executable(current_executable: &Path) -> Result<Self> {
        let service_executable = find_service_executable(current_executable)?;
        let service_working_directory = service_executable
            .parent()
            .map(Path::to_path_buf)
            .unwrap_or_else(|| PathBuf::from("."));
        let launcher_directory = current_executable
            .parent()
            .map(Path::to_path_buf)
            .unwrap_or_else(|| PathBuf::from("."));
        let timeout_seconds = env::var("N2_WORD_SERVICE_START_TIMEOUT_SECONDS")
            .unwrap_or_else(|_| DEFAULT_READY_TIMEOUT_SECONDS.to_string())
            .parse::<u64>()
            .context("N2_WORD_SERVICE_START_TIMEOUT_SECONDS must be a positive integer")?;
        if timeout_seconds == 0 {
            bail!("N2_WORD_SERVICE_START_TIMEOUT_SECONDS must be greater than zero");
        }

        Ok(Self {
            service_executable,
            service_working_directory,
            endpoint: ServiceEndpoint::from_environment()?,
            ready_timeout: Duration::from_secs(timeout_seconds),
            poll_interval: READY_POLL_INTERVAL,
            log_path: launcher_directory.join("n2-word-service-launcher.log"),
        })
    }
}

/// Run the one-click workflow used by `Start N2 Vocabulary.exe`.
pub fn run() -> Result<()> {
    let current_executable = env::current_exe().context("find the launcher executable path")?;
    let config = LauncherConfig::from_current_executable(&current_executable)?;

    println!("N2 Vocabulary launcher");
    println!("  service: {}", config.service_executable.display());
    println!("  browser: {}", config.endpoint.browser_url());

    // If the port is already open, wait for that process instead of starting
    // a second server. A second server would fail to bind and would make a
    // normal double-click look like a startup failure.
    if port_is_open(&config.endpoint, Duration::from_millis(300)) {
        println!(
            "An existing process is using {}. Waiting for WordService...",
            config.endpoint.socket_address()
        );
        wait_for_service(
            &config.endpoint,
            config.ready_timeout,
            config.poll_interval,
            None,
        )
        .with_context(|| {
            format!(
                "the existing process at {} did not become WordService-ready",
                config.endpoint.socket_address()
            )
        })?;
    } else {
        println!("Starting WordService...");
        let mut child = spawn_service(&config)?;
        if let Err(error) = wait_for_service(
            &config.endpoint,
            config.ready_timeout,
            config.poll_interval,
            Some(&mut child),
        ) {
            stop_child(&mut child);
            return Err(error).with_context(|| {
                format!(
                    "WordService did not become ready; inspect {}",
                    config.log_path.display()
                )
            });
        }
        // Dropping the handle does not terminate the Windows child process.
        // WordService intentionally stays alive so later clicks can reuse it.
        drop(child);
    }

    open_browser(&config.endpoint.browser_url())
        .context("open the React study wall in the default browser")?;
    println!("Browser opened.");
    Ok(())
}

/// Find the service executable in both the repository build layout and the
/// simple local distribution layout used by the build script.
pub fn find_service_executable(launcher_executable: &Path) -> Result<PathBuf> {
    if let Some(configured_path) = env::var_os("N2_WORD_SERVICE_EXECUTABLE") {
        let configured_path = PathBuf::from(configured_path);
        let resolved_path = if configured_path.is_absolute() {
            configured_path
        } else {
            launcher_executable
                .parent()
                .unwrap_or_else(|| Path::new("."))
                .join(configured_path)
        };
        if resolved_path.is_file() {
            return Ok(resolved_path);
        }
        bail!(
            "N2_WORD_SERVICE_EXECUTABLE points to a missing file: {}",
            resolved_path.display()
        );
    }

    let candidates = service_executable_candidates(launcher_executable);
    if let Some(path) = candidates.iter().find(|candidate| candidate.is_file()) {
        return Ok(path.clone());
    }

    let searched = candidates
        .iter()
        .map(|path| format!("  - {}", path.display()))
        .collect::<Vec<_>>()
        .join("\n");
    bail!(
        "could not find {SERVICE_EXECUTABLE_NAME}. Build the service first or set N2_WORD_SERVICE_EXECUTABLE. Searched:\n{searched}"
    );
}

pub fn service_executable_candidates(launcher_executable: &Path) -> Vec<PathBuf> {
    let launcher_directory = launcher_executable
        .parent()
        .unwrap_or_else(|| Path::new("."));
    let manifest_directory = Path::new(env!("CARGO_MANIFEST_DIR"));
    let roots = [
        launcher_directory.to_path_buf(),
        launcher_directory.join("wordService"),
        launcher_directory
            .join("wordService")
            .join("target")
            .join("launcher-release")
            .join("release"),
        launcher_directory
            .join("wordService")
            .join("target")
            .join("release"),
        launcher_directory.join("target").join("release"),
        manifest_directory
            .join("target")
            .join("launcher-release")
            .join("release"),
        manifest_directory.join("target").join("release"),
        manifest_directory.join("target").join("debug"),
    ];

    let mut candidates = Vec::new();
    for root in roots {
        let candidate = root.join(SERVICE_EXECUTABLE_NAME);
        if !candidates.contains(&candidate) {
            candidates.push(candidate);
        }
    }
    candidates
}

/// Return true when a process has bound the configured TCP port.
pub fn port_is_open(endpoint: &ServiceEndpoint, timeout: Duration) -> bool {
    resolve_socket_address(endpoint)
        .and_then(|address| TcpStream::connect_timeout(&address, timeout).map_err(Into::into))
        .is_ok()
}

/// Probe a non-mutating HTTP endpoint that requires the backend and database
/// to be initialized. A TCP connection alone is not enough: the process may
/// have opened its socket while it is still preparing SQLite and TTS state.
pub fn probe_http_ready(endpoint: &ServiceEndpoint, timeout: Duration) -> Result<()> {
    let address = resolve_socket_address(endpoint)?;
    let mut stream = TcpStream::connect_timeout(&address, timeout)
        .with_context(|| format!("connect to {}", endpoint.socket_address()))?;
    stream
        .set_read_timeout(Some(timeout))
        .context("set readiness probe read timeout")?;
    stream
        .set_write_timeout(Some(timeout))
        .context("set readiness probe write timeout")?;
    let request = format!(
        "HEAD /api/summary HTTP/1.1\r\nHost: {}\r\nConnection: close\r\n\r\n",
        endpoint.host
    );
    stream
        .write_all(request.as_bytes())
        .context("send readiness probe")?;

    let mut response = Vec::with_capacity(1024);
    let mut buffer = [0_u8; 512];
    loop {
        let bytes_read = stream
            .read(&mut buffer)
            .context("read readiness response")?;
        if bytes_read == 0 {
            break;
        }
        response.extend_from_slice(&buffer[..bytes_read]);
        if response.windows(4).any(|window| window == b"\r\n\r\n") {
            break;
        }
        if response.len() > 16 * 1024 {
            bail!("readiness response headers exceeded 16 KiB");
        }
    }

    let headers = String::from_utf8_lossy(&response);
    let status_line = headers
        .lines()
        .next()
        .ok_or_else(|| anyhow::anyhow!("readiness probe returned no HTTP status line"))?;
    let status_code = status_line
        .split_whitespace()
        .nth(1)
        .ok_or_else(|| anyhow::anyhow!("invalid HTTP status line: {status_line}"))?;
    if status_code != "200" {
        bail!("readiness probe returned HTTP {status_code}");
    }
    Ok(())
}

/// Wait until the service answers successfully, optionally detecting an early
/// child-process exit so a broken binary fails immediately instead of waiting
/// for the full timeout.
pub fn wait_for_service(
    endpoint: &ServiceEndpoint,
    timeout: Duration,
    poll_interval: Duration,
    mut child: Option<&mut Child>,
) -> Result<()> {
    let started_at = Instant::now();
    let probe_timeout = poll_interval.max(Duration::from_millis(250));
    let mut last_error;

    loop {
        match probe_http_ready(endpoint, probe_timeout) {
            Ok(()) => return Ok(()),
            Err(error) => last_error = error.to_string(),
        }

        if let Some(service_child) = child.as_deref_mut()
            && let Some(status) = service_child
                .try_wait()
                .context("check whether WordService exited")?
        {
            bail!("WordService exited before becoming ready ({status}); last probe: {last_error}");
        }

        if started_at.elapsed() >= timeout {
            bail!(
                "WordService did not become ready at {} within {} seconds; last probe: {}",
                endpoint.socket_address(),
                timeout.as_secs(),
                last_error
            );
        }
        thread::sleep(poll_interval);
    }
}

fn spawn_service(config: &LauncherConfig) -> Result<Child> {
    let stdout = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&config.log_path)
        .with_context(|| format!("open launcher log {}", config.log_path.display()))?;
    let stderr = stdout
        .try_clone()
        .context("duplicate launcher log handle for stderr")?;

    let mut command = Command::new(&config.service_executable);
    command
        .current_dir(&config.service_working_directory)
        .stdin(Stdio::null())
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr));
    #[cfg(windows)]
    command.creation_flags(CREATE_NO_WINDOW);

    command.spawn().with_context(|| {
        format!(
            "start WordService executable {}",
            config.service_executable.display()
        )
    })
}

fn stop_child(child: &mut Child) {
    if child.try_wait().ok().flatten().is_none() {
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn resolve_socket_address(endpoint: &ServiceEndpoint) -> Result<std::net::SocketAddr> {
    endpoint
        .socket_address()
        .to_socket_addrs()
        .context("resolve WordService socket address")?
        .next()
        .ok_or_else(|| anyhow::anyhow!("WordService socket address resolved to no addresses"))
}

fn format_host(host: &str) -> String {
    if host.contains(':') && !host.starts_with('[') {
        format!("[{host}]")
    } else {
        host.to_string()
    }
}

fn open_browser(url: &str) -> Result<()> {
    #[cfg(windows)]
    {
        let mut command = Command::new("cmd.exe");
        command.args(["/C", "start", "", url]);
        command.creation_flags(CREATE_NO_WINDOW);
        command
            .spawn()
            .context("run Windows default-browser handler")?;
        Ok(())
    }

    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg(url)
            .spawn()
            .context("run macOS default-browser handler")?;
        return Ok(());
    }

    #[cfg(all(unix, not(target_os = "macos")))]
    {
        Command::new("xdg-open")
            .arg(url)
            .spawn()
            .context("run Linux default-browser handler")?;
        return Ok(());
    }

    #[cfg(not(any(windows, target_os = "macos", unix)))]
    {
        bail!("opening the default browser is unsupported on this platform")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    fn endpoint_for(listener: &TcpListener) -> ServiceEndpoint {
        ServiceEndpoint {
            host: DEFAULT_HOST.to_string(),
            port: listener.local_addr().unwrap().port(),
        }
    }

    #[test]
    fn browser_url_points_to_the_react_root() {
        let endpoint = ServiceEndpoint {
            host: DEFAULT_HOST.to_string(),
            port: DEFAULT_PORT,
        };
        assert_eq!(endpoint.browser_url(), "http://127.0.0.1:8767/");
    }

    #[test]
    fn candidate_paths_include_repository_and_distribution_layouts() {
        let launcher = Path::new(r"D:\N2Vocabulary\Start N2 Vocabulary.exe");
        let candidates = service_executable_candidates(launcher);
        assert!(candidates.iter().any(|path| {
            path == Path::new(
                r"D:\N2Vocabulary\wordService\target\release\n2-word-service-rust.exe",
            )
        }));
        assert!(candidates.iter().any(|path| {
            path == Path::new(r"D:\N2Vocabulary\wordService\n2-word-service-rust.exe")
        }));
        let launcher_release = candidates
            .iter()
            .position(|path| {
                path == Path::new(
                    r"D:\N2Vocabulary\wordService\target\launcher-release\release\n2-word-service-rust.exe",
                )
            })
            .unwrap();
        let normal_release = candidates
            .iter()
            .position(|path| {
                path == Path::new(
                    r"D:\N2Vocabulary\wordService\target\release\n2-word-service-rust.exe",
                )
            })
            .unwrap();
        assert!(launcher_release < normal_release);
    }

    #[test]
    fn wait_for_service_reuses_an_existing_http_service() {
        let listener = TcpListener::bind((DEFAULT_HOST, 0)).unwrap();
        let endpoint = endpoint_for(&listener);
        let worker = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut request = [0_u8; 512];
            let _ = stream.read(&mut request);
            stream
                .write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n")
                .unwrap();
        });

        wait_for_service(
            &endpoint,
            Duration::from_secs(2),
            Duration::from_millis(10),
            None,
        )
        .unwrap();
        worker.join().unwrap();
    }

    #[test]
    fn readiness_probe_rejects_non_success_http_status() {
        let listener = TcpListener::bind((DEFAULT_HOST, 0)).unwrap();
        let endpoint = endpoint_for(&listener);
        let worker = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut request = [0_u8; 512];
            let _ = stream.read(&mut request);
            stream
                .write_all(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n")
                .unwrap();
        });

        let error = probe_http_ready(&endpoint, Duration::from_secs(1)).unwrap_err();
        assert!(error.to_string().contains("HTTP 503"));
        worker.join().unwrap();
    }
}
