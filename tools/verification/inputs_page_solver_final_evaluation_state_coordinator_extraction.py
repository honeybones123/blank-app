"""Verify final evaluation state solver coordinator extraction."""

from __future__ import annotations

import ast
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AUTO_DESIGN_COMPUTE = ROOT / "inputs_page_modules" / "auto_design_compute.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
_MISSING = object()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_case(
    module: Any,
    *,
    committable: bool,
    target_domains: list[str],
    spacing_fail: bool,
    shear_status: str,
) -> dict[str, Any]:
    patched = (
        "_build_canonical_design_state_pack",
        "evaluate_candidate_full",
        "_one_click_diff_accumulated_updates",
        "_one_click_committable_candidate_eval",
        "_one_click_target_domains_for_eval",
        "_one_click_attach_eval_target_domains",
        "_one_click_required_domains_satisfied",
        "_one_click_has_unresolved_spacing_envelope_fail",
        "_candidate_in_target_band",
        "_one_click_strict_target_band_ok",
        "_candidate_objective_util",
        "_candidate_target_band_distance",
        "_evaluate_shear_with_state",
        "BEAM_STATUS_FAIL",
    )
    originals = {name: getattr(module, name, _MISSING) for name in patched}
    calls: list[dict[str, Any]] = []

    internal_eval = {
        "overview": {
            "worst_util": 0.93,
            "all_key_pass": True,
            "statuses": {"shear": shear_status},
        },
        "state": {"D": 620},
        "source": "internal",
    }
    committable_eval = {
        "overview": {
            "worst_util": 0.91,
            "all_key_pass": True,
            "statuses": {"shear": shear_status},
        },
        "state": {"D": 615},
        "source": "committable",
    }

    try:
        module._build_canonical_design_state_pack = lambda state: {**state, "canonical": True}

        def _evaluate(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            calls.append({"name": "evaluate", "state": dict(state), "kwargs": dict(kwargs)})
            return dict(internal_eval)

        def _committable(initial: dict[str, Any], updates: dict[str, Any], **kwargs: Any):
            calls.append({"name": "committable", "updates": dict(updates), "kwargs": dict(kwargs)})
            return (dict(committable_eval), {"D": updates.get("D"), "safe": True}, None) if committable else (None, {}, None)

        def _attach(final_eval: dict[str, Any], domains: list[str], mode_config: dict[str, Any]) -> None:
            final_eval["attached_domains"] = list(domains)

        module.evaluate_candidate_full = _evaluate
        module._one_click_diff_accumulated_updates = lambda initial, working: {"D": working["D"] - initial["D"]}
        module._one_click_committable_candidate_eval = _committable
        module._one_click_target_domains_for_eval = lambda domains, updates: list(target_domains)
        module._one_click_attach_eval_target_domains = _attach
        module._one_click_required_domains_satisfied = lambda final_eval, mode_config: True
        module._one_click_has_unresolved_spacing_envelope_fail = lambda final_eval: spacing_fail
        module._candidate_in_target_band = lambda final_eval, mode_config: True
        module._one_click_strict_target_band_ok = lambda overview, mode_config: False
        module._candidate_objective_util = lambda final_eval: 0.89
        module._candidate_target_band_distance = lambda final_eval, mode_config: 0.03
        module._evaluate_shear_with_state = lambda state: {"util": 0.87, "web_util": 0.64}
        module.BEAM_STATUS_FAIL = "FAIL"
        result = module._prepare_one_click_solver_final_evaluation_state_coordinator(
            working={"D": 650},
            initial_snapshot={"D": 600},
            winning_label="Winner",
            winning_action_type="tighten",
            target_domains_for_band=["shear"],
            target_band_domain="shear",
            mode_config={"target": "band"},
            init_worst=0.5,
            final_resolved_shear_util=0.1,
            final_resolved_web_util=0.2,
        )
    finally:
        for attr, original in originals.items():
            if original is _MISSING:
                delattr(module, attr)
            else:
                setattr(module, attr, original)

    expected_source = "committable_preview" if committable else "internal_working_preview"
    expected_worst = 0.91 if committable else 0.93
    expected_ok = not spacing_fail
    expected_in_band = not spacing_fail
    return {
        "result": result,
        "calls": calls,
        "matches": (
            result["final_updates"] == {"D": 50}
            and result["final_eval_used_source_dbg"] == expected_source
            and result["final_eval_committable_worst_util_dbg"] == (0.91 if committable else None)
            and result["final_eval_internal_worst_util_dbg"] == 0.93
            and result["final_eval_committable_updates_dbg"] == ({"D": 50, "safe": True} if committable else {})
            and result["final_worst"] == expected_worst
            and result["final_pass"] is expected_ok
            and result["final_ok"] is expected_ok
            and result["final_spacing_fail"] is spacing_fail
            and result["final_in_band"] is expected_in_band
            and result["final_band_hit"] is expected_in_band
            and result["final_objective_util"] == 0.89
            and result["final_distance_to_band"] == 0.03
            and result["final_resolved_shear_util"] == 0.87
            and result["final_resolved_web_util"] == 0.64
            and result["final_target_domains"] == target_domains
            and (
                result["final_eval"].get("target_domain_for_band") == "shear"
                if not target_domains and shear_status == "FAIL"
                else True
            )
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_final_evaluation_state_coordinator",
    )
    finalization_start, finalization_end, finalization = _function_segment(
        source,
        "_finalize_one_click_solver_result_coordinator",
    )
    _, _, after_final_eval_helper = _function_segment(
        source,
        "_run_one_click_solver_finalization_after_final_evaluation_coordinator",
    )
    _, _, final_eval_unpacker = _function_segment(
        source,
        "_unpack_one_click_solver_final_evaluation_state_for_finalization_coordinator",
    )
    _, _, final_evaluation_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_final_evaluation_state_from_finalization_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    _, _, finish_body = _function_segment(
        source,
        "_finish_one_click_solver_iteration_loop_result_coordinator",
    )

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = {
        "committable_selected": _run_case(
            module,
            committable=True,
            target_domains=["shear"],
            spacing_fail=False,
            shear_status="OK",
        )["matches"],
        "internal_fallback": _run_case(
            module,
            committable=False,
            target_domains=["shear"],
            spacing_fail=False,
            shear_status="OK",
        )["matches"],
        "spacing_fail_blocks_final_ok": _run_case(
            module,
            committable=True,
            target_domains=["shear"],
            spacing_fail=True,
            shear_status="OK",
        )["matches"],
        "empty_target_domains_shear_fail_fallback": _run_case(
            module,
            committable=True,
            target_domains=[],
            spacing_fail=False,
            shear_status="FAIL",
        )["matches"],
    }
    static_checks = {
        "helper_present": "def _prepare_one_click_solver_final_evaluation_state_coordinator(" in source,
        "helper_evaluates_final_internal": 'source="one_click_final"' in helper,
        "helper_builds_final_updates": "_one_click_diff_accumulated_updates(initial_snapshot, working)" in helper,
        "helper_evaluates_committable": "_one_click_committable_candidate_eval(" in helper,
        "helper_selects_committable_or_internal": "final_eval = final_eval_committable or final_eval_internal" in helper,
        "helper_preserves_eval_debug_fields": all(
            token in helper
            for token in (
                "final_eval_internal_worst_util_dbg",
                "final_eval_committable_worst_util_dbg",
                "final_eval_used_source_dbg",
                "final_eval_committable_updates_dbg",
            )
        ),
        "helper_attaches_target_domains": "_one_click_attach_eval_target_domains(final_eval, final_target_domains, mode_config)" in helper,
        "helper_preserves_spacing_fail_override": "if final_spacing_fail:" in helper,
        "helper_preserves_band_hit_gate": "final_band_hit = bool(" in helper,
        "helper_updates_final_shear_preview": "final_shear_preview = _evaluate_shear_with_state(" in helper,
        "finalization_delegates_final_evaluation_state": (
            "_dispatch_one_click_solver_final_evaluation_state_from_finalization_coordinator("
            in finalization
            and "_prepare_one_click_solver_final_evaluation_state_coordinator("
            in final_evaluation_dispatch
            and "finalization_scope[" in final_evaluation_dispatch
        ),
        "finish_delegates_finalization": "_finalize_one_click_solver_result_coordinator(" in finish_body,
        "solver_delegates_loop_result_finish": "_finish_one_click_solver_iteration_loop_result_coordinator("
        in solve_body,
        "finalization_rehydrates_final_fields": all(
            token in final_eval_unpacker
            for token in (
                'final_evaluation_state["final_eval_internal"]',
                'final_evaluation_state["final_updates"]',
                'final_evaluation_state["final_eval"]',
                'final_evaluation_state["final_target_domains"]',
                'final_evaluation_state["final_band_hit"]',
                'final_evaluation_state["final_resolved_web_util"]',
            )
        )
        and "_unpack_one_click_solver_final_evaluation_state_for_finalization_coordinator("
        in after_final_eval_helper,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_final_evaluation_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_final_evaluation_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "finalization_segment": {
            "function": "_finalize_one_click_solver_result_coordinator",
            "start_line": finalization_start,
            "end_line": finalization_end,
            "line_count": finalization_end - finalization_start + 1,
        },
        "solver_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract partial failing final updates guard",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_final_evaluation_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_final_evaluation_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Final Evaluation State Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Runtime"])
    for key, value in payload["runtime"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Safe Slice", "", str(payload["next_safe_slice"])])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
