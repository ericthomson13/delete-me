"""Integration test for the Tauri sidecar entry point.

Spawns service/sidecar_entry.py as a real subprocess — the same way the
Rust shell does — and verifies the contract the desktop app depends on:

  1. The process advertises its listen address on stdout via
     `LISTENING_ON 127.0.0.1:<port>` BEFORE accepting requests.
  2. That port serves the FastAPI app (health + /cases both respond).
  3. The process terminates cleanly on SIGTERM.

If this passes, the Tauri Rust shell's only remaining responsibility is to
faithfully spawn the binary and parse the stdout line — both of which are
covered by `cargo test` in tauri-app/src-tauri/.
"""

from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SIDECAR_ENTRY = REPO_ROOT / "service" / "sidecar_entry.py"
LISTENING_RE = re.compile(r"^LISTENING_ON\s+(\S+)\s*$")


def _wait_for_handshake(proc: subprocess.Popen[str], timeout: float = 30.0) -> str:
    """Block until the sidecar prints its LISTENING_ON line. Returns host:port."""
    deadline = time.monotonic() + timeout
    assert proc.stdout is not None
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"sidecar exited before handshake (rc={proc.returncode})"
                )
            time.sleep(0.05)
            continue
        m = LISTENING_RE.match(line.strip())
        if m:
            return m.group(1)
    raise TimeoutError("sidecar did not advertise LISTENING_ON within timeout")


def _socket_is_listening(host: str, port: int, timeout: float = 5.0) -> bool:
    """Poll until something accepts on host:port (covers uvicorn's startup gap)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.05)
    return False


@pytest.fixture
def sidecar(tmp_path: Path):
    env = os.environ.copy()
    env["DELETE_ME_DB_URL"] = f"sqlite:///{tmp_path / 'sidecar.db'}"
    env["DELETE_ME_LOG_LEVEL"] = "warning"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, str(SIDECAR_ENTRY)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        addr = _wait_for_handshake(proc)
        host, port_s = addr.rsplit(":", 1)
        port = int(port_s)
        assert host == "127.0.0.1", f"sidecar bound to non-loopback host: {host}"
        assert _socket_is_listening(host, port), (
            f"sidecar advertised {addr} but nothing is listening"
        )
        yield host, port, proc
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def test_sidecar_advertises_loopback_port_and_serves_api(sidecar):
    host, port, _proc = sidecar
    base = f"http://{host}:{port}"

    r = httpx.get(f"{base}/health", timeout=5.0)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = httpx.get(f"{base}/cases", timeout=5.0)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_sidecar_terminates_cleanly_on_sigterm(sidecar):
    _host, _port, proc = sidecar
    proc.send_signal(signal.SIGTERM)
    rc = proc.wait(timeout=10)
    # uvicorn returns 0 on a clean SIGTERM. On some platforms a graceful
    # shutdown surfaces as a negative signal exit code; both are fine — what
    # we care about is that the process actually exits in bounded time.
    assert rc == 0 or rc == -signal.SIGTERM, f"unexpected exit code {rc}"


def test_handshake_is_machine_parseable():
    """Belt-and-suspenders: confirm the format the Rust parser expects."""
    sample = "LISTENING_ON 127.0.0.1:54321"
    m = LISTENING_RE.match(sample)
    assert m and m.group(1) == "127.0.0.1:54321"
