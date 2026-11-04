"""Build the one-folder executable (SPEC §8).

    python scripts/build_exe.py            # frontend build + PyInstaller → dist/Nodebook/
    python scripts/build_exe.py --skip-frontend

Requires: Node 20+, Python deps from requirements.txt, and `pyinstaller`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEP = ";" if os.name == "nt" else ":"


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, shell=(os.name == "nt"))


def build_frontend() -> None:
    fe = ROOT / "frontend"
    run(["npm", "ci"] if (fe / "package-lock.json").exists() else ["npm", "install"], fe)
    run(["npm", "run", "build"], fe)
    if not (ROOT / "backend" / "static" / "index.html").exists():
        sys.exit("frontend build did not produce backend/static/index.html")


def build_exe() -> Path:
    data = [
        (ROOT / "backend" / "static", "backend/static"),
        (ROOT / "backend" / "prompts", "backend/prompts"),
        (ROOT / "config", "config"),
    ]
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "Nodebook",
        "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
        "--collect-data", "dateparser", "--collect-data", "pptx", "--collect-submodules", "uvicorn",
        "--collect-all", "fsrs", "--collect-all", "genanki", "--collect-all", "pymupdf",
        "--hidden-import", "tzdata",
    ]
    for src, dest in data:
        cmd += ["--add-data", f"{src}{SEP}{dest}"]
    cmd.append(str(ROOT / "backend" / "launcher.py"))
    run(cmd, ROOT)
    out = ROOT / "dist" / "Nodebook"
    print(f"Built {out}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-frontend", action="store_true")
    ap.add_argument("--zip", action="store_true", help="also write dist/Nodebook-<platform>.zip")
    args = ap.parse_args()
    if not args.skip_frontend:
        build_frontend()
    out = build_exe()
    if args.zip:
        plat = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
        archive = shutil.make_archive(str(ROOT / "dist" / f"Nodebook-{plat}"), "zip", out.parent, out.name)
        print(f"Wrote {archive}")


if __name__ == "__main__":
    main()
