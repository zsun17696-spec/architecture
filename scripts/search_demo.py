"""Interview demo: same query, three contract dates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.retrieve import retrieve_for_project  # noqa: E402


def summarize(hits: list[dict]) -> dict:
    return {
        "n": len(hits),
        "kinds": sorted({h.get("kind") for h in hits}),
        "std_codes": sorted({h.get("std_code") for h in hits}),
        "n_pointers": sum(1 for h in hits if h.get("kind") == "pointer"),
        "n_pages": sum(1 for h in hits if h.get("kind") == "page"),
        "top": [
            {
                "id": h["id"],
                "kind": h["kind"],
                "std_code": h["std_code"],
                "article_no": h.get("article_no"),
                "page": h.get("page"),
                "score": h.get("score"),
            }
            for h in hits[:5]
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--query", default="纵向受力钢筋最小配筋率的强制性条文是哪一条")
    p.add_argument("--project", action="append")
    args = p.parse_args()
    projects = args.project or ["P-2018", "P-2024", "P-PARALLEL"]
    out = {"query": args.query, "channel": "BM25 + char-3gram TF-IDF (lexical, not semantic)"}
    for pid in projects:
        project, hits = retrieve_for_project(args.query, pid, top_k=8)
        out[pid] = {"project": project, **summarize(hits)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
