from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def test_launcher_starts_and_second_launch_reuses(tmp_path: Path) -> None:
    env = {**os.environ, "NODEBOOK_CONFIG_DIR": str(tmp_path / "cfg"), "NODEBOOK_NO_BROWSER": "1", "NODEBOOK_FAKE_LLM": "1"}
    (tmp_path / "cfg").mkdir()
    (tmp_path / "cfg" / "settings.json").write_text(json.dumps({"data_dir": str(tmp_path / "data")}))
    proc = subprocess.Popen([sys.executable, "-m", "backend.launcher"], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        lock = tmp_path / "cfg" / "nodebook.lock"
        t0 = time.monotonic()
        url = None
        while time.monotonic() - t0 < 10:  # SPEC §8 AC: up within 10 s
            if lock.exists():
                port = json.loads(lock.read_text())["port"]
                try:
                    if httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=0.5).status_code == 200:
                        url = f"http://127.0.0.1:{port}"
                        break
                except httpx.HTTPError:
                    pass
            time.sleep(0.1)
        assert url, "launcher did not come up within 10 s"
        second = subprocess.run([sys.executable, "-m", "backend.launcher"], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=20)
        assert second.returncode == 0 and "already running" in second.stdout
    finally:
        proc.terminate()
        proc.wait(timeout=10)
