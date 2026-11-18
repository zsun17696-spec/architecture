"""Citations must be a subset of this-turn hit chunk_ids."""

from __future__ import annotations

from typing import Any

HEADER = "⚠ 强制性条文"


def is_current_mandatory(chunk: dict[str, Any], contract_date: str) -> bool:
    if int(chunk.get("mandatory") or 0) != 1:
        return False
    abolished = (chunk.get("mandatory_abolished_from") or "").strip()
    if chunk.get("kind") == "pointer" and abolished and contract_date >= abolished:
        return False
    return True


def from_hit(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": int(chunk["id"]),
        "std_code": chunk.get("std_code") or "",
        "version": str(chunk.get("version") or ""),
        "article_no": chunk.get("article_no") or "",
        "clause_no": chunk.get("clause_no") or "",
        "fig_no": chunk.get("fig_no") or "",
        "page": chunk.get("page"),
        "kind": chunk.get("kind"),
        "mandatory": bool(int(chunk.get("mandatory") or 0)),
        "doc_id": chunk.get("doc_id") or "",
    }


def sanitize(
    proposed: list[dict[str, Any]],
    hits: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed = {int(h["id"]) for h in hits}
    by_id = {int(h["id"]): h for h in hits}
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for item in proposed:
        article = str(item.get("article_no") or "")
        try:
            cid = int(item.get("chunk_id"))
        except (TypeError, ValueError):
            dropped.append({**item, "reason": "not_in_this_turn_hits"})
            continue
        if article == "99.9.9" or cid not in allowed:
            dropped.append({**item, "reason": "not_in_this_turn_hits"})
            continue
        hit = by_id[cid]
        kept.append(from_hit(hit))
    return kept, dropped
