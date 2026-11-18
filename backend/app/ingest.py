"""I-01 ingest: GB 55008 scan pages + GB 50010 pointer CSV.

Does not scrape the web. Does not parse experimental markdown as standards.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import pages, pointers, store
from .paths import MANIFEST, RAW, ROOT


class MissingPdf(SystemExit):
    def __init__(self, std: str) -> None:
        super().__init__(f"MISSING_PDF: {std}")


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(reset: bool = True) -> dict:
    manifest = load_manifest()
    docs = {d["id"]: d for d in manifest["documents"]}

    pdf_meta = docs["GB55008-2021"]
    pdf_path = RAW / pdf_meta["filename"]
    if not pdf_path.is_file():
        raise MissingPdf("GB 55008-2021")
    if reset:
        store.reset_warehouse()

    ptr_meta = docs["GB50010-2010-pointers"]
    ole_path = RAW / ptr_meta["filename"]
    ole_note = "provenance-only"
    if ole_path.is_file():
        head = ole_path.read_bytes()[:8]
        if head.startswith(b"\xd0\xcf\x11\xe0"):
            ole_note = "OLE/.doc provenance-only; not parsed with python-docx"

    images = pages.render_pages(pdf_path, pdf_meta["id"])
    page_chunks = pages.build_page_chunks(pdf_meta, pdf_path, images)
    pointer_chunks = pointers.build_pointer_chunks(ptr_meta)

    assert not any(c.get("article_no") for c in page_chunks), "scan PDF must not yield article numbers"
    assert len(pointer_chunks) == 14

    conn = store.connect()
    store.upsert_document(conn, pdf_meta, str(pdf_path.as_posix()))
    store.upsert_document(
        conn,
        ptr_meta,
        str((ROOT / ptr_meta.get("csv", "tasks/ref-gb50010-2010-mandatory.csv")).as_posix()),
    )
    all_chunks = page_chunks + pointer_chunks
    store.insert_chunks(conn, all_chunks)
    store.seed_projects(conn)

    kinds = store.count_by_kind(conn)
    report = {
        "missing_pdf": None,
        "n_pointers": kinds.get("pointer", 0),
        "n_pages": kinds.get("page", 0),
        "n_articles_from_scan": 0,
        "n_images": len(images),
        "ole": ole_note,
        "pdf": str(pdf_path.as_posix()),
        "projects": ["P-2018", "P-2024", "P-PARALLEL"],
    }
    store.write_artifacts(all_chunks, report)
    conn.close()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest official corpus (pages + pointers)")
    parser.add_argument("--reset", action="store_true", default=True)
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args(argv)
    reset = not args.no_reset
    try:
        report = run(reset=reset)
    except MissingPdf as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("ingest ok")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("pointers=14 scan_articles=0 pages=%s images=%s" % (report["n_pages"], report["n_images"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
