from __future__ import annotations

import json
import sqlite3
from typing import Any

from .paths import CHUNKS_DIR, CLEAN, DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  std_code TEXT NOT NULL,
  version TEXT NOT NULL,
  title TEXT,
  kind TEXT,
  status TEXT,
  valid_from TEXT NOT NULL,
  valid_to TEXT NOT NULL,
  mandatory_abolished_from TEXT,
  source_path TEXT,
  replaced_by TEXT,
  pointer_source TEXT,
  abolition_annex TEXT
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id TEXT NOT NULL,
  std_code TEXT NOT NULL,
  version TEXT NOT NULL,
  kind TEXT,
  valid_from TEXT,
  valid_to TEXT,
  mandatory_abolished_from TEXT,
  chapter TEXT,
  chapter_title TEXT,
  section TEXT,
  section_title TEXT,
  article_no TEXT NOT NULL DEFAULT '',
  clause_no TEXT,
  fig_no TEXT,
  page INTEGER,
  caption TEXT,
  mandatory INTEGER NOT NULL,
  mandatory_source TEXT,
  mandatory_confidence REAL,
  mandatory_reviewed INTEGER DEFAULT 0,
  text TEXT NOT NULL,
  image_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunk_cite ON chunks(std_code, version, article_no);
CREATE INDEX IF NOT EXISTS idx_chunk_kind ON chunks(kind);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT,
  contract_date TEXT NOT NULL,
  version_policy TEXT NOT NULL DEFAULT 'latest_eligible'
);
CREATE TABLE IF NOT EXISTS traces (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  payload TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chunk_id INTEGER,
  action TEXT,
  note TEXT,
  created_at TEXT
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def reset_warehouse() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()


def upsert_document(conn: sqlite3.Connection, doc: dict[str, Any], source_path: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO documents (
          id, std_code, version, title, kind, status,
          valid_from, valid_to, mandatory_abolished_from,
          source_path, replaced_by, pointer_source, abolition_annex
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            doc["id"],
            doc["std_code"],
            str(doc["version"]),
            doc.get("title"),
            doc.get("kind"),
            doc.get("status", "active"),
            doc["valid_from"],
            doc["valid_to"],
            doc.get("mandatory_abolished_from") or "",
            source_path,
            doc.get("replaced_by") or "",
            doc.get("pointer_source") or "",
            doc.get("abolition_annex") or "",
        ),
    )


def insert_chunks(conn: sqlite3.Connection, chunks: list[dict[str, Any]]) -> None:
    for c in chunks:
        conn.execute(
            """
            INSERT INTO chunks (
              doc_id, std_code, version, kind, valid_from, valid_to,
              mandatory_abolished_from, chapter, chapter_title, section, section_title,
              article_no, clause_no, fig_no, page, caption,
              mandatory, mandatory_source, mandatory_confidence, mandatory_reviewed,
              text, image_path
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                c["doc_id"],
                c["std_code"],
                c["version"],
                c["kind"],
                c["valid_from"],
                c["valid_to"],
                c.get("mandatory_abolished_from") or "",
                c.get("chapter") or "",
                c.get("chapter_title") or "",
                c.get("section") or "",
                c.get("section_title") or "",
                c.get("article_no") or "",
                c.get("clause_no") or "",
                c.get("fig_no") or "",
                c.get("page"),
                c.get("caption") or "",
                1 if c.get("mandatory") else 0,
                c.get("mandatory_source") or "",
                c.get("mandatory_confidence") or 0,
                int(c.get("mandatory_reviewed") or 0),
                c["text"],
                c.get("image_path") or "",
            ),
        )
    conn.commit()


def write_artifacts(chunks: list[dict[str, Any]], report: dict[str, Any]) -> None:
    CLEAN.mkdir(parents=True, exist_ok=True)
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    by_doc: dict[str, list] = {}
    for c in chunks:
        by_doc.setdefault(c["doc_id"], []).append(c)
    for doc_id, items in by_doc.items():
        (CLEAN / f"{doc_id}.json").write_text(
            json.dumps(
                {
                    "doc_id": doc_id,
                    "std_code": items[0]["std_code"],
                    "version": items[0]["version"],
                    "kind": items[0]["kind"],
                    "n_chunks": len(items),
                    "n_with_article_no": sum(1 for x in items if x.get("article_no")),
                    "n_pages": sum(1 for x in items if x.get("kind") == "page"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        (CHUNKS_DIR / f"{doc_id}.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in items),
            encoding="utf-8",
        )
    (CLEAN / "_ingest_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Ingest report",
        "",
        f"- missing_pdf: `{report.get('missing_pdf')}`",
        f"- pointers: {report.get('n_pointers')}",
        f"- page chunks: {report.get('n_pages')}",
        f"- article bodies extracted from GB55008 PDF: {report.get('n_articles_from_scan')}",
        f"- page images: {report.get('n_images')}",
        "",
        "Scan PDF is page-locate only. Pointer text is CSV + announcement 743.",
        "",
    ]
    (CLEAN / "_ingest_report.md").write_text("\n".join(lines), encoding="utf-8")


def seed_projects(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM projects")
    conn.executemany(
        "INSERT INTO projects (id, name, contract_date, version_policy) VALUES (?,?,?,?)",
        [
            ("P-2018", "某办公楼主体（2018 合同）", "2018-06-01", "latest_eligible"),
            ("P-2024", "某医院门诊楼（2024 合同）", "2024-06-01", "latest_eligible"),
            ("P-PARALLEL", "并行期对比项目", "2024-03-15", "all_eligible"),
        ],
    )
    conn.commit()


def count_by_kind(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT kind, COUNT(*) n FROM chunks GROUP BY kind").fetchall()
    return {r["kind"]: r["n"] for r in rows}


def list_chunks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT c.*, COALESCE(d.status, 'active') AS doc_status
            FROM chunks c
            LEFT JOIN documents d ON d.id = c.doc_id
            ORDER BY c.std_code, c.article_no, c.page, c.id
            """
        ).fetchall()
    ]


def get_chunk(conn: sqlite3.Connection, chunk_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT c.*, COALESCE(d.status, 'active') AS doc_status
        FROM chunks c
        LEFT JOIN documents d ON d.id = c.doc_id
        WHERE c.id=?
        """,
        (chunk_id,),
    ).fetchone()
    return dict(row) if row else None


def list_chunks_filtered(
    conn: sqlite3.Connection,
    *,
    mandatory: int | None = None,
    std_code: str | None = None,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    rows = list_chunks(conn)
    out = rows
    if mandatory is not None:
        out = [c for c in out if int(c.get("mandatory") or 0) == mandatory]
    if std_code:
        out = [c for c in out if c.get("std_code") == std_code]
    if kind:
        out = [c for c in out if c.get("kind") == kind]
    return out


def patch_document(
    conn: sqlite3.Connection,
    doc_id: str,
    *,
    valid_from: str | None = None,
    valid_to: str | None = None,
    status: str | None = None,
) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        return None
    doc = dict(row)
    vf = valid_from or doc["valid_from"]
    vt = valid_to or doc["valid_to"]
    st = status or doc["status"]
    conn.execute(
        "UPDATE documents SET valid_from=?, valid_to=?, status=? WHERE id=?",
        (vf, vt, st, doc_id),
    )
    conn.execute(
        "UPDATE chunks SET valid_from=?, valid_to=? WHERE doc_id=?",
        (vf, vt, doc_id),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone())


def patch_chunk_mandatory(
    conn: sqlite3.Connection,
    chunk_id: int,
    mandatory: bool,
    note: str = "",
) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM chunks WHERE id=?", (chunk_id,)).fetchone()
    if not row:
        return None
    conn.execute(
        "UPDATE chunks SET mandatory=?, mandatory_reviewed=1 WHERE id=?",
        (1 if mandatory else 0, chunk_id),
    )
    conn.execute(
        "INSERT INTO reviews (chunk_id, action, note, created_at) VALUES (?,?,?,datetime('now'))",
        (chunk_id, "mandatory=" + ("1" if mandatory else "0"), note or ""),
    )
    conn.commit()
    updated = conn.execute(
        """
        SELECT c.*, COALESCE(d.status, 'active') AS doc_status
        FROM chunks c
        LEFT JOIN documents d ON d.id = c.doc_id
        WHERE c.id=?
        """,
        (chunk_id,),
    ).fetchone()
    return dict(updated) if updated else None


def list_reviews(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM reviews ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    ]


def list_traces(conn: sqlite3.Connection, limit: int = 30) -> list[dict[str, Any]]:
    out = []
    for row in conn.execute(
        "SELECT id, created_at, payload FROM traces ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ):
        item = dict(row)
        item["payload"] = json.loads(item["payload"])
        out.append(item)
    return out


def get_project(conn: sqlite3.Connection, project_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return dict(row) if row else None


def list_projects(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM projects ORDER BY id").fetchall()]


def list_documents(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM documents ORDER BY id").fetchall()]


def save_trace(conn: sqlite3.Connection, trace_id: str, created_at: str, payload: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO traces (id, created_at, payload) VALUES (?,?,?)",
        (trace_id, created_at, json.dumps(payload, ensure_ascii=False)),
    )
    conn.commit()


def get_trace(conn: sqlite3.Connection, trace_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM traces WHERE id=?", (trace_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["payload"] = json.loads(data["payload"])
    return data
