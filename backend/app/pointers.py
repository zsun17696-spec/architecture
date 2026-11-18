"""GB 50010-2010 强条指针。条文号来自 743 号公告 CSV，不含编造正文。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .paths import ROOT

CSV_PATH = ROOT / "tasks" / "ref-gb50010-2010-mandatory.csv"

POINTER_TEMPLATE = (
    "{chapter_hint}；GB 50010-2010 第{article_no}条为强制性条文，"
    "自 2022-04-01 起废止，由 GB 55008-2021 承担。来源：住建部公告第743号。"
)


def pointer_text(article_no: str, chapter_hint: str) -> str:
    return POINTER_TEMPLATE.format(article_no=article_no, chapter_hint=chapter_hint)


def load_csv(path: Path = CSV_PATH) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_pointer_chunks(doc: dict[str, Any], rows: list[dict[str, str]] | None = None) -> list[dict[str, Any]]:
    rows = rows if rows is not None else load_csv()
    chunks = []
    for row in rows:
        article_no = row["article_no"].strip()
        hint = row["chapter_hint"].strip()
        chunks.append(
            {
                "doc_id": doc["id"],
                "std_code": doc["std_code"],
                "version": str(doc["version"]),
                "kind": "pointer",
                "valid_from": doc["valid_from"],
                "valid_to": doc["valid_to"],
                "mandatory_abolished_from": doc.get("mandatory_abolished_from") or "",
                "chapter": hint.split()[0] if hint else "",
                "chapter_title": hint,
                "section": "",
                "section_title": "",
                "article_no": article_no,
                "clause_no": "",
                "fig_no": "",
                "page": None,
                "caption": hint,
                "mandatory": True,
                "mandatory_source": "csv_743",
                "mandatory_confidence": 1.0,
                "mandatory_reviewed": 1,
                "text": pointer_text(article_no, hint),
                "image_path": "",
                "source_path": str((ROOT / doc.get("csv", "tasks/ref-gb50010-2010-mandatory.csv")).as_posix()),
            }
        )
    return chunks
