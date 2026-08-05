"""V2-owned production entrypoint for the Inputs one-click action.

The old one-click solver was a second Design Brain implementation.  V2 now
previews and publishes its approved candidate automatically, so this entry
point only asks the authoritative V2 coordinator to refresh and reports the
published result to the surrounding UI compatibility code.
"""

from __future__ import annotations

import importlib
from typing import Any

import streamlit as st



def build_one_click_runtime_provider(
    *,
    st_module: Any = st,
) -> Any:
    # Retain the factory for callers that still inspect the old boundary, but
    # deliberately return a neutral marker instead of constructing V1's
    # retired candidate-search graph.
    del st_module
    return {"source": "inputs_v2", "automatic_publication": True}


def run_one_click_auto_design(
    *,
    trigger_fingerprint: tuple | None = None,
    entry_source: str = "inputs_handle_auto_design",
    st_module: Any = st,
    sys_module: Any = None,
) -> dict:
    """Refresh the automatic V2 publication without invoking a second solver."""
    del trigger_fingerprint, entry_source, sys_module
    try:
        # Resolve the coordinator dynamically.  A top-level/static import here
        # would recreate the page-runtime -> one-click -> setup cycle that the
        # V2 boundary is intended to remove.
        setup_module = importlib.import_module("inputs_application.page_runtime.setup")
        result = setup_module.refresh_inputs_design_brain_result()
        if result is None:
            return {
                "status": "awaiting_inputs",
                "source": "inputs_v2",
                "steps": [],
                "recommendation_result": None,
                "recommendation": None,
            }
        publication = dict(getattr(result, "final_publication", {}) or {})
        return {
            "status": "ready",
            "source": "inputs_v2",
            "steps": [],
            "recommendation_result": dict(
                publication.get("apply_payload") or {}
            ),
            "recommendation": None,
            "publication": publication,
            "input_revision": int(getattr(result, "source_input_revision", 0) or 0),
        }
    except Exception as exc:  # pragma: no cover - surfaced by the page shell
        return {
            "status": "failed",
            "source": "inputs_v2",
            "steps": [],
            "recommendation_result": None,
            "recommendation": None,
            "error": str(exc),
        }


__all__ = [
    "build_one_click_runtime_provider",
    "run_one_click_auto_design",
]
