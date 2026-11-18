from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from . import answer, cite, retrieve, store

Client = Literal["admin", "flutter", "tauri", "electron"]


def resolve_context(
    project_id: str | None,
    contract_date: str | None,
    conn,
) -> dict[str, Any]:
    if project_id:
        project = store.get_project(conn, project_id)
        if not project:
            raise KeyError(project_id)
        return project
    if not contract_date:
        raise ValueError("contract_date or project_id required")
    return {
        "id": None,
        "name": "adhoc",
        "contract_date": contract_date,
        "version_policy": "latest_eligible",
    }


def ask(
    query: str,
    *,
    project_id: str | None = None,
    contract_date: str | None = None,
    client: str = "admin",
    top_k: int = 8,
    extra_proposed: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if client not in ("admin", "flutter", "tauri", "electron"):
        raise ValueError("client must be admin|flutter|tauri|electron")
    if not query or not query.strip() or len(query) > 500:
        raise ValueError("query length 1-500")
    conn = store.connect()
    try:
        n = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if n == 0:
            raise RuntimeError("EMPTY_CORPUS")
        ctx = resolve_context(project_id, contract_date, conn)
        hits = retrieve.retrieve(
            query.strip(),
            contract_date=ctx["contract_date"],
            policy=ctx["version_policy"],
            top_k=top_k,
            conn=conn,
        )
        payload = answer.extractive(hits, ctx["contract_date"])
        if extra_proposed:
            _, extra_drop = cite.sanitize(extra_proposed, hits)
            payload["dropped_citation"] = payload["dropped_citation"] + extra_drop
        if os.environ.get("OPENAI_API_KEY"):
            # SPEC: optional LLM; this milestone stays extractive even if a key is set.
            payload["mode"] = "extractive"
        trace_id = str(uuid.uuid4())
        created = datetime.now(timezone.utc).isoformat()
        trace = {
            "trace_id": trace_id,
            "created_at": created,
            "query": query.strip(),
            "client": client,
            "project": ctx,
            "contract_date": ctx["contract_date"],
            "safety_query": retrieve.is_safety_query(query),
            "hit_ids": [int(h["id"]) for h in hits],
            "mode": payload["mode"],
            "mandatory_hit": payload["mandatory_hit"],
            "citations": payload["citations"],
            "dropped_citation": payload["dropped_citation"],
        }
        store.save_trace(conn, trace_id, created, trace)
        return {
            "trace_id": trace_id,
            **payload,
            "hit_ids": trace["hit_ids"],
        }
    finally:
        conn.close()
