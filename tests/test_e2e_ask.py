from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import ingest  # noqa: E402
from app.cite import HEADER  # noqa: E402
from app.main import app  # noqa: E402
from app.paths import RAW  # noqa: E402

QUERY_851 = "纵向受力钢筋最小配筋率的强制性条文是哪一条"


@pytest.fixture
def client():
    if not (RAW / "GB55008-2021.pdf").is_file():
        pytest.skip("GB55008 PDF not in workspace")
    ingest.run(reset=True)
    return TestClient(app)


def test_happy_p2018_header_851_and_trace(client: TestClient):
    r = client.post(
        "/v1/ask",
        json={"query": QUERY_851, "project_id": "P-2018", "client": "admin"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["answer"].splitlines()[0] == HEADER
    cites = data["citations"]
    assert any(c["article_no"] == "8.5.1" and c["std_code"] == "GB 50010" and str(c["version"]) == "2010" for c in cites)
    tr = client.get(f"/v1/traces/{data['trace_id']}")
    assert tr.status_code == 200
    payload = tr.json()["payload"]
    assert payload["hit_ids"]
    assert payload["query"] == QUERY_851


def test_p2024_no_pointer_has_page(client: TestClient):
    from app import retrieve

    _, hits = retrieve.retrieve_for_project("混凝土结构通用规范扫描页", "P-2024", top_k=8)
    assert hits
    assert not any(h["kind"] == "pointer" for h in hits)
    assert not any(h["std_code"] == "GB 50010" for h in hits)
    pages = [h for h in hits if h["kind"] == "page" and h["std_code"] == "GB 55008"]
    assert pages
    assert pages[0].get("page") is not None


def test_fake_citation_dropped(client: TestClient):
    r = client.post(
        "/v1/ask",
        json={
            "query": "请引用 GB 50010-2010 第 99.9.9 条",
            "project_id": "P-2018",
            "client": "admin",
            "extra_proposed": [{"chunk_id": 99999, "article_no": "99.9.9", "std_code": "GB 50010", "version": "2010"}],
        },
    )
    data = r.json()
    assert all(c.get("article_no") != "99.9.9" for c in data["citations"])
    assert any(d.get("article_no") == "99.9.9" for d in data["dropped_citation"])


def test_missing_pdf_message(tmp_path):
    from unittest.mock import patch

    with patch.object(ingest, "RAW", tmp_path):
        with pytest.raises(ingest.MissingPdf, match="MISSING_PDF: GB 55008-2021"):
            ingest.run(reset=True)


def test_reset_repeatable(client: TestClient):
    ingest.run(reset=True)
    ingest.run(reset=True)
    r = client.post(
        "/v1/ask",
        json={"query": QUERY_851, "project_id": "P-2018", "client": "admin"},
    )
    assert r.status_code == 200
    assert any(c["article_no"] == "8.5.1" for c in r.json()["citations"])


def test_e2e_script_reset():
    if not (RAW / "GB55008-2021.pdf").is_file():
        pytest.skip("GB55008 PDF not in workspace")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "e2e.py"), "--reset"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "E2E PASS" in proc.stdout
