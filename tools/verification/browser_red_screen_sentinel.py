"""Reusable browser-live red-screen sentinel.

Live browser verifiers should fail fast when the rendered app contains a Python
traceback, Streamlit runtime error, stale blocker shell, or family-contract
violation card.  This module is deliberately data-only so it can be reused by
family, workflow, and visual gates without importing product code.
"""

from __future__ import annotations

import re
from typing import Any


FORBIDDEN_LIVE_TEXT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("python_traceback", re.compile(r"Traceback:|Traceback \(most recent call last\)", re.IGNORECASE)),
    ("name_error", re.compile(r"\bNameError:\b|name ['\"]_[A-Za-z0-9_]+['\"] is not defined", re.IGNORECASE)),
    ("unbound_local_error", re.compile(r"\bUnboundLocalError:\b", re.IGNORECASE)),
    ("streamlit_duplicate_key", re.compile(r"StreamlitDuplicateElementKey|multiple elements with the same key", re.IGNORECASE)),
    ("streamlit_runtime_error", re.compile(r"streamlit\.errors\.|\bRuntimeError:\b", re.IGNORECASE)),
    ("family_contract_violation_card", re.compile(r"Design Guide family contract violation", re.IGNORECASE)),
    ("stale_primary_payload_blocker", re.compile(r"stale_primary_design_guide_payload", re.IGNORECASE)),
)


def _walk(value: Any) -> list[Any]:
    rows: list[Any] = [value]
    if isinstance(value, dict):
        for item in value.values():
            rows.extend(_walk(item))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_walk(item))
    return rows


def browser_red_screen_findings(value: Any) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in _walk(value):
        if not isinstance(item, (str, int, float, bool)):
            continue
        text = str(item)
        if not text:
            continue
        for label, pattern in FORBIDDEN_LIVE_TEXT_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            excerpt_start = max(0, match.start() - 90)
            excerpt_end = min(len(text), match.end() + 160)
            excerpt = " ".join(text[excerpt_start:excerpt_end].split())
            key = (label, excerpt)
            if key in seen:
                continue
            seen.add(key)
            findings.append({"reason": label, "excerpt": excerpt})
    return findings


def browser_red_screen_passed(value: Any) -> bool:
    return not browser_red_screen_findings(value)
