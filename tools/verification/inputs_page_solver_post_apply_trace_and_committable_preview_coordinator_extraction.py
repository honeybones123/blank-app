"""Verify post-apply trace and committable-preview solver coordinator extraction."""

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


def _base_best(updates: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "label": "Tighten depth",
        "action_type": "geometry",
        "updates": dict(updates or {"D": 620}),
        "worst_util": 0.94,
        "change_summary": "Depth increased",
        "eval": {
            "overview": {
                "all_key_pass": True,
                "worst_util": 0.94,
            },
        },
    }


def _run_case(module: Any, *, combined: bool, committable: bool) -> dict[str, Any]:
    originals = {
        "_candidate_in_target_band": getattr(module, "_candidate_in_target_band", _MISSING),
        "_one_click_committable_candidate_eval": getattr(module, "_one_click_committable_candidate_eval", _MISSING),
    }
    step_trace: list[dict[str, Any]] = []
    committable_trace: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []

    def _candidate_in_target_band(eval_payload: dict[str, Any], mode_config: dict[str, Any]) -> bool:
        calls.append({"name": "candidate_in_target_band", "mode": dict(mode_config)})
        return True

    def _committable_candidate_eval(
        initial_snapshot: dict[str, Any],
        accumulated_updates: dict[str, Any],
        *,
        source: str,
        label: str,
        action_type: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any], None]:
        calls.append(
            {
                "name": "committable",
                "initial": dict(initial_snapshot),
                "updates": dict(accumulated_updates),
                "source": source,
                "label": label,
                "action_type": action_type,
            }
        )
        if not committable:
            return None, {"D": accumulated_updates.get("D")}, None
        return (
            {"overview": {"all_key_pass": True, "worst_util": 0.91}, "state": {"D": 618}},
            {"D": accumulated_updates.get("D"), "sanitized": True},
            None,
        )

    try:
        module._candidate_in_target_band = _candidate_in_target_band
        module._one_click_committable_candidate_eval = _committable_candidate_eval
        updates = {"D": 620, "lig_d": 12} if combined else {"D": 620}
        returned = module._handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator(
            best=_base_best(updates),
            mode_config={"target": "band"},
            step_idx=2,
            initial_snapshot={"D": 600},
            accumulated_updates={"D": 20, "lig_d": 2} if combined else {"D": 20},
            w_eval={"overview": {"all_key_pass": True, "worst_util": 0.94}, "state": {"D": 620}},
            governing_domain="shear" if combined else "bending",
            tightening_mode_active=True,
            tightening_step_count=1,
            step_trace=step_trace,
            step_committable_eval_trace=committable_trace,
        )
    finally:
        for attr, original in originals.items():
            if original is _MISSING:
                delattr(module, attr)
            else:
                setattr(module, attr, original)

    expected_label = "Combined shear + geometry tightening" if combined else "Tighten depth"
    expected_gate_worst = 0.91 if committable else 0.94
    return {
        "returned": returned,
        "step_trace": step_trace,
        "committable_trace": committable_trace,
        "calls": calls,
        "matches": (
            returned["winning_label"] == expected_label
            and returned["winning_action_type"] == "geometry"
            and returned["tightening_step_count"] == 2
            and float((returned["w_gate_eval"].get("overview") or {}).get("worst_util")) == expected_gate_worst
            and step_trace
            == [
                {
                    "step": 3,
                    "label": expected_label,
                    "action_type": "geometry",
                    "worst_util": 0.94,
                    "all_key_pass": True,
                    "reached_target_band": True,
                    "change_summary": "Depth increased",
                }
            ]
            and committable_trace[0]["step"] == 2
            and committable_trace[0]["winning_label"] == expected_label
            and committable_trace[0]["internal_preview_worst_util"] == 0.94
            and committable_trace[0]["committable_preview_worst_util"] == (0.91 if committable else None)
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator",
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
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = {
        "normal_committable": _run_case(module, combined=False, committable=True)["matches"],
        "combined_shear_geometry": _run_case(module, combined=True, committable=True)["matches"],
        "committable_fallback": _run_case(module, combined=False, committable=False)["matches"],
    }
    static_checks = {
        "helper_present": "def _handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator(" in source,
        "helper_preserves_combined_label_override": '"Combined shear + geometry tightening"' in helper,
        "helper_preserves_tightening_increment": "tightening_step_count += 1" in helper,
        "helper_appends_step_trace": "step_trace.append(" in helper,
        "helper_checks_target_band": "_candidate_in_target_band(best[\"eval\"], mode_config)" in helper,
        "helper_calls_committable_eval": "_one_click_committable_candidate_eval(" in helper,
        "helper_selects_gate_eval": "w_gate_eval = w_commit_eval or w_eval" in helper,
        "helper_appends_committable_trace": "step_committable_eval_trace.append(" in helper,
        "aggregate_delegates_post_apply_trace": (
            "_handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator(" in aggregate
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
        "aggregate_rehydrates_returned_fields": all(
            token in aggregate
            for token in (
                'winning_label = post_apply_trace_state["winning_label"]',
                'winning_action_type = post_apply_trace_state["winning_action_type"]',
                'tightening_step_count = post_apply_trace_state["tightening_step_count"]',
                'w_gate_eval = post_apply_trace_state["w_gate_eval"]',
            )
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_post_apply_trace_and_committable_preview_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_post_apply_trace_and_committable_preview_coordinator",
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
        "next_safe_slice": "extract post-step continuation metrics and trace coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_post_apply_trace_and_committable_preview_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_post_apply_trace_and_committable_preview_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Post-Apply Trace And Committable Preview Coordinator Extraction",
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
