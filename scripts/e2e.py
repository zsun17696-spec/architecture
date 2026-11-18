"""One-shot E2E: ingest --reset → P-2018 ask → P-2024 retrieve → fake cite.

python scripts/e2e.py --reset
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import gateway, ingest, retrieve  # noqa: E402
from app.cite import HEADER  # noqa: E402
from app.paths import RAW  # noqa: E402

QUERY_851 = "纵向受力钢筋最小配筋率的强制性条文是哪一条"


def check_happy() -> list[str]:
    fails: list[str] = []
    result = gateway.ask(QUERY_851, project_id="P-2018", client="admin")
    first = (result.get("answer") or "").splitlines()[0] if result.get("answer") else ""
    if first != HEADER:
        fails.append(f"header want {HEADER!r} got {first!r}")
    arts = {c.get("article_no") for c in result.get("citations") or []}
    codes = {(c.get("std_code"), str(c.get("version"))) for c in result.get("citations") or []}
    if "8.5.1" not in arts:
        fails.append(f"missing 8.5.1 in citations {arts}")
    if ("GB 50010", "2010") not in codes:
        fails.append(f"missing GB 50010 2010 in {codes}")
    if not result.get("trace_id"):
        fails.append("no trace_id")
    from app import store

    conn = store.connect()
    try:
        row = store.get_trace(conn, result["trace_id"])
    finally:
        conn.close()
    if not row:
        fails.append("trace not persisted")
    return fails


def check_p2024() -> list[str]:
    fails: list[str] = []
    _, hits = retrieve.retrieve_for_project("混凝土结构通用规范扫描页", "P-2024", top_k=8)
    if any(h.get("kind") == "pointer" for h in hits):
        fails.append("P-2024 has pointer")
    if any(h.get("std_code") == "GB 50010" for h in hits):
        fails.append("P-2024 has GB 50010")
    pages = [h for h in hits if h.get("kind") == "page" and h.get("std_code") == "GB 55008"]
    if not pages:
        fails.append("P-2024 missing GB 55008 page")
    elif pages[0].get("page") is None:
        fails.append("page field empty")
    return fails


def check_fake_cite() -> list[str]:
    fails: list[str] = []
    result = gateway.ask(
        "请引用 GB 50010-2010 第 99.9.9 条",
        project_id="P-2018",
        client="admin",
        extra_proposed=[{"chunk_id": 99999, "article_no": "99.9.9", "std_code": "GB 50010", "version": "2010"}],
    )
    if any(c.get("article_no") == "99.9.9" for c in result.get("citations") or []):
        fails.append("99.9.9 leaked into citations")
    if not any(d.get("article_no") == "99.9.9" for d in result.get("dropped_citation") or []):
        fails.append("99.9.9 not in dropped_citation")
    return fails


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", default=True)
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args(argv)
    reset = not args.no_reset
    if not (RAW / "GB55008-2021.pdf").is_file():
        print("MISSING_PDF: GB 55008-2021", file=sys.stderr)
        return 2
    report = ingest.run(reset=reset)
    print("ingest ok", json.dumps({"n_pages": report["n_pages"], "n_pointers": report["n_pointers"]}, ensure_ascii=False))
    fails = check_happy() + check_p2024() + check_fake_cite()
    if fails:
        print("E2E FAIL")
        for f in fails:
            print("-", f)
        return 1
    print("E2E PASS: P-2018 header+8.5.1; P-2024 page-only; 99.9.9 dropped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
