"""Prove application-owned one-click post-commit audit exact parity."""

from __future__ import annotations

import contextlib
import copy
import io
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import streamlit as st

        from inputs_application.guidance_entrypoint import (
            build_guidance_entrypoint_runtime,
        )
        from inputs_application.one_click_commit_policy import (
            one_click_post_commit_audit,
        )
        from inputs_application.one_click_runtime_provider import (
            build_partial_one_click_runtime_provider,
        )
        from inputs_page_modules.app_bridge import post_commit_audit as legacy

    shared_defaults = {
        "b": 300.0,
        "D": 600.0,
        "lig_d": 10,
        "bot_row_1_count": 4,
        "bot1_count": 4,
        "Ast_bot": 2010.0,
    }
    snapshot = {
        **shared_defaults,
        "D": 650.0,
        "Mu_star": 400.0,
        "Vu_star": 150.0,
    }
    summary = {
        **snapshot,
        "d": 585.0,
        "db_bot_1": 24,
        "db_bot_2": 0,
        "bot2_count": 0,
        "lig_legs": 2,
        "s_lig": 200,
    }

    def shared_state_snapshot() -> dict:
        return copy.deepcopy(snapshot)

    def guidance_state_snapshot(state: dict | None) -> dict:
        return {"guided": True, **copy.deepcopy(dict(state or {}))}

    def build_canonical_design_state_pack(state: dict) -> dict:
        return {"packed": True, **copy.deepcopy(state)}

    def collect_design_overview(state: dict, **_kwargs) -> dict:
        return {
            "worst_util": 0.82 if state.get("d") else 0.81,
            "statuses": {"bending": "PASS", "shear": "PASS"},
        }

    def evaluate_candidate_full(
        state: dict,
        *,
        source: str,
        label: str,
        action_type: str,
        updates: dict,
    ) -> dict:
        del label, action_type, updates
        util_by_source = {
            "one_click_post_commit_audit_shared_eval": 0.83,
            "one_click_post_commit_audit_shared_packed_eval": 0.84,
            "one_click_post_commit_audit_summary_eval": 0.85,
            "one_click_post_commit_audit": 0.86,
        }
        return {
            "state": copy.deepcopy(state),
            "overview": {
                "worst_util": util_by_source[source],
                "statuses": {"bending": "PASS", "shear": "PASS"},
            },
        }

    dependencies = {
        "SHARED_DEFAULTS": shared_defaults,
        "_shared_state_snapshot": shared_state_snapshot,
        "_guidance_state_snapshot": guidance_state_snapshot,
        "_build_canonical_design_state_pack": (
            build_canonical_design_state_pack
        ),
        "_collect_design_overview": collect_design_overview,
        "evaluate_candidate_full": evaluate_candidate_full,
        "_resolved_inputs_summary_state": lambda: (
            copy.deepcopy(summary),
            {"mode": "test"},
        ),
    }
    originals = {
        name: getattr(legacy, name, None)
        for name in dependencies
    }
    try:
        for name, value in dependencies.items():
            setattr(legacy, name, value)
        cases = (
            {"D": 650.0, "lig_d": 10},
            {
                "bot_row_1_count": 4,
                "bot1_count": 99,
                "Ast_bot": 9999.0,
                "_diagnostic": True,
            },
            {"D": 651.0, "unknown": "ignored"},
            {},
        )
        for intended in cases:
            expected = legacy._one_click_post_commit_audit(intended)
            actual = one_click_post_commit_audit(
                intended,
                shared_defaults=shared_defaults,
                shared_state_snapshot=shared_state_snapshot,
                guidance_state_snapshot=guidance_state_snapshot,
                build_canonical_design_state_pack=(
                    build_canonical_design_state_pack
                ),
                collect_design_overview=collect_design_overview,
                evaluate_candidate_full=evaluate_candidate_full,
                resolve_summary_state=lambda: copy.deepcopy(summary),
            )
            assert actual == expected, (intended, actual, expected)
    finally:
        for name, value in originals.items():
            if value is None:
                delattr(legacy, name)
            else:
                setattr(legacy, name, value)

    guidance = build_guidance_entrypoint_runtime(
        st_module=st,
        os_module=os,
        sys_module=sys,
    )
    provider = build_partial_one_click_runtime_provider(
        st_module=st,
        guidance_runtime=guidance,
    )
    callback = provider._one_click_post_commit_audit
    assert getattr(callback.func, "__module__", "") == (
        "inputs_application.one_click_commit_policy"
    )
    print(
        "PASS: application-owned post-commit audit has exact 4/4 payload "
        "parity and permanent provider wiring"
    )


if __name__ == "__main__":
    main()
