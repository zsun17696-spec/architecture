from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import answer, cite, ingest  # noqa: E402
from app.cite import HEADER
from app.main import app  # noqa: E402
from app.paths import RAW  # noqa: E402


@pytest.fixture(scope="module")
def client():
    if not (RAW / "GB55008-2021.pdf").is_file():
        pytest.skip("GB55008 PDF not in workspace")
    ingest.run(reset=True)
    return TestClient(app)


def test_ask_p2018_header_and_851(client: TestClient):
    r = client.post(
        "/v1/ask",
        json={
            "query": "纵向受力钢筋最小配筋率的强制性条文是哪一条",
            "project_id": "P-2018",
            "client": "admin",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["answer"].splitlines()[0] == HEADER
    assert data["mandatory_hit"] is True
    arts = {c["article_no"] for c in data["citations"]}
    assert "8.5.1" in arts
    ids = set(data["hit_ids"])
    assert all(c["chunk_id"] in ids for c in data["citations"])
    assert "条款正文" not in data["answer"]


def test_ask_p2024_page_no_fake_article(client: TestClient):
    r = client.post(
        "/v1/ask",
        json={"query": "混凝土结构通用规范", "project_id": "P-2024", "client": "flutter"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["citations"]
    for c in data["citations"]:
        assert c["std_code"] == "GB 55008"
        assert c["article_no"] == ""
        assert c.get("page")
    assert "2021年第167号" in data["answer"]
    assert "不编造条文号" in data["answer"]


def test_drop_fake_article(client: TestClient):
    r = client.post(
        "/v1/ask",
        json={
            "query": "请引用 GB 50010-2010 第 99.9.9 条",
            "project_id": "P-2018",
            "client": "tauri",
            "extra_proposed": [{"chunk_id": 99999, "article_no": "99.9.9", "std_code": "GB 50010", "version": "2010"}],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert all(c.get("article_no") != "99.9.9" for c in data["citations"])
    assert any(d.get("article_no") == "99.9.9" for d in data["dropped_citation"])
    tid = data["trace_id"]
    tr = client.get(f"/v1/traces/{tid}")
    assert tr.status_code == 200
    assert tr.json()["payload"]["dropped_citation"]


def test_stream_meta_header(client: TestClient):
    r = client.post(
        "/v1/ask/stream",
        json={"query": "强制性条文", "project_id": "P-2018", "client": "electron"},
    )
    assert r.status_code == 200
    body = r.text
    assert "event: meta" in body
    assert "event: token" in body
    assert "event: done" in body


def test_sanitize_unit():
    hits = [{"id": 1, "std_code": "GB 50010", "version": "2010", "article_no": "8.5.1", "mandatory": 1, "kind": "pointer", "doc_id": "x"}]
    kept, dropped = cite.sanitize(
        [{"chunk_id": "1", "article_no": "8.5.1"}, {"chunk_id": 2, "article_no": "99.9.9"}],
        hits,
    )
    assert len(kept) == 1
    assert kept[0]["chunk_id"] == 1
    assert dropped[0]["article_no"] == "99.9.9"
    assert answer.extractive(hits, "2018-06-01")["answer"].startswith(HEADER)


def test_page_image_rejects_dotdot(client: TestClient):
    r = client.get("/media/pages/../warehouse/p001.jpg")
    assert r.status_code in (400, 404, 422)


def test_bad_client(client: TestClient):
    r = client.post("/v1/ask", json={"query": "hi", "project_id": "P-2018", "client": "atlas"})
    assert r.status_code == 422
