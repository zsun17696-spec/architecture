from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import ingest, retrieve, search  # noqa: E402
from app.paths import RAW  # noqa: E402


@pytest.fixture(scope="module")
def _ingested():
    if not (RAW / "GB55008-2021.pdf").is_file():
        pytest.skip("GB55008 PDF not in workspace")
    ingest.run(reset=True)
    search._INDEX = search.LexicalIndex()


def _kinds(hits):
    return {h["kind"] for h in hits}


def _codes(hits):
    return {h["std_code"] for h in hits}


def test_p2018_pointers_no_55008_pages(_ingested):
    _, hits = retrieve.retrieve_for_project("纵向受力钢筋最小配筋率的强制性条文是哪一条", "P-2018", top_k=14)
    assert hits
    assert "pointer" in _kinds(hits)
    assert "GB 50010" in _codes(hits)
    assert not any(h["kind"] == "page" and h["std_code"] == "GB 55008" for h in hits)
    assert any(h.get("article_no") == "8.5.1" for h in hits)


def test_p2024_no_pointers_has_page(_ingested):
    _, hits = retrieve.retrieve_for_project("混凝土结构通用规范扫描页", "P-2024", top_k=8)
    assert hits
    assert not any(h["kind"] == "pointer" for h in hits)
    assert not any(h["std_code"] == "GB 50010" for h in hits)
    pages = [h for h in hits if h["kind"] == "page" and h["std_code"] == "GB 55008"]
    assert len(pages) >= 1
    assert pages[0].get("page") is not None
    assert pages[0].get("doc_id")


def test_parallel_both_std_codes(_ingested):
    _, hits = retrieve.retrieve_for_project("强制性条文", "P-PARALLEL", top_k=20)
    assert hits
    assert "GB 50010" in _codes(hits)
    assert "GB 55008" in _codes(hits)
    assert "pointer" in _kinds(hits)
    assert "page" in _kinds(hits)


def test_safety_only_four_markers():
    assert retrieve.is_safety_query("这是强制性条文吗")
    assert retrieve.is_safety_query("必须严格执行")
    assert retrieve.is_safety_query("严禁降低")
    assert retrieve.is_safety_query("强条清单")
    assert not retrieve.is_safety_query("混凝土保护层厚度在哪一节")
    assert not retrieve.is_safety_query("最小配筋率规定")
    assert not retrieve.is_safety_query("抗震构造")


def test_safety_multiplier(_ingested):
    q = "强制性条文"
    a = retrieve.retrieve(q, contract_date="2018-06-01", policy="latest_eligible", top_k=5)
    assert a and a[0].get("safety_boost") is True
    q2 = "混凝土保护层厚度在哪一节"
    b = retrieve.retrieve(q2, contract_date="2018-06-01", policy="latest_eligible", top_k=5)
    assert all(h.get("safety_boost") is False for h in b)
