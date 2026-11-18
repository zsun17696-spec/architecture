"""强制性条文识别：规则 + 显式标记。"""

from __future__ import annotations

import re

EXPLICIT = re.compile(r"【强制性条文】")
STRONG_POS = ("必须", "严禁")
STRONG_NEG = ("不得",)  # 常与强制并列，单独出现不直接升为 mandatory


def classify(text: str, marked: bool = False) -> tuple[bool, str, float]:
    """返回 (mandatory, rule, confidence)。"""
    if marked or EXPLICIT.search(text):
        return True, "explicit_marker", 0.99
    has_must = any(k in text for k in STRONG_POS)
    if has_must:
        return True, "keyword_必须/严禁", 0.86
    return False, "none", 0.7


def strip_marker(text: str) -> str:
    return EXPLICIT.sub("", text).strip()
