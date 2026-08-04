"""Lock one-click terminal combined-overdesign publication."""

from __future__ import annotations

import contextlib
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOURCE = (
    ROOT
    / "artifacts"
    / "verification"
    / "live_fuzz"
    / "replay_2026-07-28T20-48-32"
    / "failure_browser_state.json"
)
ARTIFACT = (
    ROOT
    / "artifacts"
    / "verification"
    / "combined_overdesign_safe_fallback_publication_direct_runtime.json"
)


def main() -> int:
    if not SOURCE.exists():
        print(f"FAIL: captured state missing: {SOURCE}")
        return 1

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        import streamlit as st

        from design_brain.final_publication import (
            build_final_design_guide_cta,
        )
        from inputs_application.guidance_entrypoint import (
            build_guidance_entrypoint_runtime,
            compute_inputs_guidance,
        )

    browser_state = json.loads(SOURCE.read_text(encoding="utf-8"))
    state = dict(browser_state.get("browser_shared_probe") or {})
    try:
        st.session_state.clear()
    except Exception:
        pass
    for key, value in state.items():
        st.session_state[key] = deepcopy(value)

    runtime = build_guidance_entrypoint_runtime(
        st_module=st,
        os_module=os,
        sys_module=sys,
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        payload = compute_inputs_guidance(
            runtime,
            deepcopy(state),
            guidance_debug_verbose=True,
            debug_enabled=True,
        )

    items = [
        dict(row)
        for row in list(payload.get("guidance_items") or [])
        if isinstance(row, dict)
    ]
    item = dict(items[0] if items else {})
    contract = dict(item.get("button_contract") or {})
    cta = build_final_design_guide_cta(item=item).to_dict()
    debug = dict(payload.get("debug_trace") or {})
    fold = dict(
        dict(debug.get("family_ladder_runtime_result") or {}).get(
            "combined_overdesign_terminal_fold"
        )
        or {}
    )

    post_state = deepcopy(state)
    post_state.update(dict(cta.get("updates") or {}))
    st.session_state.clear()
    for key, value in post_state.items():
        st.session_state[key] = deepcopy(value)
    post_runtime = build_guidance_entrypoint_runtime(
        st_module=st,
        os_module=os,
        sys_module=sys,
    )
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        post_payload = compute_inputs_guidance(
            post_runtime,
            deepcopy(post_state),
            guidance_debug_verbose=True,
            debug_enabled=True,
        )
    post_items = [
        dict(row)
        for row in list(post_payload.get("guidance_items") or [])
        if isinstance(row, dict)
    ]
    post_item = dict(post_items[0] if post_items else {})
    post_contract = dict(post_item.get("button_contract") or {})

    checks = {
        "captured_case_dispatches_combined_overdesign": (
            debug.get(
                "family_ladder_dispatch_selected_family_id"
            )
            == "COMBINED_OVERDESIGN"
        ),
        "terminal_fold_proof_reaches_publication": (
            fold.get("terminal_reached") is True
            and str(fold.get("terminal_candidate_status") or "")
            in {"TERMINAL_TARGET_BAND", "TERMINAL_EXACT_STOP"}
            and dict(fold.get("cumulative_updates") or {})
            == dict(contract.get("updates") or {})
        ),
        "final_cta_preserves_terminal_safe_action": (
            cta.get("enabled") is True
            and cta.get("actionable") is True
            and cta.get("action_type") == "apply_resolved_candidate"
            and bool(cta.get("updates"))
            and cta.get("disabled_reason") is None
        ),
        "post_apply_is_terminal_without_second_cta": (
            str(post_item.get("status") or "").upper() == "PASS"
            and str(post_item.get("family") or "").upper()
            in {"EXACT_STOP_PROVEN", "TARGET_BAND_REACHED"}
            and post_contract.get("enabled") is False
            and not bool(
                post_contract.get("updates") or post_item.get("updates")
            )
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    artifact = {
        "schema": "combined_overdesign_terminal_publication_direct_runtime.v2",
        "status": "PASS" if not failures else "FAIL",
        "source": str(SOURCE),
        "checks": checks,
        "failures": failures,
        "button_contract": contract,
        "final_cta": cta,
        "terminal_fold": fold,
        "post_apply_item": post_item,
        "post_apply_button_contract": post_contract,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "PASS: terminal combined-overdesign proof survives final CTA publication"
        if not failures
        else f"FAIL: {failures}"
    )
    print(f"Artifact: {ARTIFACT}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
