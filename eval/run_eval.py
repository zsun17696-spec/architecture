"""Golden-set eval. Authority: eval/golden_set_20.json.

Recall denominator is only in_recall=true items (n=7). Trend only — not homework 0.85.
Does not invent questions or page maps to pad n.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import gateway, ingest, retrieve  # noqa: E402
from app.paths import EVAL_DIR, RAW  # noqa: E402

GOLDEN = EVAL_DIR / "golden_set_20.json"
REPORT_MD = EVAL_DIR / "_eval_report.md"
REPORT_JSON = EVAL_DIR / "_eval_last.json"
RECALL_K = 5
DISCLAIMER = "趋势参考，n=7，不对标作业 0.85"


def load_golden(path: Path = GOLDEN) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def recall_items(golden: dict[str, Any]) -> list[dict[str, Any]]:
    locked = list(golden["scoring"]["recall_ids"])
    items = [it for it in golden["items"] if it.get("in_recall")]
    ids = [it["id"] for it in items]
    if ids != locked:
        raise SystemExit(f"golden in_recall ids {ids} != scoring.recall_ids {locked}")
    if len(items) != int(golden["scoring"]["recall_n"]):
        raise SystemExit("recall_n mismatch")
    return items


def hit_articles(hits: list[dict[str, Any]], k: int) -> list[str]:
    out: list[str] = []
    for h in hits[:k]:
        art = (h.get("article_no") or "").strip()
        if art:
            out.append(art)
    return out


def score_article_item(item: dict[str, Any], hits: list[dict[str, Any]], k: int = RECALL_K) -> dict[str, Any]:
    expect = list(item.get("expect_article_no") or [])
    got = hit_articles(hits, k)
    mode = item.get("match") or "all"
    if mode == "any":
        ok = any(a in got for a in expect)
    else:
        ok = bool(expect) and all(a in got for a in expect)
    return {
        "id": item["id"],
        "ok": ok,
        "match": mode,
        "expect": expect,
        "got_top": got,
        "in_recall": True,
    }


def score_g17(item: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    want_code = item.get("expect_std_code") or "GB 50010"
    want_ver = str(item.get("expect_version") or "2010")
    versions = {(h.get("std_code"), str(h.get("version") or "")) for h in hits}
    has_wanted = (want_code, want_ver) in versions
    has_55008 = any(h.get("std_code") == "GB 55008" for h in hits)
    ok = bool(hits) and has_wanted and not has_55008
    return {
        "id": item["id"],
        "ok": ok,
        "score_as": "version_gate",
        "in_recall": False,
        "has_gb50010_2010": has_wanted,
        "has_gb55008": has_55008,
        "std_codes": sorted({h.get("std_code") or "" for h in hits}),
    }


def score_g18(item: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    forbidden = set(item.get("forbidden_article_no") or ["99.9.9"])
    cited = {str(c.get("article_no") or "") for c in result.get("citations") or []}
    dropped = {str(d.get("article_no") or "") for d in result.get("dropped_citation") or []}
    leak = bool(cited & forbidden)
    ok = (not leak) and bool(dropped & forbidden)
    return {
        "id": item["id"],
        "ok": ok,
        "score_as": "citation_negative",
        "in_recall": False,
        "cited_forbidden": sorted(cited & forbidden),
        "dropped_forbidden": sorted(dropped & forbidden),
    }


def evaluate(*, reset: bool = True, top_k: int = 10) -> dict[str, Any]:
    if not (RAW / "GB55008-2021.pdf").is_file():
        raise ingest.MissingPdf("GB 55008-2021")
    ingest.run(reset=reset)
    golden = load_golden()
    recall_rows = []
    for item in recall_items(golden):
        hits = retrieve.retrieve(
            item["query"],
            contract_date=item["contract_date"],
            policy="latest_eligible",
            top_k=top_k,
        )
        recall_rows.append(score_article_item(item, hits, k=RECALL_K))

    by_id = {it["id"]: it for it in golden["items"]}
    g17 = by_id["G17"]
    hits17 = retrieve.retrieve(
        g17["query"],
        contract_date=g17["contract_date"],
        policy="latest_eligible",
        top_k=top_k,
    )
    gate = score_g17(g17, hits17)

    g18 = by_id["G18"]
    ask18 = gateway.ask(
        g18["query"],
        contract_date=g18["contract_date"],
        client="admin",
        extra_proposed=[
            {"chunk_id": 99999, "article_no": "99.9.9", "std_code": "GB 50010", "version": "2010"}
        ],
    )
    cite_neg = score_g18(g18, ask18)

    n = len(recall_rows)
    hits_n = sum(1 for r in recall_rows if r["ok"])
    recall = hits_n / n if n else 0.0
    payload = {
        "disclaimer": DISCLAIMER,
        "recall_n": n,
        "recall_ids": [r["id"] for r in recall_rows],
        "recall_at_5": round(recall, 4),
        "recall_hits": hits_n,
        "recall_items": recall_rows,
        "version_gate": gate,
        "citation_negative": cite_neg,
        "excluded_from_recall": [it["id"] for it in golden["items"] if not it.get("in_recall")],
    }
    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_report(payload), encoding="utf-8")
    return payload


def render_report(p: dict[str, Any]) -> str:
    lines = [
        "# 黄金集评估",
        "",
        f"**{p['disclaimer']}**",
        "",
        f"- 权威文件：`eval/golden_set_20.json`",
        f"- Recall 分母 n={p['recall_n']}：{'/'.join(p['recall_ids'])}",
        f"- Recall@{RECALL_K} = {p['recall_hits']}/{p['recall_n']} = {p['recall_at_5']}",
        f"- 不计入 Recall：{', '.join(p['excluded_from_recall'])}（含 G17 版本闸门、G18 引用负例）",
        f"- 未为凑分母编题或编页码。",
        "",
        "## Recall 明细",
        "",
        "| id | ok | match | expect | got@5 |",
        "|----|----|-------|--------|-------|",
    ]
    for r in p["recall_items"]:
        lines.append(
            f"| {r['id']} | {r['ok']} | {r['match']} | {','.join(r['expect'])} | {','.join(r['got_top']) or '∅'} |"
        )
    g = p["version_gate"]
    c = p["citation_negative"]
    lines += [
        "",
        "## 单列（不进 Recall）",
        "",
        f"- G17 version_gate：{'PASS' if g['ok'] else 'FAIL'}（须见 GB 50010-2010，不得见 GB 55008 页）",
        f"- G18 citation_negative：{'PASS' if c['ok'] else 'FAIL'}（99.9.9 不得进 citations，须进 dropped_citation）",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        payload = evaluate(reset=True)
    except ingest.MissingPdf as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(payload["disclaimer"])
    print(f"Recall@{RECALL_K}={payload['recall_hits']}/{payload['recall_n']}={payload['recall_at_5']}")
    print(f"G17={'PASS' if payload['version_gate']['ok'] else 'FAIL'} G18={'PASS' if payload['citation_negative']['ok'] else 'FAIL'}")
    print(f"wrote {REPORT_MD.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
