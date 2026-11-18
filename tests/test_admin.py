from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import ingest, retrieve, store  # noqa: E402
from app.main import app  # noqa: E402
from app.paths import RAW  # noqa: E402

QUERY_851 = "纵向受力钢筋最小配筋率的强制性条文是哪一条"


@pytest.fixture
def client():
    if not (RAW / "GB55008-2021.pdf").is_file():
        pytest.skip("GB55008 PDF not in workspace")
    ingest.run(reset=True)
    return TestClient(app)


def test_patch_valid_to_applies_on_next_ask(client: TestClient):
    hits = retrieve.retrieve(QUERY_851, contract_date="2018-06-01", policy="latest_eligible", top_k=14)
    assert any(h.get("article_no") == "8.5.1" for h in hits)
    forbidden = client.patch(
        "/v1/documents/GB50010-2010-pointers",
        json={"valid_to": "2017-12-31"},
    )
    assert forbidden.status_code == 403
    ok = client.patch(
        "/v1/documents/GB50010-2010-pointers",
        json={"valid_to": "2017-12-31"},
        headers={"X-Role": "admin"},
    )
    assert ok.status_code == 200
    assert ok.json()["valid_to"] == "2017-12-31"
    hits2 = retrieve.retrieve(QUERY_851, contract_date="2018-06-01", policy="latest_eligible", top_k=14)
    assert not any(h.get("kind") == "pointer" for h in hits2)
    ask = client.post("/v1/ask", json={"query": QUERY_851, "project_id": "P-2018", "client": "admin"})
    arts = {c.get("article_no") for c in ask.json().get("citations") or []}
    assert "8.5.1" not in arts


def test_patch_mandatory_next_query(client: TestClient):
    conn = store.connect()
    try:
        row = conn.execute("SELECT id FROM chunks WHERE article_no='8.5.1'").fetchone()
        cid = int(row["id"])
    finally:
        conn.close()
    r = client.patch(
        f"/v1/chunks/{cid}/mandatory",
        json={"mandatory": False, "note": "demo override"},
        headers={"X-Role": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["mandatory"] == 0
    hits = retrieve.retrieve("强制性条文", contract_date="2018-06-01", policy="latest_eligible", top_k=14)
    target = next(h for h in hits if h.get("article_no") == "8.5.1")
    assert int(target["mandatory"]) == 0
    assert target.get("safety_boost") is False


def test_eval_latest_and_chunks(client: TestClient):
    rows = client.get("/v1/chunks", params={"kind": "pointer"}).json()
    assert len(rows) == 14
    ev = client.get("/v1/eval/latest", headers={"X-Role": "admin"})
    assert ev.status_code in (200, 404)
    if ev.status_code == 200:
        assert ev.json().get("recall_n") == 7
