"""Verify selected-candidate apply/evaluate solver coordinator extraction."""

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


def _base_best() -> dict[str, Any]:
    return {
        "eval": {"overview": {"statuses": {"bending": "OK"}}},
        "label": "Accepted candidate",
        "action_type": "tighten",
        "updates": {"D": 620},
        "signature": "best-signature",
        "worst_util": 0.93,
    }


def _run_success_case(module: Any) -> dict[str, Any]:
    originals = {
        "_trace_accepted_best_candidate_solver_iteration_coordinator": module._trace_accepted_best_candidate_solver_iteration_coordinator,
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", _MISSING),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", _MISSING),
        "_one_click_diff_accumulated_updates": getattr(module, "_one_click_diff_accumulated_updates", _MISSING),
        "_one_click_target_domains_for_eval": getattr(module, "_one_click_target_domains_for_eval", _MISSING),
        "_one_click_attach_eval_target_domains": getattr(module, "_one_click_attach_eval_target_domains", _MISSING),
        "_candidate_state_signature": getattr(module, "_candidate_state_signature", _MISSING),
        "BEAM_STATUS_FAIL": getattr(module, "BEAM_STATUS_FAIL", _MISSING),
    }
    calls: list[dict[str, Any]] = []

    def _trace_accepted(**kwargs: Any) -> None:
        calls.append({"name": "accepted", "label": kwargs["best"]["label"]})

    def _canonical(state: dict[str, Any]) -> dict[str, Any]:
        cloned = dict(state)
        cloned["canonical"] = True
        return cloned

    def _evaluate(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        calls.append({"name": "evaluate", "state": dict(state), "kwargs": dict(kwargs)})
        return {"overview": {"statuses": {"shear": "OK"}}, "state": dict(state)}

    def _diff(initial_snapshot: dict[str, Any], working: dict[str, Any]) -> dict[str, Any]:
        return {"D": working.get("D") - initial_snapshot.get("D")}

    def _target_domains(target_domains_for_band: Any, accumulated_updates: dict[str, Any]) -> list[str]:
        calls.append({"name": "target_domains", "updates": dict(accumulated_updates)})
        return ["bending"]

    def _attach(w_eval: dict[str, Any], target_domains: list[str], mode_config: dict[str, Any]) -> None:
        w_eval["attached_target_domains"] = list(target_domains)

    try:
        module._trace_accepted_best_candidate_solver_iteration_coordinator = _trace_accepted
        module._build_canonical_design_state_pack = _canonical
        module.evaluate_candidate_full = _evaluate
        module._one_click_diff_accumulated_updates = _diff
        module._one_click_target_domains_for_eval = _target_domains
        module._one_click_attach_eval_target_domains = _attach
        module._candidate_state_signature = lambda w_eval: "new-signature"
        module.BEAM_STATUS_FAIL = "FAIL"
        seen_sigs = {"old-signature"}
        returned = module._handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator(
            best=_base_best(),
            mode_config={},
            step_idx=2,
            tightening_step_count=1,
            max_tightening_steps=4,
            candidate_family_depth_reached="spacing",
            best_distance_to_band_this_iteration=0.15,
            initial_snapshot={"D": 600},
            working={"D": 600},
            step_trace=[],
            winning_label=None,
            winning_action_type=None,
            target_domains_for_band=["bending"],
            target_band_domain="bending",
            seen_sigs=seen_sigs,
            trace_callback=lambda ev, dat: calls.append({"name": "trace", "ev": ev, "dat": dict(dat)}),
        )
    finally:
        for attr, original in originals.items():
            if original is _MISSING:
                delattr(module, attr)
            else:
                setattr(module, attr, original)

    return {
        "returned": returned,
        "calls": calls,
        "seen_sigs": sorted(seen_sigs),
        "matches": (
            returned["should_break"] is False
            and returned["working"] == {"D": 620, "canonical": True}
            and returned["accumulated_updates"] == {"D": 20}
            and returned["target_domains"] == ["bending"]
            and returned["w_eval"]["attached_target_domains"] == ["bending"]
            and sorted(seen_sigs) == ["best-signature", "new-signature", "old-signature"]
            and [call["name"] for call in calls] == ["accepted", "evaluate", "target_domains"]
        ),
    }


def _run_evaluate_failed_case(module: Any) -> dict[str, Any]:
    originals = {
        "_trace_accepted_best_candidate_solver_iteration_coordinator": module._trace_accepted_best_candidate_solver_iteration_coordinator,
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", _MISSING),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", _MISSING),
        "_trace_evaluate_failed_after_apply_solver_stop_coordinator": module._trace_evaluate_failed_after_apply_solver_stop_coordinator,
    }
    calls: list[str] = []
    step_base_seen: dict[str, Any] | None = None

    def _canonical(state: dict[str, Any]) -> dict[str, Any]:
        return dict(state)

    def _evaluate(state: dict[str, Any], **kwargs: Any) -> None:
        calls.append("evaluate")
        return None

    def _failed_stop(**kwargs: Any) -> tuple[dict[str, Any], str, str]:
        nonlocal step_base_seen
        calls.append("failed_stop")
        step_base_seen = kwargs["step_base"]
        return kwargs["step_base"], "evaluate_failed_after_apply", "failed"

    try:
        module._trace_accepted_best_candidate_solver_iteration_coordinator = lambda **kwargs: calls.append("accepted")
        module._build_canonical_design_state_pack = _canonical
        module.evaluate_candidate_full = _evaluate
        module._trace_evaluate_failed_after_apply_solver_stop_coordinator = _failed_stop
        returned = module._handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator(
            best=_base_best(),
            mode_config={},
            step_idx=2,
            tightening_step_count=1,
            max_tightening_steps=4,
            candidate_family_depth_reached="spacing",
            best_distance_to_band_this_iteration=0.15,
            initial_snapshot={"D": 600},
            working={"D": 600},
            step_trace=[],
            winning_label="Prior",
            winning_action_type="prior_action",
            target_domains_for_band=["bending"],
            target_band_domain="bending",
            seen_sigs=set(),
            trace_callback=lambda ev, dat: None,
        )
    finally:
        for attr, original in originals.items():
            if original is _MISSING:
                delattr(module, attr)
            else:
                setattr(module, attr, original)

    return {
        "returned": returned,
        "calls": calls,
        "step_base_seen": step_base_seen,
        "matches": (
            returned["should_break"] is True
            and returned["working"] == {"D": 600}
            and returned["stop_reason"] == "evaluate_failed_after_apply"
            and returned["status"] == "failed"
            and returned["w_eval"] is None
            and calls == ["accepted", "evaluate", "failed_stop"]
        ),
    }


def _run_repeated_state_case(module: Any) -> dict[str, Any]:
    originals = {
        "_trace_accepted_best_candidate_solver_iteration_coordinator": module._trace_accepted_best_candidate_solver_iteration_coordinator,
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", _MISSING),
        "evaluate_candidate_full": getattr(module, "evaluate_candidate_full", _MISSING),
        "_one_click_diff_accumulated_updates": getattr(module, "_one_click_diff_accumulated_updates", _MISSING),
        "_one_click_target_domains_for_eval": getattr(module, "_one_click_target_domains_for_eval", _MISSING),
        "_one_click_attach_eval_target_domains": getattr(module, "_one_click_attach_eval_target_domains", _MISSING),
        "_candidate_state_signature": getattr(module, "_candidate_state_signature", _MISSING),
        "_trace_repeated_state_solver_stop_coordinator": module._trace_repeated_state_solver_stop_coordinator,
        "BEAM_STATUS_FAIL": getattr(module, "BEAM_STATUS_FAIL", _MISSING),
    }
    calls: list[str] = []

    try:
        module._trace_accepted_best_candidate_solver_iteration_coordinator = lambda **kwargs: calls.append("accepted")
        module._build_canonical_design_state_pack = lambda state: dict(state)
        module.evaluate_candidate_full = lambda state, **kwargs: {"overview": {"statuses": {"shear": "OK"}}, "state": dict(state)}
        module._one_click_diff_accumulated_updates = lambda initial, working: {"D": working.get("D") - initial.get("D")}
        module._one_click_target_domains_for_eval = lambda domains, updates: []
        module._one_click_attach_eval_target_domains = lambda w_eval, domains, mode_config: None
        module._candidate_state_signature = lambda w_eval: "duplicate-signature"
        module.BEAM_STATUS_FAIL = "FAIL"

        def _repeated_stop(**kwargs: Any) -> tuple[dict[str, Any], str, str]:
            calls.append("repeated_stop")
            return kwargs["step_base"], "repeated_state", "exhausted"

        module._trace_repeated_state_solver_stop_coordinator = _repeated_stop
        seen_sigs = {"duplicate-signature"}
        returned = module._handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator(
            best=_base_best(),
            mode_config={},
            step_idx=2,
            tightening_step_count=1,
            max_tightening_steps=4,
            candidate_family_depth_reached="spacing",
            best_distance_to_band_this_iteration=0.15,
            initial_snapshot={"D": 600},
            working={"D": 600},
            step_trace=[],
            winning_label="Prior",
            winning_action_type="prior_action",
            target_domains_for_band=[],
            target_band_domain="bending",
            seen_sigs=seen_sigs,
            trace_callback=lambda ev, dat: None,
        )
    finally:
        for attr, original in originals.items():
            if original is _MISSING:
                delattr(module, attr)
            else:
                setattr(module, attr, original)

    return {
        "returned": returned,
        "calls": calls,
        "seen_sigs": sorted(seen_sigs),
        "matches": (
            returned["should_break"] is True
            and returned["working"] == {"D": 600}
            and returned["stop_reason"] == "repeated_state"
            and returned["status"] == "exhausted"
            and calls == ["accepted", "repeated_stop"]
            and sorted(seen_sigs) == ["duplicate-signature"]
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator",
    )
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_accepted_candidate_post_step_coordinator",
    )
    _, _, iteration_loop = _function_segment(
        source,
        "_run_one_click_solver_iteration_loop_coordinator",
    )
    _, _, candidate_flow = _function_segment(
        source,
        "_run_one_click_solver_iteration_candidate_flow_coordinator",
    )
    _, _, post_selection = _function_segment(
        source,
        "_run_one_click_solver_iteration_post_selection_acceptance_flow_coordinator",
    )
    _, _, accepted_candidate_dispatch = _function_segment(
        source,
        "_dispatch_one_click_solver_accepted_candidate_post_step_from_post_selection_coordinator",
    )
    _, _, accepted_iteration_packer = _function_segment(
        source,
        "_build_one_click_solver_accepted_iteration_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    success_case = _run_success_case(module)
    evaluate_failed_case = _run_evaluate_failed_case(module)
    repeated_state_case = _run_repeated_state_case(module)
    static_checks = {
        "helper_present": "def _handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator(" in source,
        "helper_delegates_accepted_iteration_trace": "_trace_accepted_best_candidate_solver_iteration_coordinator(" in helper,
        "helper_preserves_step_base_copy": "step_base = copy.deepcopy(working)" in helper,
        "helper_applies_best_updates": 'working.update(best["updates"])' in helper,
        "helper_rebuilds_canonical_pack": "_build_canonical_design_state_pack(working)" in helper,
        "helper_evaluates_after_apply": "evaluate_candidate_full(" in helper,
        "helper_delegates_evaluate_failed_stop": "_trace_evaluate_failed_after_apply_solver_stop_coordinator(" in helper,
        "helper_preserves_target_domain_attach": "_one_click_attach_eval_target_domains(w_eval, target_domains, mode_config)" in helper,
        "helper_delegates_repeated_state_stop": "_trace_repeated_state_solver_stop_coordinator(" in helper,
        "helper_mutates_seen_signatures": "seen_sigs.add(wsig)" in helper and "seen_sigs.add(bsig)" in helper,
        "aggregate_delegates_apply_selected_candidate": (
            "_handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator(" in aggregate
        ),
        "solver_delegates_iteration_loop": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body
        ),
        "iteration_loop_delegates_candidate_flow": (
            "_dispatch_one_click_solver_iteration_candidate_flow_from_iteration_loop_coordinator("
            in iteration_loop
        ),
        "candidate_flow_delegates_post_selection": (
            "_dispatch_one_click_solver_post_selection_acceptance_flow_from_iteration_candidate_flow_coordinator("
            in candidate_flow
        ),
        "post_selection_delegates_accepted_candidate_post_step": (
            "_dispatch_one_click_solver_accepted_candidate_post_step_from_post_selection_coordinator("
            in post_selection
        ),
        "accepted_candidate_dispatch_delegates_aggregate": (
            "_handle_one_click_solver_accepted_candidate_post_step_coordinator("
            in accepted_candidate_dispatch
        ),
        "aggregate_rehydrates_apply_state": all(
            token in aggregate
            for token in (
                'working = apply_selected_candidate_state["working"]',
                'w_eval = apply_selected_candidate_state["w_eval"]',
                'accumulated_updates = apply_selected_candidate_state["accumulated_updates"]',
                'target_domains = apply_selected_candidate_state["target_domains"]',
            )
        ),
        "accepted_iteration_packer_preserves_working": (
            '"working": accepted_candidate_post_step_state["working"]'
            in accepted_iteration_packer
        ),
    }
    runtime = {
        "success_case": success_case["matches"],
        "evaluate_failed_case": evaluate_failed_case["matches"],
        "repeated_state_case": repeated_state_case["matches"],
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_apply_selected_candidate_and_evaluate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_apply_selected_candidate_and_evaluate_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "aggregate_segment": {
            "function": "_handle_one_click_solver_accepted_candidate_post_step_coordinator",
            "start_line": aggregate_start,
            "end_line": aggregate_end,
            "line_count": aggregate_end - aggregate_start + 1,
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
        "next_safe_slice": "extract post-step commit trace and continuation gate coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_apply_selected_candidate_and_evaluate_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_apply_selected_candidate_and_evaluate_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Apply Selected Candidate And Evaluate Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Runtime",
        ]
    )
    for key, value in payload["runtime"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            "",
            str(payload["next_safe_slice"]),
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    payload = build_payload()
    json_path, md_path = write_artifacts(payload)
    print(json.dumps({"status": payload["status"], "json": str(json_path), "report": str(md_path)}, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
