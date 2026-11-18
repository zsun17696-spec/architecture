from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import ingest  # noqa: E402
from app.main import app  # noqa: E402
from app.paths import RAW  # noqa: E402


@pytest.fixture
def client():
    if not (RAW / "GB55008-2021.pdf").is_file():
        pytest.skip("GB55008 PDF not in workspace")
    ingest.run(reset=True)
    return TestClient(app)


def test_sync_pack_has_14_pointers(client: TestClient):
    r = client.get("/v1/sync/mandatory")
    assert r.status_code == 200
    rows = r.json()
    ptrs = [x for x in rows if x.get("kind") == "pointer"]
    assert len(ptrs) == 14
    hit = next(x for x in ptrs if x.get("article_no") == "8.5.1")
    assert "住建部公告第743号" in hit["text"]
    assert "8.5" in hit["text"]
    assert "条款正文" not in hit["text"]
    assert hit.get("std_code") == "GB 50010"
    flutter = client.post(
        "/v1/ask",
        json={
            "query": "纵向受力钢筋最小配筋率的强制性条文是哪一条",
            "project_id": "P-2018",
            "client": "flutter",
        },
    )
    assert flutter.status_code == 200
    assert flutter.json()["answer"].splitlines()[0] == "⚠ 强制性条文"
