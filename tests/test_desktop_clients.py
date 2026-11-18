from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import ingest  # noqa: E402
from app.main import app  # noqa: E402
from app.paths import RAW, WEB_DIST  # noqa: E402


@pytest.fixture
def client():
    if not (RAW / "GB55008-2021.pdf").is_file():
        pytest.skip("GB55008 PDF not in workspace")
    ingest.run(reset=True)
    return TestClient(app)


def test_electron_ask_no_fig_no(client: TestClient):
    r = client.post(
        "/v1/ask",
        json={
            "query": "纵向受力钢筋最小配筋率的强制性条文是哪一条",
            "project_id": "P-2018",
            "client": "electron",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["answer"].splitlines()[0] == "⚠ 强制性条文"
    for c in data["citations"]:
        assert not c.get("fig_no")
    assert any(c.get("article_no") == "8.5.1" for c in data["citations"])


def test_tauri_ask_and_chunk(client: TestClient):
    r = client.post(
        "/v1/ask",
        json={"query": "最小配筋率交底", "project_id": "P-2018", "client": "tauri"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["citations"]
    cid = data["citations"][0]["chunk_id"]
    ch = client.get(f"/v1/chunks/{cid}")
    assert ch.status_code == 200
    assert "条款正文" not in (ch.json().get("text") or "")


def test_page_image_and_spa_clients(client: TestClient):
    img = client.get("/media/pages/GB55008-2021/p001.jpg")
    assert img.status_code in (200, 404)
    vue = (ROOT / "apps" / "web" / "src" / "App.vue").read_text(encoding="utf-8")
    assert "图集未入库" in vue
    assert 'client: "tauri"' in vue or 'client.value === "tauri"' in vue
    assert (ROOT / "apps" / "web" / "src").is_dir()
    dist = WEB_DIST / "index.html"
    if dist.is_file():
        html = dist.read_text(encoding="utf-8")
        assert "app" in html
