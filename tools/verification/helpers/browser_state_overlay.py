"""Deterministic reconciliation for Streamlit browser-verifier probes.

The outer app and the Inputs workspace fragment publish separate hidden probe
widgets.  DOM order is not an authority boundary, so the verifier selects the
most complete outer state and the newest explicitly-fresh fragment overlay.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _integer(value: Any, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _outer_score(candidate: Mapping[str, Any], position: int) -> tuple[int, ...]:
    phase = str(
        candidate.get("browser_probe_phase")
        or candidate.get("probe_phase")
        or ""
    ).strip().lower()
    return (
        1 if phase in {"post_page_render", "final"} else 0,
        1 if isinstance(candidate.get("summary_state_probe"), Mapping) else 0,
        1 if isinstance(candidate.get("final_publication_verifier_payload"), Mapping) else 0,
        _integer(candidate.get("results_version")),
        position,
    )


def select_browser_state_candidate(
    candidates: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Select the strongest outer probe without relying on DOM ordering."""

    values = [dict(item) for item in candidates if isinstance(item, Mapping)]
    if not values:
        return {}
    return max(
        enumerate(values),
        key=lambda item: _outer_score(item[1], item[0]),
    )[1]


def _overlay_score(
    overlay: Mapping[str, Any],
    container: Mapping[str, Any],
    position: int,
) -> tuple[int, ...]:
    return (
        1 if overlay.get("fragment_fresh") is True else 0,
        _integer(container.get("result_source_input_revision")),
        _integer(container.get("authoritative_revision")),
        _integer(container.get("workspace_revision")),
        _integer(container.get("fragment_emitted_at_ms")),
        position,
    )


def select_fragment_browser_state_overlay(
    candidates: Iterable[Mapping[str, Any]],
    *,
    base_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the newest explicitly-fresh Inputs fragment overlay."""

    del base_state  # Reserved for future identity matching; no implicit merge.
    overlays: list[tuple[dict[str, Any], dict[str, Any], int]] = []
    for position, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            continue
        raw = candidate.get("browser_state_overlay")
        if not isinstance(raw, Mapping):
            continue
        overlay = dict(raw)
        if overlay.get("fragment_fresh") is not True:
            continue
        overlays.append((overlay, dict(candidate), position))
    if not overlays:
        return {}
    return max(
        overlays,
        key=lambda item: _overlay_score(item[0], item[1], item[2]),
    )[0]


def merge_fragment_browser_state_overlay(
    base_state: Mapping[str, Any],
    overlay: Mapping[str, Any],
) -> dict[str, Any]:
    """Overlay fragment-owned top-level evidence onto the outer probe."""

    merged = dict(base_state or {})
    for key, value in dict(overlay or {}).items():
        if key == "fragment_fresh":
            continue
        merged[key] = value
    merged["fragment_fresh"] = bool(overlay.get("fragment_fresh"))
    return merged


__all__ = [
    "merge_fragment_browser_state_overlay",
    "select_browser_state_candidate",
    "select_fragment_browser_state_overlay",
]
