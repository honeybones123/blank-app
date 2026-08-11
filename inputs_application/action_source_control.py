"""Shared action-source control for Beam Inputs and Load Analysis.

The existing ``actions_mode`` and ``actions_source`` fields remain the only
engineering authority.  Page widget keys are synchronized projections so the
two pages cannot retain contradictory selections.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any, Callable


MANUAL_ACTIONS_SOURCE = "Manual design actions (inputs below)"
LOAD_ANALYSIS_ACTIONS_SOURCE = "Teaching SFD/BMD page (|M|max, |V|max)"

INPUTS_ACTION_SOURCE_TOGGLE_KEY = "inputs_action_source_toggle"
LOAD_ANALYSIS_ACTION_SOURCE_TOGGLE_KEY = "design_action_source_toggle"
_ACTION_SOURCE_WIDGET_KEYS = (
    INPUTS_ACTION_SOURCE_TOGGLE_KEY,
    LOAD_ANALYSIS_ACTION_SOURCE_TOGGLE_KEY,
    # Compatibility projection retained for consumers that have not yet
    # migrated from the former Inputs information-panel toggle.
    "inputs_use_calculated_actions",
)


def uses_load_analysis_actions(state: MutableMapping[str, Any]) -> bool:
    """Resolve the canonical source without consulting page widget mirrors."""

    mode = str(state.get("actions_mode") or "").strip().lower()
    if mode in {"manual", "design"}:
        return mode == "design"
    source = str(state.get("actions_source") or "").strip()
    return source in {
        LOAD_ANALYSIS_ACTIONS_SOURCE,
        "Calculated design actions (from SFD/BMD)",
    }


def seed_action_source_toggle(
    state: MutableMapping[str, Any],
    widget_key: str,
) -> bool:
    """Project the canonical source into one not-yet-rendered widget key."""

    selected = uses_load_analysis_actions(state)
    state[widget_key] = selected
    return selected


def commit_action_source_toggle(
    state: MutableMapping[str, Any],
    widget_key: str,
) -> bool:
    """Commit one page toggle and synchronize every non-authoritative mirror."""

    selected = bool(state.get(widget_key, False))
    mode = "design" if selected else "manual"
    source = (
        LOAD_ANALYSIS_ACTIONS_SOURCE if selected else MANUAL_ACTIONS_SOURCE
    )
    changed = (
        str(state.get("actions_mode") or "").strip().lower() != mode
        or str(state.get("actions_source") or "").strip() != source
    )
    state["actions_mode"] = mode
    state["actions_source"] = source
    for mirror_key in _ACTION_SOURCE_WIDGET_KEYS:
        if mirror_key != widget_key:
            state[mirror_key] = selected
    if changed:
        state["inputs_dirty"] = True
        state["_inputs_dirty"] = True
        state["_force_design_action_widget_hydrate"] = True
    return changed


def load_analysis_action_projection(
    *,
    draft: Mapping[str, Any] | None,
    results: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the derived ULS/SLS aliases consumed by Beam Inputs.

    The projection deliberately excludes every manual action field.  Switching
    back to Beam Inputs therefore restores the user's previous manual actions
    instead of exposing a copied Load Analysis value.
    """

    draft_values = dict(draft or {})
    result_values = dict(results or {})
    source_policy = str(
        draft_values.get("design_actions_source_selector") or "max"
    ).strip().lower()
    use_section = source_policy == "section" and any(
        key in result_values
        for key in (
            "design_M_uls_kNm",
            "design_M_uls_kNm_signed",
            "design_V_uls_kN",
            "design_M_sls_kNm",
            "design_M_sls_kNm_signed",
            "design_V_sls_kN",
        )
    )
    projection = {
        "design_actions_source": "section" if use_section else "max",
        "sfd_Mmax_abs_kNm": float(
            result_values.get("sfd_Mmax_abs_kNm", 0.0) or 0.0
        ),
        "sfd_Vmax_abs_kN": float(
            result_values.get("sfd_Vmax_abs_kN", 0.0) or 0.0
        ),
        "sfd_Msls_max_kNm": float(
            result_values.get("sfd_Msls_max_kNm", 0.0) or 0.0
        ),
        "sfd_Vsls_max_kN": float(
            result_values.get("sfd_Vsls_max_kN", 0.0) or 0.0
        ),
        "M_pos_max_uls_kNm": float(
            result_values.get("M_pos_max_uls_kNm", 0.0) or 0.0
        ),
        "M_neg_min_uls_kNm": float(
            result_values.get("M_neg_min_uls_kNm", 0.0) or 0.0
        ),
        "M_pos_max_sls_kNm": float(
            result_values.get("M_pos_max_sls_kNm", 0.0) or 0.0
        ),
        "M_neg_min_sls_kNm": float(
            result_values.get("M_neg_min_sls_kNm", 0.0) or 0.0
        ),
        # Load Analysis currently resolves beam bending and shear only. Keep
        # its zero axial result separate from the saved manual axial field.
        "Nu_star": 0.0,
    }
    if use_section:
        for key in (
            "design_M_uls_kNm",
            "design_M_uls_kNm_signed",
            "design_V_uls_kN",
            "design_M_sls_kNm",
            "design_M_sls_kNm_signed",
            "design_V_sls_kN",
        ):
            projection[key] = float(result_values.get(key, 0.0) or 0.0)
    return projection


def synchronize_load_analysis_actions_for_inputs(
    state: MutableMapping[str, Any],
    *,
    draft: Mapping[str, Any] | None,
    results: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Synchronize only the derived Load Analysis projection when selected."""

    if not uses_load_analysis_actions(state):
        return ()
    projection = load_analysis_action_projection(draft=draft, results=results)
    changed: list[str] = []
    for key, value in projection.items():
        if state.get(key) != value:
            state[key] = value
            changed.append(key)
    if changed:
        state["inputs_dirty"] = True
        state["_inputs_dirty"] = True
        state["_force_design_action_widget_hydrate"] = True
    return tuple(sorted(changed))


def render_action_source_toggle(
    st_module: Any,
    *,
    widget_key: str,
    before_commit: Callable[[], Any] | None = None,
    after_commit: Callable[[bool], Any] | None = None,
) -> bool:
    """Render the same synchronized action-source control on either page."""

    seed_action_source_toggle(st_module.session_state, widget_key)

    def _commit() -> None:
        if before_commit is not None:
            before_commit()
        commit_action_source_toggle(st_module.session_state, widget_key)
        if after_commit is not None:
            after_commit(bool(st_module.session_state.get(widget_key, False)))

    value = st_module.toggle(
        "Use Load Analysis actions for Beam Inputs",
        key=widget_key,
        on_change=_commit,
        help=(
            "When enabled, Beam Inputs and the general calculation pages use "
            "the ULS and SLS actions calculated by Load Analysis. When disabled, "
            "they use the actions entered on Beam Inputs. Load Analysis itself "
            "always uses its own page loads."
        ),
    )
    st_module.caption(
        "Beam Inputs action source: "
        + ("Load Analysis" if value else "Beam Inputs")
    )
    return bool(value)


__all__ = [
    "INPUTS_ACTION_SOURCE_TOGGLE_KEY",
    "LOAD_ANALYSIS_ACTIONS_SOURCE",
    "LOAD_ANALYSIS_ACTION_SOURCE_TOGGLE_KEY",
    "MANUAL_ACTIONS_SOURCE",
    "commit_action_source_toggle",
    "load_analysis_action_projection",
    "render_action_source_toggle",
    "seed_action_source_toggle",
    "synchronize_load_analysis_actions_for_inputs",
    "uses_load_analysis_actions",
]
