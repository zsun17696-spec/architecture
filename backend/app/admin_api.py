from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from . import ingest, store
from .paths import EVAL_DIR, WEB_DIST

router = APIRouter()


def require_admin(x_role: str | None) -> None:
    if (x_role or "user").lower() != "admin":
        raise HTTPException(403, "FORBIDDEN")


class DocumentPatch(BaseModel):
    valid_from: str | None = None
    valid_to: str | None = None
    status: str | None = None


class MandatoryPatch(BaseModel):
    mandatory: bool
    note: str = ""


@router.patch("/v1/documents/{doc_id}")
def patch_document(doc_id: str, body: DocumentPatch, x_role: str | None = Header(default=None)):
    require_admin(x_role)
    if body.status and body.status not in ("active", "abolished"):
        raise HTTPException(400, "status must be active|abolished")
    conn = store.connect()
    try:
        row = store.patch_document(
            conn,
            doc_id,
            valid_from=body.valid_from,
            valid_to=body.valid_to,
            status=body.status,
        )
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "document not found")
    return row


@router.get("/v1/chunks")
def chunks(
    mandatory: int | None = Query(default=None),
    std_code: str | None = Query(default=None),
    kind: str | None = Query(default=None),
):
    conn = store.connect()
    try:
        return store.list_chunks_filtered(conn, mandatory=mandatory, std_code=std_code, kind=kind)
    finally:
        conn.close()


@router.get("/v1/chunks/{chunk_id}")
def get_chunk(chunk_id: int):
    conn = store.connect()
    try:
        row = store.get_chunk(conn, chunk_id)
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "chunk not found")
    return row


@router.patch("/v1/chunks/{chunk_id}/mandatory")
def patch_mandatory(chunk_id: int, body: MandatoryPatch, x_role: str | None = Header(default=None)):
    require_admin(x_role)
    conn = store.connect()
    try:
        row = store.patch_chunk_mandatory(conn, chunk_id, body.mandatory, body.note)
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "chunk not found")
    return row


@router.get("/v1/reviews")
def reviews(limit: int = Query(default=50, ge=1, le=200)):
    conn = store.connect()
    try:
        return store.list_reviews(conn, limit)
    finally:
        conn.close()


@router.get("/v1/traces")
def traces(limit: int = Query(default=30, ge=1, le=100)):
    conn = store.connect()
    try:
        return store.list_traces(conn, limit)
    finally:
        conn.close()


@router.get("/v1/eval/latest")
def eval_latest(x_role: str | None = Header(default=None)):
    require_admin(x_role)
    path = EVAL_DIR / "_eval_last.json"
    if not path.is_file():
        raise HTTPException(404, "run python eval/run_eval.py first")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/v1/ingest")
def trigger_ingest(x_role: str | None = Header(default=None), reset: bool = True):
    require_admin(x_role)
    try:
        return ingest.run(reset=reset)
    except ingest.MissingPdf as exc:
        raise HTTPException(422, str(exc)) from None


def spa_hint() -> dict[str, Any]:
    return {
        "app": "矩典 SpecGate",
        "web": "apps/web (npm run dev) or dist",
        "client": "admin|electron|tauri",
        "dist": str(WEB_DIST),
    }
