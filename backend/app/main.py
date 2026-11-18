from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import admin_api, gateway, store
from .cite import HEADER
from .paths import PAGES, WEB_DIST

app = FastAPI(title="矩典 SpecGate", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

Client = Literal["admin", "flutter", "tauri", "electron"]


class AskBody(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    project_id: str | None = None
    contract_date: str | None = None
    client: Client = "admin"
    top_k: int = Field(default=8, ge=1, le=40)
    extra_proposed: list[dict[str, Any]] | None = None


@app.get("/health")
def health():
    conn = store.connect()
    try:
        n = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    except Exception:
        n = 0
    finally:
        conn.close()
    return {"ok": True, "chunks": n, "corpus": "ready" if n else "empty"}


@app.get("/v1/projects")
def projects():
    conn = store.connect()
    try:
        return store.list_projects(conn)
    finally:
        conn.close()


@app.get("/v1/documents")
def documents():
    conn = store.connect()
    try:
        return store.list_documents(conn)
    finally:
        conn.close()


@app.post("/v1/ask")
def ask(body: AskBody, x_role: str | None = Header(default=None)):
    _ = x_role
    try:
        return gateway.ask(
            body.query,
            project_id=body.project_id,
            contract_date=body.contract_date,
            client=body.client,
            top_k=body.top_k,
            extra_proposed=body.extra_proposed,
        )
    except KeyError:
        raise HTTPException(404, "project not found") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except RuntimeError as exc:
        if str(exc) == "EMPTY_CORPUS":
            raise HTTPException(503, "EMPTY_CORPUS") from None
        raise


@app.post("/v1/ask/stream")
def ask_stream(body: AskBody):
    try:
        result = gateway.ask(
            body.query,
            project_id=body.project_id,
            contract_date=body.contract_date,
            client=body.client,
            top_k=body.top_k,
            extra_proposed=body.extra_proposed,
        )
    except KeyError:
        raise HTTPException(404, "project not found") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except RuntimeError as exc:
        if str(exc) == "EMPTY_CORPUS":
            raise HTTPException(503, "EMPTY_CORPUS") from None
        raise

    def events():
        meta = {
            "trace_id": result["trace_id"],
            "mandatory_hit": result["mandatory_hit"],
            "header": HEADER if result["mandatory_hit"] else None,
            "mode": result["mode"],
        }
        yield f"event: meta\ndata: {json.dumps(meta, ensure_ascii=False)}\n\n"
        text = result["answer"]
        for i in range(0, len(text), 24):
            piece = text[i : i + 24]
            yield f"event: token\ndata: {json.dumps({'t': piece}, ensure_ascii=False)}\n\n"
        done = {
            "citations": result["citations"],
            "dropped_citation": result["dropped_citation"],
            "trace_id": result["trace_id"],
        }
        yield f"event: done\ndata: {json.dumps(done, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/v1/traces/{trace_id}")
def get_trace(trace_id: str):
    conn = store.connect()
    try:
        row = store.get_trace(conn, trace_id)
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "trace not found")
    return row


@app.get("/v1/sync/mandatory")
def sync_mandatory():
    conn = store.connect()
    try:
        rows = conn.execute(
            "SELECT article_no, std_code, version, mandatory, text, valid_from, valid_to, kind, page "
            "FROM chunks WHERE kind='pointer' OR (kind='page' AND mandatory=1)"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/media/pages/{doc_id}/{name}")
def page_image(doc_id: str, name: str):
    if ".." in doc_id or ".." in name or "/" in doc_id or "\\" in doc_id or "/" in name or "\\" in name:
        raise HTTPException(400, "bad path")
    if not name.lower().endswith((".jpg", ".jpeg", ".png")):
        raise HTTPException(404, "not an image")
    path = (PAGES / doc_id / name).resolve()
    root = PAGES.resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404, "page image not found")
    return FileResponse(path)


app.include_router(admin_api.router)


@app.get("/")
def root():
    index = WEB_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    return admin_api.spa_hint()


assets = WEB_DIST / "assets"
if assets.is_dir():
    app.mount("/assets", StaticFiles(directory=assets), name="assets")
