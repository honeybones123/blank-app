"""Best-effort debug output helpers for the Inputs page modules."""

from __future__ import annotations

from typing import Any


def safe_debug_print(*args: Any, **kwargs: Any) -> None:
    """Emit diagnostic output without letting console handle failures break Streamlit."""
    try:
        print(*args, **kwargs)
    except Exception:
        return
