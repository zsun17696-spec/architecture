"""按 章-节-条-款 切分规范 Markdown / 图集 JSON。"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .mandatory import classify, strip_marker

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
CHAPTER_RE = re.compile(r"^#\s+第(?P<no>\d+)章\s+(?P<title>.+)$")
SECTION_RE = re.compile(r"^##\s+(?P<no>\d+\.\d+)\s+(?P<title>.+)$")
ARTICLE_RE = re.compile(r"^###\s+(?P<no>\d+\.\d+\.\d+)\s*$")
CLAUSE_RE = re.compile(r"^####\s+(?P<no>\d+)\s*$")


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    m = FM_RE.match(text)
    if not m:
        return {}, text
    meta = yaml.safe_load(m.group(1)) or {}
    return meta, text[m.end() :]


def _as_date(v: Any) -> str:
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def chunk_markdown(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(raw)
    chunks: list[dict[str, Any]] = []
    chapter = section = article_no = ""
    chapter_title = section_title = ""
    buf: list[str] = []
    clause = ""
    marked = False

    def flush():
        nonlocal buf, marked, clause
        text = strip_marker("\n".join(buf).strip())
        if not article_no or not text:
            buf, marked, clause = [], False, ""
            return
        mandatory, rule, conf = classify(text, marked)
        chunks.append(
            {
                "doc_id": f"{meta.get('std_code')}-{meta.get('version')}",
                "std_code": meta.get("std_code"),
                "version": str(meta.get("version")),
                "title": meta.get("title"),
                "kind": meta.get("kind", "code"),
                "valid_from": _as_date(meta.get("valid_from")),
                "valid_to": _as_date(meta.get("valid_to")),
                "chapter": chapter,
                "chapter_title": chapter_title,
                "section": section,
                "section_title": section_title,
                "article_no": article_no,
                "clause_no": clause,
                "fig_no": "",
                "page": None,
                "caption": "",
                "mandatory": mandatory,
                "mandatory_rule": rule,
                "mandatory_confidence": conf,
                "text": text,
                "source_path": str(path.as_posix()),
            }
        )
        buf, marked, clause = [], False, ""

    for line in body.splitlines():
        if CHAPTER_RE.match(line):
            flush()
            m = CHAPTER_RE.match(line)
            chapter, chapter_title = m.group("no"), m.group("title")
            continue
        if SECTION_RE.match(line):
            flush()
            m = SECTION_RE.match(line)
            section, section_title = m.group("no"), m.group("title")
            continue
        if ARTICLE_RE.match(line):
            flush()
            article_no = ARTICLE_RE.match(line).group("no")
            continue
        if CLAUSE_RE.match(line):
            flush()
            clause = CLAUSE_RE.match(line).group("no")
            continue
        if "【强制性条文】" in line:
            marked = True
        if line.strip():
            buf.append(line)
    flush()
    return chunks


def chunk_atlas(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for p in data.get("pages", []):
        text = " ".join(
            [
                p.get("title", ""),
                p.get("caption", ""),
                " ".join(p.get("notes") or []),
            ]
        )
        mandatory, rule, conf = classify(text)
        out.append(
            {
                "doc_id": f"{data['std_code']}-{data['version']}",
                "std_code": data["std_code"],
                "version": str(data["version"]),
                "title": data.get("title"),
                "kind": "atlas",
                "valid_from": data.get("valid_from"),
                "valid_to": data.get("valid_to"),
                "chapter": "",
                "chapter_title": "",
                "section": "",
                "section_title": "",
                "article_no": p.get("fig_no"),
                "clause_no": "",
                "fig_no": p.get("fig_no"),
                "page": p.get("page"),
                "caption": p.get("caption"),
                "mandatory": mandatory,
                "mandatory_rule": rule,
                "mandatory_confidence": conf,
                "text": text,
                "source_path": str(path.as_posix()),
            }
        )
    return out


def chunk_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        return chunk_atlas(path)
    return chunk_markdown(path)
