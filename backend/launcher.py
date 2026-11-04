"""Nodebook entry point for the one-run executable (SPEC §8).

Pick a free port on 127.0.0.1 → start Uvicorn → open the default browser.
Single instance: a second launch finds the running app through the lock file and
just opens the browser to it."""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import httpx

from backend.core.settings import default_config_dir

HOST = "127.0.0.1"  # never bind anything else


def lock_path() -> Path:
    return default_config_dir() / "nodebook.lock"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return int(s.getsockname()[1])


def running_instance() -> str | None:
    """URL of an already running Nodebook, or None (stale locks are ignored)."""
    p = lock_path()
    try:
        info = json.loads(p.read_text("utf-8"))
        url = f"http://{HOST}:{int(info['port'])}"
        r = httpx.get(f"{url}/api/health", timeout=1.5)
        if r.status_code == 200 and r.json().get("status") == "ok":
            return url
    except (OSError, ValueError, KeyError, httpx.HTTPError):
        return None
    return None


def write_lock(port: int) -> None:
    p = lock_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"pid": os.getpid(), "port": port}), "utf-8")


def remove_lock() -> None:
    try:
        info = json.loads(lock_path().read_text("utf-8"))
        if info.get("pid") == os.getpid():
            lock_path().unlink()
    except (OSError, ValueError):
        pass


def open_when_ready(url: str, timeout: float = 30.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if httpx.get(f"{url}/api/health", timeout=1.0).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.15)
    if os.environ.get("NODEBOOK_NO_BROWSER") != "1":
        webbrowser.open(url)


def main() -> int:
    existing = running_instance()
    if existing:
        print(f"Nodebook is already running at {existing}")
        if os.environ.get("NODEBOOK_NO_BROWSER") != "1":
            webbrowser.open(existing)
        return 0

    import uvicorn

    from backend.app import create_app

    port = int(os.environ.get("NODEBOOK_PORT") or free_port())
    url = f"http://{HOST}:{port}"
    write_lock(port)
    print(f"Nodebook is running at {url}  (close this window to quit)")
    threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    try:
        uvicorn.run(create_app(), host=HOST, port=port, log_level="warning")
    finally:
        remove_lock()
    return 0


if __name__ == "__main__":
    sys.exit(main())
