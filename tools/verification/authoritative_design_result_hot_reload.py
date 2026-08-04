"""Focused regression for Streamlit hot-reload result identity rebinding."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.design_result_store import AuthoritativeDesignResultStore
from design_brain.authority import AuthoritativeDesignResult


def main() -> int:
    original = AuthoritativeDesignResult(
        engineering_hash="hot-reload-hash",
        governing_family="bending",
        selected_updates={"b": 450.0},
    )
    payload = original.to_dict()

    stale_type = type(
        "AuthoritativeDesignResult",
        (),
        {
            "__module__": "design_brain.authority",
            "to_dict": lambda self: dict(payload),
        },
    )
    stale = stale_type()
    state: dict = {}
    store = AuthoritativeDesignResultStore(state)
    rebound = store.store(stale)  # type: ignore[arg-type]
    assert isinstance(rebound, AuthoritativeDesignResult)
    assert rebound.to_dict() == payload
    assert store.current() is rebound

    try:
        store.store(dict(payload))  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("plain dictionaries must remain rejected")

    print("authoritative_design_result_hot_reload: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
