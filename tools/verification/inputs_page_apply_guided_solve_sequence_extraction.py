"""Verify guided-solve sequence extraction from the Inputs app bridge."""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "inputs_page_app_contract_bridge.py"
MODULE = ROOT / "inputs_page_modules" / "apply_guidance_action.py"
ARTIFACTS = ROOT / "artifacts" / "verification"
AUDITS = ROOT / "artifacts" / "audits"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _function_node(source: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


class _FakeStreamlit:
    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}
        self.rerun_count = 0

    def rerun(self) -> None:
        self.rerun_count += 1


def _bind_for_scenario(name: str) -> dict[str, Any]:
    import inputs_page_modules.apply_guidance_action as extracted

    fake_st = _FakeStreamlit()
    fake_st.session_state["debug_bundle"] = {"guidance_branch": "test_branch"}
    state = {"D": 600, "bars": 4}
    calls: dict[str, Any] = {"applies": [], "banner_meta": [], "evaluations": []}
    eval_sequence = [{"is_compliant": False}, {"is_compliant": name == "post_compliant"}]

    if name == "seed_compliant":
        eval_sequence = [{"is_compliant": True}]

    def _shared_state_snapshot() -> dict:
        return dict(state)

    def _guidance_state_snapshot(snapshot: dict) -> dict:
        return dict(snapshot)

    def _evaluate_candidate_full(snapshot: dict, *, source: str) -> dict:
        calls["evaluations"].append({"snapshot": dict(snapshot), "source": source})
        if eval_sequence:
            return dict(eval_sequence.pop(0))
        return {"is_compliant": False}

    def _compute_geometry_recommendation(snapshot: dict) -> dict | None:
        if name == "no_recommendation":
            return None
        if name == "arrangement_fallback":
            return {"arrangement": {"bars": 6}}
        return {"updates": {"D": 650}}

    def _compute_bottom_reo_recommendation(snapshot: dict) -> dict | None:
        if name == "no_recommendation":
            return None
        return {"updates": {"bars": 5}}

    def _compute_shear_recommendation(snapshot: dict) -> dict | None:
        if name == "no_recommendation":
            return None
        return {"updates": {"s_lig": 150}}

    def _bottom_arrangement_to_shared_updates(arrangement: dict) -> dict:
        return {"bars": arrangement.get("bars")}

    def _updates_match_state(snapshot: dict, updates: dict) -> bool:
        return name == "updates_match"

    def _build_design_actions_context(snapshot: dict) -> dict:
        return {"ctx": dict(snapshot)}

    def _collect_design_overview(snapshot: dict, *, context: dict) -> dict:
        return {"overview": dict(snapshot), "context": dict(context)}

    def _prepare_guidance_apply_banner_meta(action_type: str, payload: dict) -> None:
        calls["banner_meta"].append({"action_type": action_type, "payload": dict(payload)})
        fake_st.session_state["banner_meta"] = {"title": payload.get("guidance_banner_title")}

    def _apply_shared_updates(updates: dict, *, source: str, rerun: bool, focus_section: str) -> bool:
        calls["applies"].append(
            {
                "updates": dict(updates),
                "source": source,
                "rerun": bool(rerun),
                "focus_section": focus_section,
            }
        )
        state.update(updates)
        return name != "apply_fails"

    extracted.bind_apply_guidance_action_dependencies(
        {
            "DESIGN_GUIDE_APPLY_BANNER_META_KEY": "banner_meta",
            "DESIGN_GUIDE_DEBUG_BUNDLE_KEY": "debug_bundle",
            "DESIGN_GUIDE_PENDING_STEP_CTX_KEY": "pending_step_ctx",
            "_apply_shared_updates": _apply_shared_updates,
            "_bottom_arrangement_to_shared_updates": _bottom_arrangement_to_shared_updates,
            "_build_design_actions_context": _build_design_actions_context,
            "_collect_design_overview": _collect_design_overview,
            "_compute_bottom_reo_recommendation": _compute_bottom_reo_recommendation,
            "_compute_geometry_recommendation": _compute_geometry_recommendation,
            "_compute_shear_recommendation": _compute_shear_recommendation,
            "_guidance_state_snapshot": _guidance_state_snapshot,
            "_prepare_guidance_apply_banner_meta": _prepare_guidance_apply_banner_meta,
            "_shared_state_snapshot": _shared_state_snapshot,
            "_updates_match_state": _updates_match_state,
            "evaluate_candidate_full": _evaluate_candidate_full,
            "st": fake_st,
        }
    )
    return {"module": extracted, "st": fake_st, "calls": calls}


def _run_scenario(name: str) -> dict[str, Any]:
    bound = _bind_for_scenario(name)
    returned = bound["module"].apply_guided_solve_sequence(source="guidance:test")
    return {
        "returned": returned,
        "rerun_count": bound["st"].rerun_count,
        "session_state": dict(bound["st"].session_state),
        "calls": bound["calls"],
    }


def main() -> int:
    bridge_source = BRIDGE.read_text(encoding="utf-8")
    module_source = MODULE.read_text(encoding="utf-8")
    bridge_node = _function_node(bridge_source, "apply_guided_solve_sequence")
    module_node = _function_node(module_source, "apply_guided_solve_sequence")
    bridge_body = ast.get_source_segment(bridge_source, bridge_node) or ""
    dependency_section = module_source.partition("def bind_apply_guidance_action_dependencies")[0]

    scenarios = {
        name: _run_scenario(name)
        for name in (
            "seed_compliant",
            "no_recommendation",
            "updates_match",
            "apply_fails",
            "post_compliant",
            "arrangement_fallback",
        )
    }

    import inputs_page_app_contract_bridge as bridge
    import inputs_page_modules.apply_guidance_action as extracted

    original = bridge._apply_guided_solve_sequence_extracted
    delegate_call: dict[str, Any] = {}

    def _fake_extracted(*, source: str) -> bool:
        delegate_call["source"] = source
        delegate_call["module_owner"] = extracted.apply_guided_solve_sequence is original
        return True

    try:
        bridge._apply_guided_solve_sequence_extracted = _fake_extracted
        wrapped = bridge.apply_guided_solve_sequence(source="guidance:bridge")
    finally:
        bridge._apply_guided_solve_sequence_extracted = original

    checks: dict[str, bool] = {
        "bridge_wrapper_is_small": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1 <= 8,
        "bridge_binds_dependencies": "_bind_apply_guidance_action_dependencies(globals())" in bridge_body,
        "bridge_delegates_to_extracted_module": "_apply_guided_solve_sequence_extracted" in bridge_body,
        "module_contains_extracted_body": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1 >= 65,
        "module_dependency_list_no_longer_binds_guided_sequence": '"apply_guided_solve_sequence"' not in dependency_section,
        "module_has_needed_low_level_dependencies": all(
            token in dependency_section
            for token in (
                '"_compute_geometry_recommendation"',
                '"_compute_bottom_reo_recommendation"',
                '"_compute_shear_recommendation"',
                '"_bottom_arrangement_to_shared_updates"',
                '"_updates_match_state"',
            )
        ),
        "seed_compliant_noop": scenarios["seed_compliant"]["returned"] is False
        and scenarios["seed_compliant"]["calls"]["applies"] == [],
        "no_recommendation_noop": scenarios["no_recommendation"]["returned"] is False
        and scenarios["no_recommendation"]["calls"]["applies"] == [],
        "updates_match_noop": scenarios["updates_match"]["returned"] is False
        and scenarios["updates_match"]["calls"]["applies"] == [],
        "apply_failure_clears_pending": scenarios["apply_fails"]["returned"] is False
        and "pending_step_ctx" not in scenarios["apply_fails"]["session_state"],
        "post_compliant_reruns_and_returns_true": scenarios["post_compliant"]["returned"] is True
        and scenarios["post_compliant"]["rerun_count"] == 1,
        "arrangement_fallback_applies_bottom_updates": scenarios["arrangement_fallback"]["calls"]["applies"][0]["updates"] == {"bars": 6},
        "apply_uses_no_rerun_shared_update": scenarios["post_compliant"]["calls"]["applies"][0]["rerun"] is False,
        "apply_focus_section_model": scenarios["post_compliant"]["calls"]["applies"][0]["focus_section"] == "model",
        "bridge_runtime_delegates": wrapped is True and delegate_call.get("source") == "guidance:bridge",
        "bridge_runtime_preserves_module_owner": delegate_call.get("module_owner") is True,
    }

    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "scenarios": scenarios,
        "bridge_wrapper_lines": (bridge_node.end_lineno or bridge_node.lineno) - bridge_node.lineno + 1,
        "module_function_lines": (module_node.end_lineno or module_node.lineno) - module_node.lineno + 1,
    }

    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS / f"inputs_page_apply_guided_solve_sequence_extraction_{stamp}.json"
    report_path = AUDITS / f"inputs_page_apply_guided_solve_sequence_extraction_{stamp}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Apply Guided Solve Sequence Extraction",
                "",
                f"Status: {result['status']}",
                "",
                f"- Bridge wrapper lines: {result['bridge_wrapper_lines']}",
                f"- Extracted module function lines: {result['module_function_lines']}",
                "",
                "## Checks",
                "",
                *[f"- {check}: {'PASS' if passed else 'FAIL'}" for check, passed in checks.items()],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(result["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
