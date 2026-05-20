use std::sync::Arc;
use std::time::Duration;

use anyhow::{anyhow, Result};
use once_cell::sync::OnceCell;
use tauri::{AppHandle, RunEvent, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tokio::sync::{oneshot, Mutex};
use tokio::time::timeout;

const SIDECAR_BINARY: &str = "delete-me-sidecar";
const SIDECAR_READY_TIMEOUT: Duration = Duration::from_secs(20);
const HEALTH_POLL_INTERVAL: Duration = Duration::from_secs(10);
const HEALTH_FAIL_THRESHOLD: u32 = 3;

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

/// Tracks consecutive health-probe failures and decides when to restart the
/// sidecar. Pure-state, no I/O — the async monitor wraps this around `reqwest`.
#[derive(Debug, PartialEq, Eq)]
enum HealthAction {
    Continue,
    RestartNow,
}

#[derive(Debug)]
struct HealthState {
    consecutive_failures: u32,
    threshold: u32,
}

impl HealthState {
    fn new(threshold: u32) -> Self {
        Self {
            consecutive_failures: 0,
            threshold,
        }
    }

    fn record_success(&mut self) -> HealthAction {
        self.consecutive_failures = 0;
        HealthAction::Continue
    }

    fn record_failure(&mut self) -> HealthAction {
        self.consecutive_failures += 1;
        if self.consecutive_failures >= self.threshold {
            // Reset so we give the restart time to come up before re-deciding.
            self.consecutive_failures = 0;
            HealthAction::RestartNow
        } else {
            HealthAction::Continue
        }
    }
}

struct SidecarState {
    child: Mutex<Option<CommandChild>>,
    api_base: OnceCell<String>,
    /// Port the sidecar is bound to. Captured on first spawn and re-used on
    /// restart so the UI's cached `api_base` stays valid across crashes.
    port: Mutex<Option<u16>>,
    health: Mutex<HealthState>,
}

impl SidecarState {
    fn new() -> Self {
        Self {
            child: Mutex::new(None),
            api_base: OnceCell::new(),
            port: Mutex::new(None),
            health: Mutex::new(HealthState::new(HEALTH_FAIL_THRESHOLD)),
        }
    }
}

#[tauri::command]
fn get_api_base(state: State<'_, Arc<SidecarState>>) -> Result<String, String> {
    state
        .api_base
        .get()
        .cloned()
        .ok_or_else(|| "sidecar has not advertised a listen address yet".to_string())
}

async fn spawn_sidecar(app: &AppHandle, state: Arc<SidecarState>) -> Result<()> {
    let mut cmd = app
        .shell()
        .sidecar(SIDECAR_BINARY)
        .map_err(|e| anyhow!("resolve sidecar: {e}"))?;

    // On restart, re-use the original port so api_base stays valid.
    if let Some(port) = *state.port.lock().await {
        cmd = cmd.env("DELETE_ME_SIDECAR_PORT", port.to_string());
    }

    let (mut rx, child) = cmd.spawn().map_err(|e| anyhow!("spawn sidecar: {e}"))?;
    *state.child.lock().await = Some(child);

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
                        // OnceCell::set is fine if the URL is identical on
                        // restart (same port). Discard the Err in that case.
                        let _ = state_for_reader.api_base.set(base.clone());
                        if let Some(port) = base
                            .rsplit_once(':')
                            .and_then(|(_, p)| p.parse::<u16>().ok())
                        {
                            *state_for_reader.port.lock().await = Some(port);
                        }
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

    match timeout(SIDECAR_READY_TIMEOUT, ready_rx).await {
        Ok(Ok(base)) => {
            log::info!("sidecar ready at {base}");
            Ok(())
        }
        Ok(Err(_)) => Err(anyhow!("sidecar exited before advertising a port")),
        Err(_) => Err(anyhow!(
            "sidecar did not advertise a port within {}s",
            SIDECAR_READY_TIMEOUT.as_secs()
        )),
    }
}

async fn probe_health(client: &reqwest::Client, base: &str) -> bool {
    let url = format!("{base}/health");
    match client.get(&url).send().await {
        Ok(resp) => resp.status().is_success(),
        Err(e) => {
            log::debug!("health probe failed: {e}");
            false
        }
    }
}

async fn restart_sidecar(app: &AppHandle, state: Arc<SidecarState>) {
    log::warn!("restarting sidecar (consecutive health failures hit threshold)");
    if let Some(child) = state.child.lock().await.take() {
        let _ = child.kill();
    }
    if let Err(e) = spawn_sidecar(app, state).await {
        log::error!("sidecar restart failed: {e:#}");
    }
}

fn spawn_health_monitor(app: AppHandle, state: Arc<SidecarState>) {
    tauri::async_runtime::spawn(async move {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(3))
            .build()
            .expect("build reqwest client");

        loop {
            tokio::time::sleep(HEALTH_POLL_INTERVAL).await;

            let Some(base) = state.api_base.get().cloned() else {
                continue;
            };
            let ok = probe_health(&client, &base).await;
            let action = {
                let mut h = state.health.lock().await;
                if ok {
                    h.record_success()
                } else {
                    h.record_failure()
                }
            };
            if matches!(action, HealthAction::RestartNow) {
                restart_sidecar(&app, state.clone()).await;
            }
        }
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let state = Arc::new(SidecarState::new());
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
                if let Err(e) = spawn_sidecar(&app_handle, state.clone()).await {
                    log::error!("failed to start sidecar: {e:#}");
                    return;
                }
                spawn_health_monitor(app_handle, state);
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
    use super::{parse_listening_line, HealthAction, HealthState};

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
        assert_eq!(parse_listening_line("LISTENING_ON 127.0.0.1"), None);
        assert_eq!(parse_listening_line("LISTENING_ON 127.0.0.1:abc"), None);
        assert_eq!(parse_listening_line("LISTENING_ON 127.0.0.1:"), None);
    }

    #[test]
    fn health_state_continues_below_threshold() {
        let mut h = HealthState::new(3);
        assert_eq!(h.record_failure(), HealthAction::Continue);
        assert_eq!(h.record_failure(), HealthAction::Continue);
    }

    #[test]
    fn health_state_restarts_at_threshold() {
        let mut h = HealthState::new(3);
        h.record_failure();
        h.record_failure();
        assert_eq!(h.record_failure(), HealthAction::RestartNow);
    }

    #[test]
    fn health_state_resets_after_restart() {
        // After triggering a restart, the counter resets so we don't
        // immediately restart again before the new sidecar has a chance to
        // come up.
        let mut h = HealthState::new(3);
        h.record_failure();
        h.record_failure();
        h.record_failure(); // RestartNow → resets counter
        assert_eq!(h.record_failure(), HealthAction::Continue);
        assert_eq!(h.record_failure(), HealthAction::Continue);
        assert_eq!(h.record_failure(), HealthAction::RestartNow);
    }

    #[test]
    fn health_state_success_resets_counter() {
        let mut h = HealthState::new(3);
        h.record_failure();
        h.record_failure();
        assert_eq!(h.record_success(), HealthAction::Continue);
        // Next two failures should not yet hit threshold.
        assert_eq!(h.record_failure(), HealthAction::Continue);
        assert_eq!(h.record_failure(), HealthAction::Continue);
    }
}
