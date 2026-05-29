from __future__ import annotations

from typing import Any


def status_is_acceptable(value: Any) -> bool:
    return str(value or "").strip().upper() in {"PASS", "INFO", "NEAR LIMIT", "-", "—"}
