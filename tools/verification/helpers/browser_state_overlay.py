"""Shared selection and merge policy for fragment browser verification state."""

from __future__ import annotations

from typing import Any


def _as_int(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def browser_state_freshness_key(
    state: dict[str, Any],
    *,
    candidate_index: int = 0,
) -> tuple[int, int, int, int, int, int]:
    """Rank outer browser probes without relying on DOM selector order."""

    timing = (
        dict(state.get("render_timing_probe") or {})
        if isinstance(state.get("render_timing_probe"), dict)
        else {}
    )
    return (
        int(
            str(state.get("browser_probe_phase") or "").strip()
            == "post_page_render"
        ),
        int(not bool(state.get("pre_page_render_lightweight"))),
        _as_int(timing.get("rerun_seq")),
        _as_int(timing.get("event_count")),
        _as_int(state.get("results_version")),
        -int(candidate_index),
    )


def select_browser_state_candidate(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return the freshest outer browser-state candidate."""

    if not candidates:
        return {}
    return max(
        enumerate(candidates),
        key=lambda row: browser_state_freshness_key(
            row[1],
            candidate_index=row[0],
        ),
    )[1]


def select_fragment_browser_state_overlay(
    candidates: list[dict[str, Any]],
    *,
    base_state: dict[str, Any],
) -> dict[str, Any]:
    """Return a fragment overlay only when it is not older than the base.

    Streamlit can briefly retain the previous fragment textarea while the
    outer post-render Browser-state probe has already advanced.  Treating the
    mere ``fragment_fresh`` flag as globally fresh lets that old textarea
    overwrite newly committed engineering values.  The fragment emission time
    is therefore compared with the outer render start before merging.
    """

    overlay_candidates: list[tuple[tuple[int, int, int, int], dict[str, Any]]] = []
    for candidate_index, payload in enumerate(candidates):
        overlay = payload.get("browser_state_overlay")
        if not (
            isinstance(overlay, dict)
            and overlay.get("fragment_fresh")
        ):
            continue
        overlay_candidates.append(
            (
                (
                    _as_int(payload.get("fragment_emitted_at_ms")),
                    _as_int(payload.get("workspace_revision")),
                    _as_int(payload.get("workspace_fragment_render_count")),
                    -candidate_index,
                ),
                dict(overlay),
            )
        )
    if not overlay_candidates:
        return {}

    overlay_key, overlay = max(overlay_candidates, key=lambda row: row[0])
    fragment_emitted_at_ms = overlay_key[0]
    timing = (
        dict(base_state.get("render_timing_probe") or {})
        if isinstance(base_state.get("render_timing_probe"), dict)
        else {}
    )
    base_started_at_ms = _as_int(timing.get("started_at_ms"))
    if (
        fragment_emitted_at_ms >= 0
        and base_started_at_ms >= 0
        and fragment_emitted_at_ms < base_started_at_ms
    ):
        return {}
    return overlay


def merge_fragment_browser_state_overlay(
    state: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    """Recursively overlay fields without erasing omitted nested authority.

    Fragment probes often refresh one portion of a nested publication map.
    A shallow ``{**state, **overlay}`` loses still-current family/outcome
    fields from the outer post-render probe. Recursive mapping merge preserves
    omitted fields while explicit scalar values, including ``False`` and
    ``0``, remain authoritative.
    """

    merged = dict(state)
    for key, overlay_value in dict(overlay).items():
        state_value = merged.get(key)
        if isinstance(state_value, dict) and isinstance(overlay_value, dict):
            merged[key] = merge_fragment_browser_state_overlay(
                state_value,
                overlay_value,
            )
        else:
            merged[key] = overlay_value
    return merged


__all__ = [
    "browser_state_freshness_key",
    "merge_fragment_browser_state_overlay",
    "select_browser_state_candidate",
    "select_fragment_browser_state_overlay",
]
