"""Measure Electron startup/RSS; record Tauri status. Writes docs/desktop-compare.md.

Requires: gateway on SPECGATE_URL (default http://127.0.0.1:8000) and npm electron.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ELECTRON_DIR = ROOT / "apps" / "electron"
DOC = ROOT / "docs" / "desktop-compare.md"
GATEWAY = os.environ.get("SPECGATE_URL", "http://127.0.0.1:8000")


def gateway_ok() -> bool:
    try:
        with urlopen(GATEWAY + "/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def electron_bin() -> Path:
    named = ELECTRON_DIR / "node_modules" / "electron" / "dist" / "electron.exe"
    if named.is_file():
        return named
    unix = ELECTRON_DIR / "node_modules" / "electron" / "dist" / "electron"
    if unix.is_file():
        return unix
    raise FileNotFoundError("electron binary missing; run node node_modules/electron/install.js")


def probe_electron(client: str) -> dict:
    env = os.environ.copy()
    env["SPECGATE_URL"] = GATEWAY
    env["SPECGATE_CLIENT"] = client
    env["SPECGATE_HEADLESS"] = "1"
    t0 = time.perf_counter()
    proc = subprocess.run(
        [str(electron_bin()), "."],
        cwd=ELECTRON_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    wall = round((time.perf_counter() - t0) * 1000)
    line = ""
    for raw in (proc.stdout or "").splitlines()[::-1]:
        if raw.strip().startswith("{"):
            line = raw.strip()
            break
    if not line:
        return {
            "client": client,
            "shell": "electron",
            "ok": False,
            "startup_ms": wall,
            "rss_mb": None,
            "note": (proc.stderr or proc.stdout or "no json")[:400],
        }
    data = json.loads(line)
    data["ok"] = True
    data["wall_ms"] = wall
    return data


def rustc_ok() -> bool:
    return shutil.which("rustc") is not None and shutil.which("cargo") is not None


def render(rows: list[dict], gateway: bool) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Desktop compare (Electron vs Tauri2)",
        "",
        f"Measured: {now}. Same Vue dist: `apps/web/dist` served by FastAPI `/?client=`.",
        "",
        "| shell | client | startup_ms | rss_mb | notes |",
        "|-------|--------|------------|--------|-------|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('shell')} | {r.get('client')} | {r.get('startup_ms')} | {r.get('rss_mb')} | {r.get('note', r.get('url', ''))} |"
        )
    lines += [
        "",
        f"- Gateway `{GATEWAY}` reachable: **{gateway}**.",
        f"- rustc/cargo present: **{rustc_ok()}**. This machine cannot build native Tauri2 until Rust is installed.",
        "- Electron loads the **same** SPA as Tauri (`apps/web/dist`). Atlas missing → 条文号/扫描页, never invent `fig_no`.",
        "- Tauri mode is `http://127.0.0.1:8000/?client=tauri` (handover draft + citations). Native binary: `apps/tauri-handover`.",
        "- FR-24: fill native Tauri RSS after `cargo tauri build`; until then SPA row is the demo path (SPEC: npm/dev same SPA).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    gw = gateway_ok()
    rows: list[dict] = []
    if (ELECTRON_DIR / "package.json").is_file():
        for c in ("electron", "tauri"):
            try:
                rows.append(probe_electron(c))
            except Exception as exc:
                rows.append(
                    {
                        "shell": "electron",
                        "client": c,
                        "startup_ms": "",
                        "rss_mb": "",
                        "note": str(exc),
                    }
                )
    rows.append(
        {
            "shell": "tauri2-native",
            "client": "tauri",
            "startup_ms": "n/a",
            "rss_mb": "n/a",
            "note": "rustc missing; conf at apps/tauri-handover/src-tauri",
        }
    )
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(render(rows, gw), encoding="utf-8")
    print(DOC.read_text(encoding="utf-8"))
    return 0 if gw else 2


if __name__ == "__main__":
    raise SystemExit(main())
