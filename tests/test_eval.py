from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from eval.run_eval import (  # noqa: E402
    DISCLAIMER,
    GOLDEN,
    REPORT_MD,
    load_golden,
    recall_items,
    score_article_item,
    score_g17,
    score_g18,
)


def test_recall_denominator_is_locked_seven():
    golden = load_golden()
    items = recall_items(golden)
    assert [it["id"] for it in items] == ["G01", "G02", "G03", "G08", "G09", "G11", "G14"]
    assert golden["scoring"]["recall_n"] == 7
    skipped = [it["id"] for it in golden["items"] if not it.get("in_recall")]
    assert "G17" in skipped
    assert "G18" in skipped
    assert "G04" in skipped
    raw = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert raw["items"][0]["id"] == "G01"


def test_g01_any_vs_g08_all():
    g01 = {"id": "G01", "expect_article_no": ["3.1.7", "8.5.1"], "match": "any"}
    hits = [{"article_no": "8.5.1"}, {"article_no": "11.7.14"}]
    assert score_article_item(g01, hits, k=5)["ok"] is True
    g08 = {"id": "G08", "expect_article_no": ["8.5.1"], "match": "all"}
    assert score_article_item(g08, [{"article_no": "3.1.7"}], k=5)["ok"] is False
    assert score_article_item(g08, [{"article_no": "8.5.1"}], k=5)["ok"] is True


def test_g17_g18_not_recall():
    g17 = score_g17(
        {"id": "G17", "expect_std_code": "GB 50010", "expect_version": "2010"},
        [{"std_code": "GB 50010", "version": "2010", "kind": "pointer"}],
    )
    assert g17["in_recall"] is False
    assert g17["ok"] is True
    g17_fail = score_g17(
        {"id": "G17", "expect_std_code": "GB 50010", "expect_version": "2010"},
        [{"std_code": "GB 55008", "version": "2021", "kind": "page"}],
    )
    assert g17_fail["ok"] is False
    g18 = score_g18(
        {"id": "G18", "forbidden_article_no": ["99.9.9"]},
        {
            "citations": [{"article_no": "8.5.1"}],
            "dropped_citation": [{"article_no": "99.9.9"}],
        },
    )
    assert g18["in_recall"] is False
    assert g18["ok"] is True
    leak = score_g18(
        {"id": "G18", "forbidden_article_no": ["99.9.9"]},
        {"citations": [{"article_no": "99.9.9"}], "dropped_citation": []},
    )
    assert leak["ok"] is False


def test_live_eval_writes_disclaimer():
    from app.paths import RAW
    from eval.run_eval import evaluate

    if not (RAW / "GB55008-2021.pdf").is_file():
        import pytest

        pytest.skip("GB55008 PDF not in workspace")
    payload = evaluate(reset=True)
    assert payload["recall_n"] == 7
    assert payload["disclaimer"] == DISCLAIMER
    assert "G17" not in payload["recall_ids"]
    assert "G18" not in payload["recall_ids"]
    text = REPORT_MD.read_text(encoding="utf-8")
    assert DISCLAIMER in text
    assert "未为凑分母编题或编页码" in text
    assert payload["version_gate"]["ok"] is True
    assert payload["citation_negative"]["ok"] is True
