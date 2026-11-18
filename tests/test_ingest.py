from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import ingest, pointers, store  # noqa: E402
from app.paths import DB_PATH, RAW  # noqa: E402


def test_pointer_count_and_chapter_hint():
    rows = pointers.load_csv()
    assert len(rows) == 14
    doc = json.loads((ROOT / "data" / "raw" / "manifest.json").read_text(encoding="utf-8"))[
        "documents"
    ][1]
    chunks = pointers.build_pointer_chunks(doc, rows)
    assert len(chunks) == 14
    for row, chunk in zip(rows, chunks, strict=True):
        assert chunk["kind"] == "pointer"
        assert chunk["article_no"] == row["article_no"]
        assert row["chapter_hint"] in chunk["text"]
        assert "住建部公告第743号" in chunk["text"]
        assert "条款正文" not in chunk["text"]


def test_missing_pdf(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest, "RAW", tmp_path)
    with pytest.raises(ingest.MissingPdf, match="MISSING_PDF: GB 55008-2021"):
        ingest.run(reset=True)


def test_full_ingest_scan_has_no_articles():
    if not (RAW / "GB55008-2021.pdf").is_file():
        pytest.skip("GB55008 PDF not in workspace")
    report = ingest.run(reset=True)
    assert report["n_pointers"] == 14
    assert report["n_articles_from_scan"] == 0
    assert report["n_pages"] >= 1
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    pages = conn.execute("SELECT * FROM chunks WHERE kind='page'").fetchall()
    assert all(not r["article_no"] for r in pages)
    assert all(r["page"] is not None and r["page"] >= 1 for r in pages)
    ptrs = conn.execute("SELECT * FROM chunks WHERE kind='pointer'").fetchall()
    assert len(ptrs) == 14
    assert {r["article_no"] for r in ptrs} >= {"8.5.1", "3.1.7", "11.7.14"}
    projects = {r[0] for r in conn.execute("SELECT id FROM projects")}
    assert projects == {"P-2018", "P-2024", "P-PARALLEL"}
    conn.close()
    report_md = ROOT / "data" / "clean" / "_ingest_report.md"
    assert report_md.is_file()
