"""Extractive answers. No fabricated GB 50010 body. Scan pages cite page + 167 only."""

from __future__ import annotations

from typing import Any

from .cite import HEADER, from_hit, is_current_mandatory, sanitize


def format_hit(chunk: dict[str, Any]) -> str:
    kind = chunk.get("kind")
    code = chunk.get("std_code")
    ver = chunk.get("version")
    if kind == "pointer":
        return (
            f"【{code}-{ver} 第{chunk.get('article_no')}条】\n"
            f"{chunk.get('text') or ''}"
        )
    if kind == "page":
        page = chunk.get("page")
        doc_id = chunk.get("doc_id")
        return (
            f"【{code}-{ver} 扫描页 p{page}】doc_id={doc_id} page={page}\n"
            "出处：住房和城乡建设部公告2021年第167号。本页无文本层，不编造条文号。"
        )
    return f"【{code}-{ver}】\n{chunk.get('text') or ''}"


def extractive(hits: list[dict[str, Any]], contract_date: str) -> dict[str, Any]:
    used = hits[:3]
    proposed = [from_hit(h) for h in used]
    citations, dropped = sanitize(proposed, hits)
    mandatory_hit = any(is_current_mandatory(h, contract_date) for h in used)
    parts = [format_hit(h) for h in used]
    if not used:
        body = "当前合同日期下没有适用版本的检索结果。"
        mandatory_hit = False
    else:
        body = "\n\n".join(parts)
    if mandatory_hit:
        answer = HEADER + "\n" + body
    else:
        answer = body
    versions = []
    seen = set()
    for h in used:
        key = (h.get("std_code"), str(h.get("version")))
        if key in seen:
            continue
        seen.add(key)
        versions.append({"std_code": key[0], "version": key[1]})
    return {
        "mode": "extractive",
        "mandatory_hit": mandatory_hit,
        "answer": answer,
        "citations": citations,
        "dropped_citation": dropped,
        "used_versions": versions,
    }
