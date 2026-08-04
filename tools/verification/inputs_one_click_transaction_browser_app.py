"""Focused Streamlit browser app for one-click provider transaction parity."""

from __future__ import annotations

import json
import os
import sys
import traceback
from types import SimpleNamespace

import streamlit as st

from inputs_page_modules.auto_design_compute import (
    _LEGACY_AUTO_DESIGN_NAMES,
    run_one_click_auto_design_coordinator,
)
from state_and_helpers import SHARED_DEFAULTS, init_shared_session_state
from tools.verification.recipes.one_click_recipe_defs import (
    build_state,
    find_named_case,
)


IMPLEMENTATION = str(
    os.environ.get("INPUTS_ONE_CLICK_AB_IMPLEMENTATION") or "legacy"
).strip().lower()
RECIPE_NAME = str(
    st.query_params.get("browser_recipe") or "AB_IN_TARGET_BAND"
).strip()


def _provider():
    if IMPLEMENTATION == "legacy":
        import inputs_page_app_contract_bridge as legacy

        source = legacy._BRIDGE_PROVIDER
    elif IMPLEMENTATION == "permanent":
        from inputs_application.one_click_entrypoint import (
            build_one_click_runtime_provider,
        )

        source = build_one_click_runtime_provider(st_module=st)
    else:
        raise RuntimeError(f"Unknown implementation: {IMPLEMENTATION}")
    values = {
        name: getattr(source, name)
        for name in _LEGACY_AUTO_DESIGN_NAMES
    }
    values["copy"] = getattr(source, "copy")
    values["math"] = getattr(source, "math")
    if RECIPE_NAME not in {
        "D_bending_overdesign",
        "E_shear_overdesign",
        "F_combined_overdesign",
    }:
        values["compute_efficiency_tightening_state"] = (
            lambda _state: {
                "classification": "in_band",
                "mode_tightening": None,
                "bottom_tightening": None,
                "shear_tightening": None,
                "geometry_tightening": None,
            }
        )
        values["_one_click_in_band_shear_cleanup_deferral"] = (
            lambda *_args, **_kwargs: {
                "active": False,
                "reason": "browser_transaction_inert_cleanup_fixture",
                "recommendation": None,
                "candidate_eval": None,
            }
        )
    real_post_commit_audit = values["_one_click_post_commit_audit"]

    def _recording_post_commit_audit(updates):
        audit = real_post_commit_audit(updates)
        st.session_state["_browser_post_commit_audit_full"] = audit
        return audit

    values["_one_click_post_commit_audit"] = _recording_post_commit_audit
    if RECIPE_NAME == "AB_COMMIT_ROLLBACK":
        values["_one_click_post_commit_audit"] = (
            lambda updates: {
                "post_commit_matches_intended_updates": False,
                "post_commit_mismatch_keys": sorted(updates),
                "post_commit_mismatch_details": {
                    "fixture": "forced_transaction_rollback"
                },
                "audited_commit_updates": dict(updates),
                "ignored_commit_update_keys": [],
                "has_row_model_updates": False,
                "ignored_row_model_legacy_mirror_keys": [],
                "post_commit_live_worst_util": 0.9263739254603983,
                "post_commit_live_statuses": {
                    "bending": "PASS",
                    "shear": "PASS",
                },
            }
        )
    return SimpleNamespace(**values)


def _seed() -> None:
    init_shared_session_state()
    recipe = find_named_case(RECIPE_NAME)
    if recipe is None:
        raise RuntimeError(f"Unknown browser recipe: {RECIPE_NAME}")
    state = build_state(recipe.get("changes"))
    for key, default in SHARED_DEFAULTS.items():
        st.session_state[key] = state.get(key, default)
    st.session_state.update(
        {
            "page_slug": "inputs",
            "_dev_mode": False,
            "_auto_design_auto_invoke": True,
            "_auto_design_requested_at_ts": 1.0,
            "_auto_design_request_source": (
                f"browser_transaction:{IMPLEMENTATION}"
            ),
            "auto_design_request_source": (
                f"browser_transaction:{IMPLEMENTATION}"
            ),
            "auto_design_invoke_pending": True,
            "auto_design_invoke_set": True,
            "auto_design_latch_owner": "handle_auto_design",
            "_solver_running": True,
        }
    )


if "_one_click_browser_transaction_result" not in st.session_state:
    _seed()
    try:
        if IMPLEMENTATION == "production":
            from inputs_application.one_click_entrypoint import (
                run_one_click_auto_design as production_one_click,
            )

            result = production_one_click(
                trigger_fingerprint=("browser_transaction", RECIPE_NAME),
                entry_source="inputs_handle_auto_design",
                st_module=st,
                sys_module=sys,
            )
        else:
            result = run_one_click_auto_design_coordinator(
                _provider(),
                st,
                sys,
                trigger_fingerprint=("browser_transaction", RECIPE_NAME),
                entry_source="inputs_handle_auto_design",
            )
        error = None
    except Exception as exc:
        result = {}
        error = traceback.format_exc()
    st.session_state["_one_click_browser_transaction_result"] = result
    st.session_state["_one_click_browser_transaction_error"] = error

result = dict(
    st.session_state.get("_one_click_browser_transaction_result") or {}
)
feedback = dict(st.session_state.get("_one_click_run_feedback") or {})
shared_subset = {
    key: st.session_state.get(key)
    for key in (
        "b",
        "D",
        "bot1_count",
        "bot2_count",
        "db_bot_1",
        "db_bot_2",
        "lig_d",
        "lig_legs",
        "s_lig",
    )
}
payload = {
    "probe_phase": "post_page_render",
    "browser_probe_phase": "post_page_render",
    "pre_page_render_lightweight": False,
    "implementation": IMPLEMENTATION,
    "recipe": RECIPE_NAME,
    "solver_result": result,
    "one_click_feedback": feedback,
    "shared_subset": shared_subset,
    "transaction_error": st.session_state.get(
        "_one_click_browser_transaction_error"
    ),
    "post_commit_audit": st.session_state.get(
        "_browser_post_commit_audit_full"
    ),
    "session_contract": {
        "invoke_present": "_auto_design_auto_invoke" in st.session_state,
        "invoke_pending": st.session_state.get(
            "auto_design_invoke_pending"
        ),
        "invoke_consumed": st.session_state.get(
            "auto_design_invoke_consumed"
        ),
        "solver_running": st.session_state.get("_solver_running"),
        "compute_in_progress": st.session_state.get(
            "_compute_in_progress"
        ),
        "applying_auto_design": st.session_state.get(
            "_applying_auto_design"
        ),
        "last_run_status": st.session_state.get(
            "_one_click_last_run_status"
        ),
        "last_stop_reason": st.session_state.get(
            "_one_click_last_stop_reason"
        ),
    },
}
st.text_area(
    "Browser state",
    value=json.dumps(payload, sort_keys=True, default=str),
    height=420,
)
