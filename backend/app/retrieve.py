"""Contract-date filter + lexical retrieve. Mandatory/validity always read from DB rows."""

from __future__ import annotations

from typing import Any

from . import search, store

SAFETY_MARKERS = ("强制", "强条", "必须", "严禁")
BM25_W = 0.6
LEX_W = 0.4
SAFETY_MULT = 1.25


def is_safety_query(query: str) -> bool:
    return any(m in (query or "") for m in SAFETY_MARKERS)


def eligible_chunks(
    chunks: list[dict[str, Any]],
    contract_date: str,
    policy: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    drop_pointers = policy == "latest_eligible"
    for c in chunks:
        status = c.get("doc_status") or "active"
        if c.get("kind") != "pointer" and status == "abolished":
            continue
        vf, vt = c.get("valid_from") or "0000-01-01", c.get("valid_to") or "9999-12-31"
        if not (vf <= contract_date <= vt):
            continue
        abolished = (c.get("mandatory_abolished_from") or "").strip()
        if drop_pointers and c.get("kind") == "pointer" and abolished and contract_date >= abolished:
            continue
        out.append(c)
    if policy != "latest_eligible":
        return out
    best: dict[str, str] = {}
    for c in out:
        code = c["std_code"]
        ver_from = c.get("valid_from") or ""
        if code not in best or ver_from > best[code]:
            best[code] = ver_from
    return [c for c in out if c.get("valid_from") == best.get(c["std_code"])]


def _ensure_std_code_coverage(
    ranked: list[tuple[float, dict[str, Any]]],
    top_k: int,
    policy: str,
) -> list[tuple[float, dict[str, Any]]]:
    """all_eligible: keep the best hit per std_code so Top-k is not one code only."""
    if policy != "all_eligible" or not ranked:
        return ranked
    picked: list[tuple[float, dict[str, Any]]] = []
    seen: set[str] = set()
    for item in ranked:
        code = item[1]["std_code"]
        if code in seen:
            continue
        picked.append(item)
        seen.add(code)
    picked_ids = {item[1]["id"] for item in picked}
    for item in ranked:
        if item[1]["id"] in picked_ids:
            continue
        picked.append(item)
        picked_ids.add(item[1]["id"])
        if len(picked) >= top_k:
            break
    picked.sort(key=lambda x: x[0], reverse=True)
    return picked[: max(top_k, len(seen))]


def _blend(bm25: float, lex: float, query: str, chunk: dict[str, Any]) -> float:
    s = BM25_W * bm25 + LEX_W * lex
    if is_safety_query(query) and int(chunk.get("mandatory") or 0) == 1:
        s *= SAFETY_MULT
    return s


def retrieve(
    query: str,
    *,
    contract_date: str,
    policy: str = "latest_eligible",
    top_k: int = 8,
    conn=None,
) -> list[dict[str, Any]]:
    own = conn is None
    if own:
        conn = store.connect()
    try:
        chunks = store.list_chunks(conn)
        if not chunks:
            return []
        index = search.get_index(chunks)
        cand = eligible_chunks(chunks, contract_date, policy)
        raw = {int(c["id"]): c for c in cand}
        scored = index.scores(query) if index.ids else {}
        ranked: list[tuple[float, dict[str, Any]]] = []
        for cid, chunk in raw.items():
            bm25, lex = scored.get(cid, (0.0, 0.0))
            ranked.append((_blend(bm25, lex, query, chunk), chunk))
        ranked.sort(key=lambda x: x[0], reverse=True)
        ranked = _ensure_std_code_coverage(ranked, top_k, policy)
        hits = []
        for score, chunk in ranked[:top_k]:
            item = dict(chunk)
            item["score"] = round(float(score), 6)
            item["safety_boost"] = is_safety_query(query) and int(chunk.get("mandatory") or 0) == 1
            hits.append(item)
        return hits
    finally:
        if own:
            conn.close()


def retrieve_for_project(query: str, project_id: str, top_k: int = 8) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    conn = store.connect()
    try:
        project = store.get_project(conn, project_id)
        if not project:
            raise KeyError(f"unknown project: {project_id}")
        hits = retrieve(
            query,
            contract_date=project["contract_date"],
            policy=project["version_policy"],
            top_k=top_k,
            conn=conn,
        )
        return project, hits
    finally:
        conn.close()
