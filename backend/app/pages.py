"""Scan-page locate: count pages and render images. Never treat extract_text as articles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .paths import PAGES


def page_count(pdf_path: Path) -> int:
    return len(PdfReader(str(pdf_path)).pages)


def render_pages(pdf_path: Path, doc_id: str, scale: float = 1.4) -> list[Path]:
    """Write JPEG page images. Fail soft if pypdfium2 is missing."""
    out_dir = PAGES / doc_id
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []
    pdf = pdfium.PdfDocument(str(pdf_path))
    paths: list[Path] = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            bitmap = page.render(scale=scale)
            pil = bitmap.to_pil()
            dest = out_dir / f"p{i + 1:03d}.jpg"
            pil.convert("RGB").save(dest, "JPEG", quality=72, optimize=True)
            paths.append(dest)
    finally:
        pdf.close()
    return paths


def build_page_chunks(doc: dict[str, Any], pdf_path: Path, image_paths: list[Path]) -> list[dict[str, Any]]:
    n = page_count(pdf_path)
    by_index = {int(p.stem[1:]): p for p in image_paths if p.stem.startswith("p")}
    chunks = []
    for i in range(1, n + 1):
        img = by_index.get(i)
        rel = str(img.as_posix()) if img else ""
        chunks.append(
            {
                "doc_id": doc["id"],
                "std_code": doc["std_code"],
                "version": str(doc["version"]),
                "kind": "page",
                "valid_from": doc["valid_from"],
                "valid_to": doc["valid_to"],
                "mandatory_abolished_from": doc.get("mandatory_abolished_from") or "",
                "chapter": "",
                "chapter_title": "",
                "section": "",
                "section_title": "",
                "article_no": "",
                "clause_no": "",
                "fig_no": "",
                "page": i,
                "caption": f"{doc['title']} 扫描页 {i}/{n}",
                "mandatory": True,
                "mandatory_source": "gb55008_scan",
                "mandatory_confidence": 1.0,
                "mandatory_reviewed": 0,
                "text": (
                    f"扫描页 p{i}，无文本层，不承诺条文正文。"
                    f"规范 {doc['std_code']}-{doc['version']}《{doc['title']}》。"
                    "出处：住房和城乡建设部公告2021年第167号。"
                ),
                "image_path": rel,
                "source_path": str(pdf_path.as_posix()),
            }
        )
    return chunks
