"""Lexical dual channel: BM25 + character 3-gram TF-IDF cosine.

This is not a semantic embedding index.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np

try:
    import jieba
except ImportError:  # pragma: no cover
    jieba = None

from rank_bm25 import BM25Okapi


def tokenize(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if jieba is not None:
        return [t for t in jieba.lcut(text) if t.strip()]
    return [text[i : i + 2] for i in range(max(len(text) - 1, 0))]


def char_ngrams(text: str, n: int = 3) -> list[str]:
    s = (text or "").replace(" ", "")
    if len(s) < n:
        return [s] if s else []
    return [s[i : i + n] for i in range(len(s) - n + 1)]


def _norm(vec: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(vec))
    if n == 0:
        return vec
    return vec / n


def fingerprint(chunks: Iterable[dict[str, Any]]) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(f"{c['id']}\t{c.get('text', '')}\n".encode("utf-8"))
    return h.hexdigest()


@dataclass
class LexicalIndex:
    """In-memory BM25 + char 3-gram TF-IDF. Rebuild only when text fingerprint changes."""

    text_fp: str = ""
    ids: list[int] = field(default_factory=list)
    _bm25: BM25Okapi | None = None
    _tfidf: np.ndarray | None = None
    _idf: dict[str, float] = field(default_factory=dict)
    _vocab: dict[str, int] = field(default_factory=dict)

    def needs_rebuild(self, chunks: list[dict[str, Any]]) -> bool:
        return fingerprint(chunks) != self.text_fp

    def rebuild(self, chunks: list[dict[str, Any]]) -> None:
        ordered = sorted(chunks, key=lambda c: int(c["id"]))
        self.ids = [int(c["id"]) for c in ordered]
        texts = [c.get("text") or "" for c in ordered]
        tokenized = [tokenize(t) or ["_"] for t in texts]
        self._bm25 = BM25Okapi(tokenized)
        grams = [char_ngrams(t) for t in texts]
        df: dict[str, int] = {}
        for g in grams:
            for term in set(g):
                df[term] = df.get(term, 0) + 1
        n_docs = max(len(grams), 1)
        vocab = {term: i for i, term in enumerate(sorted(df))}
        idf = {term: math.log((n_docs + 1) / (cnt + 1)) + 1.0 for term, cnt in df.items()}
        mat = np.zeros((len(grams), max(len(vocab), 1)), dtype=np.float64)
        for i, g in enumerate(grams):
            tf: dict[str, int] = {}
            for term in g:
                tf[term] = tf.get(term, 0) + 1
            for term, cnt in tf.items():
                j = vocab[term]
                mat[i, j] = cnt * idf[term]
            mat[i] = _norm(mat[i])
        self._tfidf = mat
        self._idf = idf
        self._vocab = vocab
        self.text_fp = fingerprint(chunks)

    def _query_tfidf(self, query: str) -> np.ndarray:
        dim = self._tfidf.shape[1] if self._tfidf is not None else 1
        vec = np.zeros(dim, dtype=np.float64)
        if not self._vocab:
            return vec
        for term in char_ngrams(query):
            j = self._vocab.get(term)
            if j is None:
                continue
            vec[j] += self._idf.get(term, 0.0)
        return _norm(vec)

    def scores(self, query: str) -> dict[int, tuple[float, float]]:
        """id -> (bm25_raw, tfidf_cosine)."""
        if self._bm25 is None or self._tfidf is None:
            return {}
        bm = np.array(self._bm25.get_scores(tokenize(query) or ["_"]), dtype=np.float64)
        mx = float(bm.max()) if bm.size else 0.0
        bm_n = bm / mx if mx > 0 else bm
        qv = self._query_tfidf(query)
        cos = self._tfidf @ qv
        return {i: (float(bm_n[k]), float(cos[k])) for k, i in enumerate(self.ids)}


_INDEX = LexicalIndex()


def get_index(chunks: list[dict[str, Any]]) -> LexicalIndex:
    if _INDEX.needs_rebuild(chunks) or not _INDEX.ids:
        _INDEX.rebuild(chunks)
    return _INDEX
