"""Entry point used when the FastAPI service is bundled as a Tauri sidecar.

The Tauri shell spawns this binary, reads stdout for a line of the form
`LISTENING_ON 127.0.0.1:<port>`, and uses that to point the UI at the API.
We pick an ephemeral free port ourselves so multiple installs can coexist
and so we never collide with whatever is on 8000.
"""

from __future__ import annotations

import os
import socket
import sys

import uvicorn

from service.app import app


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    port = int(os.environ.get("DELETE_ME_SIDECAR_PORT") or _free_loopback_port())
    # Print BEFORE uvicorn starts so the parent reads the port immediately.
    # Tauri waits up to 20s for the next health/readiness signal; uvicorn
    # binding the port is the signal.
    sys.stdout.write(f"LISTENING_ON 127.0.0.1:{port}\n")
    sys.stdout.flush()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level=os.environ.get("DELETE_ME_LOG_LEVEL", "info").lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
