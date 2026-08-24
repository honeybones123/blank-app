"""Inputs-page developer session debug sidebar rendering."""

from __future__ import annotations

import json
from typing import Any


_DEBUG_KEYS = (
    "page_slug",
    "_inputs_workspace_revision",
    "_inputs_last_commit_timings_ms",
    "_inputs_workspace_section_timings_ms",
    "_inputs_design_brain_deferred_invocation_count",
    "_inputs_engineering_compute_count_by_revision",
    "_inputs_engineering_input_transaction_probe",
    "_inputs_authoritative_design_result_runtime_probe",
    "_inputs_design_brain_job_probe",
    "_inputs_design_guide_fragment_state_v1",
    "actions_source",
    "inputs_actions_source",
    "loads_edit_mode",
    "load_Mstar_proxy",
    "load_Vstar_proxy",
    "load_Nstar_proxy",
    "uls_Mstar",
    "uls_Vstar",
    "uls_Nstar",
    "Mu_star",
    "Mu_star_kNm",
    "Vu_star",
    "final_shear_truth_bundle_complete",
    "shear_truth_status",
    "final_shear_truth_resolved",
    "final_shear_truth_failure_reason",
    "published_result_spacing_mm",
    "published_result_spacing_meaning",
    "_final_shear_truth_normalized_source",
    "_final_shear_truth_normalized_latest",
    "sfd_Mmax_abs_kNm",
    "sfd_Vmax_abs_kN",
)


def render_inputs_dev_session_debug_sidebar(
    *,
    sidebar_module: Any,
    state: dict,
    ss: dict,
    design_guide_sidebar_debug_toggle_key: str,
) -> None:
    sidebar_module.sidebar.toggle(
        "Design Guide Debug",
        value=False,
        key=design_guide_sidebar_debug_toggle_key,
    )

    debug_mode = sidebar_module.sidebar.checkbox(
        "Debug session state",
        key=f"debug_state_toggle_{ss.get('page_slug','page')}",
    )
    if debug_mode:
        sidebar_module.sidebar.markdown("### Debug session state")
        sidebar_module.sidebar.json({key: state.get(key) for key in _DEBUG_KEYS})
        sidebar_module.sidebar.markdown("#### Inputs summary state debug")
        sidebar_module.sidebar.code(
            json.dumps(
                dict(state.get("_inputs_summary_debug_bundle") or {}),
                indent=2,
                default=str,
            ),
        )


__all__ = ["render_inputs_dev_session_debug_sidebar"]
