from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from .paths import CLEAN, CHUNKS_DIR, DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  std_code TEXT,
  version TEXT,
  title TEXT,
  kind TEXT,
  valid_from TEXT,
  valid_to TEXT,
  source_path TEXT,
  status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  doc_id TEXT,
  std_code TEXT,
  version TEXT,
  kind TEXT,
  valid_from TEXT,
  valid_to TEXT,
  chapter TEXT,
  chapter_title TEXT,
  section TEXT,
  section_title TEXT,
  article_no TEXT,
  clause_no TEXT,
  fig_no TEXT,
  page INTEGER,
  caption TEXT,
  mandatory INTEGER,
  mandatory_rule TEXT,
  mandatory_confidence REAL,
  mandatory_reviewed INTEGER DEFAULT 0,
  text TEXT
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT,
  contract_date TEXT,
  version_policy TEXT DEFAULT 'latest_eligible'
);
CREATE TABLE IF NOT EXISTS traces (
  id TEXT PRIMARY KEY,
  created_at TEXT,
  payload TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
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


def reset_chunks(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM documents")
    conn.commit()


def upsert_document(conn: sqlite3.Connection, chunk: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO documents
        (id, std_code, version, title, kind, valid_from, valid_to, source_path, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """,
        (
            chunk["doc_id"],
            chunk["std_code"],
            chunk["version"],
            chunk["title"],
            chunk["kind"],
            chunk["valid_from"],
            chunk["valid_to"],
            chunk["source_path"],
        ),
    )


def insert_chunks(conn: sqlite3.Connection, chunks: list[dict[str, Any]]) -> None:
    for c in chunks:
        conn.execute(
            """
            INSERT INTO chunks (
              doc_id, std_code, version, kind, valid_from, valid_to,
              chapter, chapter_title, section, section_title,
              article_no, clause_no, fig_no, page, caption,
              mandatory, mandatory_rule, mandatory_confidence, text
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                c["doc_id"],
                c["std_code"],
                c["version"],
                c["kind"],
                c["valid_from"],
                c["valid_to"],
                c["chapter"],
                c["chapter_title"],
                c["section"],
                c["section_title"],
                c["article_no"],
                c["clause_no"],
                c["fig_no"],
                c["page"],
                c["caption"],
                1 if c["mandatory"] else 0,
                c["mandatory_rule"],
                c["mandatory_confidence"],
                c["text"],
            ),
        )
    conn.commit()


def write_artifacts(chunks: list[dict[str, Any]]) -> None:
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
                    "n_chunks": len(items),
                    "mandatory": sum(1 for x in items if x["mandatory"]),
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


def seed_projects(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO projects VALUES ('P-2018','某办公楼主体','2018-06-01','latest_eligible')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO projects VALUES ('P-2024','某医院门诊楼','2024-06-01','latest_eligible')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO projects VALUES ('P-PARALLEL','并行期对比项目','2024-03-15','all_eligible')"
    )
    conn.commit()


def eligible_versions(conn: sqlite3.Connection, contract_date: str, std_code: str | None = None):
    q = "SELECT * FROM documents WHERE status='active' AND valid_from<=? AND valid_to>=?"
    args: list[Any] = [contract_date, contract_date]
    if std_code:
        q += " AND std_code=?"
        args.append(std_code)
    return [dict(r) for r in conn.execute(q, args).fetchall()]


def all_chunks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM chunks").fetchall()]


def get_chunk(conn: sqlite3.Connection, chunk_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM chunks WHERE id=?", (chunk_id,)).fetchone()
    return dict(row) if row else None


def today() -> str:
    return date.today().isoformat()
