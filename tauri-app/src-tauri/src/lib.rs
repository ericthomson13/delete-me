use std::sync::Arc;
use std::time::Duration;

use anyhow::{anyhow, Result};
use once_cell::sync::OnceCell;
use tauri::{RunEvent, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tokio::sync::Mutex;
use tokio::sync::oneshot;
use tokio::time::timeout;

/// Parses a single stdout line from the Python sidecar. Returns the
/// `http://host:port` base URL if the line is the readiness signal
/// (`LISTENING_ON 127.0.0.1:54321`), otherwise `None`.
///
/// Kept pure (and free of tauri/tokio deps) so it's unit-testable.
fn parse_listening_line(line: &str) -> Option<String> {
    let trimmed = line.trim();
    let addr = trimmed.strip_prefix("LISTENING_ON ")?.trim();
    if addr.is_empty() {
        return None;
    }
    // Reject anything that doesn't look like host:port — we don't want to
    // build a malformed URL and chase a connect error later.
    let (_, port) = addr.rsplit_once(':')?;
    if port.is_empty() || !port.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }
    Some(format!("http://{addr}"))
}

// Holds the live sidecar handle so we can kill it on app exit.
struct SidecarState {
    child: Mutex<Option<CommandChild>>,
    api_base: OnceCell<String>,
}

#[tauri::command]
fn get_api_base(state: State<'_, Arc<SidecarState>>) -> Result<String, String> {
    state
        .api_base
        .get()
        .cloned()
        .ok_or_else(|| "sidecar has not advertised a listen address yet".to_string())
}

async fn spawn_sidecar(app: &tauri::AppHandle, state: Arc<SidecarState>) -> Result<()> {
    // `delete-me-sidecar` is the externalBin declared in tauri.conf.json. The
    // shell plugin resolves it to the target-triple-suffixed binary that lives
    // beside the app bundle (or in src-tauri/binaries/ during dev).
    let cmd = app
        .shell()
        .sidecar("delete-me-sidecar")
        .map_err(|e| anyhow!("resolve sidecar: {e}"))?;

    let (mut rx, child) = cmd.spawn().map_err(|e| anyhow!("spawn sidecar: {e}"))?;
    *state.child.lock().await = Some(child);

    // The sidecar prints `LISTENING_ON 127.0.0.1:PORT` to stdout once uvicorn
    // is ready. We block app startup on receiving that line (with a timeout)
    // so the UI never tries to fetch before the server is up.
    let (tx, ready_rx) = oneshot::channel::<String>();
    let state_for_reader = state.clone();
    let mut tx_slot = Some(tx);

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    let line = String::from_utf8_lossy(&line).to_string();
                    log::info!("sidecar stdout: {line}");
                    if let Some(base) = parse_listening_line(&line) {
                        let _ = state_for_reader.api_base.set(base.clone());
                        if let Some(tx) = tx_slot.take() {
                            let _ = tx.send(base);
                        }
                    }
                }
                CommandEvent::Stderr(line) => {
                    log::warn!("sidecar stderr: {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Terminated(payload) => {
                    log::error!("sidecar terminated: code={:?}", payload.code);
                    break;
                }
                _ => {}
            }
        }
    });

    match timeout(Duration::from_secs(20), ready_rx).await {
        Ok(Ok(base)) => {
            log::info!("sidecar ready at {base}");
            Ok(())
        }
        Ok(Err(_)) => Err(anyhow!("sidecar exited before advertising a port")),
        Err(_) => Err(anyhow!("sidecar did not advertise a port within 20s")),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let state = Arc::new(SidecarState {
        child: Mutex::new(None),
        api_base: OnceCell::new(),
    });
    let state_for_setup = state.clone();
    let state_for_exit = state.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(state.clone())
        .invoke_handler(tauri::generate_handler![get_api_base])
        .setup(move |app| {
            let app_handle = app.handle().clone();
            let state = state_for_setup.clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = spawn_sidecar(&app_handle, state).await {
                    log::error!("failed to start sidecar: {e:#}");
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(move |_app, event| {
            if let RunEvent::ExitRequested { .. } = event {
                let state = state_for_exit.clone();
                tauri::async_runtime::block_on(async move {
                    if let Some(child) = state.child.lock().await.take() {
                        let _ = child.kill();
                    }
                });
            }
        });
}

#[cfg(test)]
mod tests {
    use super::parse_listening_line;

    #[test]
    fn parses_loopback_port() {
        assert_eq!(
            parse_listening_line("LISTENING_ON 127.0.0.1:54321"),
            Some("http://127.0.0.1:54321".into())
        );
    }

    #[test]
    fn tolerates_trailing_newline() {
        assert_eq!(
            parse_listening_line("LISTENING_ON 127.0.0.1:8080\n"),
            Some("http://127.0.0.1:8080".into())
        );
    }

    #[test]
    fn rejects_non_handshake_lines() {
        assert_eq!(parse_listening_line("INFO: uvicorn running"), None);
        assert_eq!(parse_listening_line(""), None);
        assert_eq!(parse_listening_line("LISTENING_ON"), None);
        assert_eq!(parse_listening_line("LISTENING_ON "), None);
    }

    #[test]
    fn rejects_malformed_address() {
        // No port at all.
        assert_eq!(parse_listening_line("LISTENING_ON 127.0.0.1"), None);
        // Non-numeric port.
        assert_eq!(parse_listening_line("LISTENING_ON 127.0.0.1:abc"), None);
        // Empty port.
        assert_eq!(parse_listening_line("LISTENING_ON 127.0.0.1:"), None);
    }
}
