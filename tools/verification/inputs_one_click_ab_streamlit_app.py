"""Verifier-only Streamlit entrypoint for legacy/permanent one-click A/B runs."""

from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

import streamlit as st

from tools.verification.recipes import one_click_recipe_defs

import inputs_page_route_coordinators as route
import inputs_page_modules.auto_design_compute as auto_design_compute


IMPLEMENTATION = str(
    os.environ.get("INPUTS_ONE_CLICK_AB_IMPLEMENTATION") or "legacy"
).strip().lower()
MAX_STEPS = max(
    1,
    int(os.environ.get("INPUTS_ONE_CLICK_AB_MAX_STEPS") or "1"),
)

_original_solver = auto_design_compute._solve_one_click_to_target


def _bounded_solver(state: dict, **kwargs):
    kwargs["max_steps"] = min(
        int(kwargs.get("max_steps") or MAX_STEPS),
        MAX_STEPS,
    )
    return _original_solver(state, **kwargs)


auto_design_compute._solve_one_click_to_target = _bounded_solver

if not one_click_recipe_defs.find_named_case("AB_NO_BOTTOM_BARS"):
    one_click_recipe_defs.REGRESSION_CASES.append(
        {
            "name": "AB_NO_BOTTOM_BARS",
            "changes": {
                **one_click_recipe_defs._manual_actions(100.0, 0.0),
                "bot1_count": 0,
                "bot2_count": 0,
                "bot_row_count": 1,
                "bot_row_1_bars": 0,
                "bot_row_2_bars": 0,
                "nb_bot": 0,
                "bot_entry": 0.0,
            },
            "expected_starting_condition": "No bottom bars resolved.",
        }
    )
if not one_click_recipe_defs.find_named_case("AB_INVALID_GEOMETRY"):
    one_click_recipe_defs.REGRESSION_CASES.append(
        {
            "name": "AB_INVALID_GEOMETRY",
            "changes": {
                **one_click_recipe_defs._manual_actions(100.0, 50.0),
                "b": 0.0,
                "bw": 0.0,
                "D": 0.0,
            },
            "expected_starting_condition": "Canonical geometry is invalid.",
        }
    )
if not one_click_recipe_defs.find_named_case("AB_IN_TARGET_BAND"):
    one_click_recipe_defs.REGRESSION_CASES.append(
        {
            "name": "AB_IN_TARGET_BAND",
            "changes": one_click_recipe_defs._manual_actions(98.0, 0.0),
            "expected_starting_condition": (
                "Bending utilisation begins in the balanced target band."
            ),
        }
    )

if IMPLEMENTATION not in {"legacy", "permanent"}:
    raise RuntimeError(
        "INPUTS_ONE_CLICK_AB_IMPLEMENTATION must be legacy or permanent"
    )


def _transaction_provider():
    if IMPLEMENTATION == "legacy":
        import inputs_page_app_contract_bridge as legacy

        source = legacy._BRIDGE_PROVIDER
    else:
        from inputs_application.one_click_entrypoint import (
            build_one_click_runtime_provider,
        )

        source = build_one_click_runtime_provider(st_module=st)
    values = {
        name: getattr(source, name)
        for name in auto_design_compute._LEGACY_AUTO_DESIGN_NAMES
    }
    values["copy"] = getattr(source, "copy")
    values["math"] = getattr(source, "math")
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
            "reason": "browser_ab_inert_cleanup_fixture",
            "recommendation": None,
            "candidate_eval": None,
        }
    )
    return SimpleNamespace(**values)


def _run_ab_one_click(**kwargs):
    return auto_design_compute.run_one_click_auto_design_coordinator(
        _transaction_provider(),
        st,
        sys,
        **kwargs,
    )


route.run_one_click_auto_design = _run_ab_one_click


_original_setup = route.render_inputs_page_setup_current_coordinator


def _seed_ab_invocation(ss: dict) -> None:
    auto_invoke_requested = str(
        os.environ.get("INPUTS_ONE_CLICK_AB_AUTO_INVOKE") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    recipe_applied = bool(ss.get("_browser_recipe_applied_state"))
    token = (
        str(st.query_params.get("browser_recipe") or ""),
        IMPLEMENTATION,
    )
    if (
        auto_invoke_requested
        and recipe_applied
        and ss.get("_one_click_ab_invoke_token") != token
    ):
        ss["_one_click_ab_invoke_token"] = token
        ss[route.AUTO_DESIGN_AUTO_INVOKE_KEY] = True
        ss[route.AUTO_DESIGN_REQUEST_TS_KEY] = time.time()
        ss[route.AUTO_DESIGN_REQUEST_SOURCE_KEY] = (
            f"browser_ab:{IMPLEMENTATION}"
        )
        ss["auto_design_request_source"] = (
            f"browser_ab:{IMPLEMENTATION}"
        )
        ss["auto_design_invoke_pending"] = True
        ss["auto_design_invoke_set"] = True
        ss["_one_click_ab_implementation"] = IMPLEMENTATION


def _ab_setup(*, ss: dict):
    _seed_ab_invocation(ss)
    result = _original_setup(ss=ss)
    return result


route.render_inputs_page_setup_current_coordinator = _ab_setup

import inputs_page  # noqa: E402

inputs_page.render_inputs_page_setup_current_coordinator = _ab_setup
_original_render_inputs = inputs_page.render_inputs


def _ab_render_inputs():
    _seed_ab_invocation(st.session_state)
    return _original_render_inputs()


inputs_page.render_inputs = _ab_render_inputs

import app  # noqa: E402


if __name__ == "__main__":
    app.main()
