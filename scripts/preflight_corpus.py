"""Traverse data/raw and report whether each file has extractable text.

SPEC [EXISTS] must cite a row in data/raw/_corpus_report.md.
Files with usable_chars == 0 (or only watermark-level text) must not enter
the full-text ingest path.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORT = RAW / "_corpus_report.md"
JSON_REPORT = RAW / "_corpus_report.json"

WATERMARK_MAX = 80  # per-page chars still treated as no article text


def sniff(path: Path) -> str:
    head = path.read_bytes()[:8]
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK"):
        return "zip"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        return "ole-doc"
    if path.suffix.lower() in {".md", ".json", ".csv", ".txt"}:
        return path.suffix.lower().lstrip(".")
    return "unknown"


def inspect_pdf(path: Path) -> dict:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = len(reader.pages)
    per_page = [len((p.extract_text() or "").strip()) for p in reader.pages]
    raw = path.read_bytes()
    usable = sum(c for c in per_page if c > WATERMARK_MAX)
    return {
        "kind": "pdf",
        "pages": pages,
        "chars_sum": sum(per_page),
        "chars_first5": per_page[:5],
        "usable_chars": usable,
        "text_layer": usable > 0,
        "need_ocr": usable == 0,
        "dctdecode": raw.count(b"/DCTDecode"),
        "tounicode": raw.count(b"/ToUnicode"),
        "notes": "page extract_text is watermark-only" if usable == 0 and sum(per_page) > 0 else "",
    }


def inspect_textish(path: Path, kind: str) -> dict:
    data = path.read_text(encoding="utf-8", errors="replace")
    return {
        "kind": kind,
        "pages": None,
        "chars_sum": len(data.strip()),
        "chars_first5": None,
        "usable_chars": len(data.strip()),
        "text_layer": True,
        "need_ocr": False,
        "notes": "",
    }


def inspect_ole(path: Path) -> dict:
    return {
        "kind": "ole-doc",
        "pages": None,
        "chars_sum": path.stat().st_size,
        "chars_first5": None,
        "usable_chars": 0,
        "text_layer": False,
        "need_ocr": False,
        "notes": "OLE Compound File (.doc). python-docx cannot read. provenance-only unless parsed as ole.",
    }


def inspect_one(path: Path) -> dict:
    kind = sniff(path)
    rec = {
        "file": path.name,
        "relpath": str(path.relative_to(ROOT)).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sniff": kind,
    }
    try:
        if kind == "pdf":
            rec.update(inspect_pdf(path))
        elif kind == "ole-doc":
            rec.update(inspect_ole(path))
        elif kind in {"md", "json", "csv", "txt"}:
            rec.update(inspect_textish(path, kind))
        else:
            rec.update(
                {
                    "kind": kind,
                    "pages": None,
                    "chars_sum": 0,
                    "usable_chars": 0,
                    "text_layer": False,
                    "need_ocr": False,
                    "notes": "unparsed",
                }
            )
    except Exception as exc:  # noqa: BLE001
        rec.update(
            {
                "kind": kind,
                "pages": None,
                "chars_sum": 0,
                "usable_chars": 0,
                "text_layer": False,
                "need_ocr": False,
                "notes": f"inspect_error: {exc}",
            }
        )
    rec["ingest_role"] = role_for(rec)
    return rec


def role_for(rec: dict) -> str:
    name = rec["file"]
    if name.startswith("_"):
        return "report"
    if rec.get("sniff") == "ole-doc":
        return "provenance-only"
    if name.endswith(".md") and name in {
        "GB50010-2010.md",
        "GB50010-2024.md",
        "GB50204-2015.md",
        "JGJ59-2011.md",
        "SOURCE.md",
    }:
        if name == "SOURCE.md":
            return "provenance-only"
        return "experimental-not-acceptance"
    if rec.get("kind") == "json" and "atlas" in name:
        return "experimental-not-acceptance"
    if rec.get("need_ocr") or rec.get("usable_chars", 0) == 0:
        if rec.get("kind") == "pdf":
            return "scan-page-locate"
        return "skip-fulltext-ingest"
    return "fulltext-ingest-ok"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    files = sorted(
        p
        for p in RAW.iterdir()
        if p.is_file() and not p.name.startswith("_")
    )
    rows = [inspect_one(p) for p in files]
    payload = {"generated": date.today().isoformat(), "rows": rows}
    JSON_REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Corpus preflight",
        "",
        f"Generated: {payload['generated']}",
        "",
        "SPEC `[EXISTS]` must cite **File** + this table. `chars=0` / `need_ocr=true` files must not enter the full-text ingest flowchart.",
        "",
        "| # | File | bytes | sniff | pages | chars_sum | usable_chars | text_layer | need_ocr | ingest_role | notes |",
        "|---|------|------:|-------|------:|----------:|-------------:|:----------:|:--------:|-------------|-------|",
    ]
    for i, r in enumerate(rows, 1):
        notes = (r.get("notes") or "").replace("|", "/")
        lines.append(
            f"| {i} | `{r['file']}` | {r['bytes']} | {r.get('sniff')} | {r.get('pages') if r.get('pages') is not None else ''} | "
            f"{r.get('chars_sum')} | {r.get('usable_chars')} | {str(r.get('text_layer')).lower()} | "
            f"{str(r.get('need_ocr')).lower()} | {r.get('ingest_role')} | {notes} |"
        )
    lines += [
        "",
        "## Roles",
        "",
        "- `fulltext-ingest-ok`: may enter §5.1 extract → article chunk.",
        "- `scan-page-locate`: page-level chunks only (doc_id + page); no article body.",
        "- `provenance-only`: metadata / official list; not article text.",
        "- `experimental-not-acceptance`: not in manifest for grading.",
        "- `skip-fulltext-ingest`: do not parse as articles.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(REPORT)
    for r in rows:
        print(f"{r['file']}\tusable={r.get('usable_chars')}\trole={r.get('ingest_role')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
