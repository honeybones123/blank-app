"""Verify one-click solver iteration state coordinator extraction."""

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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_segment(source: str, name: str) -> tuple[int, int, str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _run_case(module: Any) -> dict[str, Any]:
    originals = {
        "_candidate_state_signature": getattr(module, "_candidate_state_signature", None),
        "_governing_focus_from_overview": getattr(module, "_governing_focus_from_overview", None),
    }
    calls: list[dict[str, Any]] = []

    try:
        module._candidate_state_signature = lambda eval_obj: ("seed", eval_obj["overview"]["worst_util"])

        def _focus(overview: dict) -> str:
            calls.append({"overview": dict(overview)})
            return "shear"

        module._governing_focus_from_overview = _focus
        result = module._prepare_one_click_solver_iteration_state_coordinator(
            init_eval={"overview": {"worst_util": 0.88}},
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    result["step_trace"].append({"probe": True})
    list_isolated = result["step_trace"] == [{"probe": True}]
    result["seen_sigs"].add(("extra", 1))
    set_mutable = ("extra", 1) in result["seen_sigs"]
    return {"result": result, "calls": calls, "list_isolated": list_isolated, "set_mutable": set_mutable}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_iteration_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    runtime_setup_start, runtime_setup_end, runtime_setup_body = _function_segment(
        source, "_prepare_one_click_solver_runtime_setup_state_coordinator"
    )
    _, _, ready_body = _function_segment(
        source,
        "_build_one_click_solver_runtime_setup_ready_state_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    result = runtime["result"]
    runtime_checks = {
        "seen_signature_seed_preserved": ("seed", 0.88) in result["seen_sigs"],
        "step_and_stop_defaults_preserved": result["step_trace"] == [{"probe": True}]
        and result["stop_reason"] == "max_steps"
        and result["status"] == "exhausted"
        and result["winning_label"] is None
        and result["winning_action_type"] is None,
        "governing_domain_default_preserved": result["final_governing_domain"] == "shear"
        and runtime["calls"] == [{"overview": {"worst_util": 0.88}}],
        "rejection_and_shear_defaults_preserved": result["rejected_as_non_governing_cleanup"] == 0
        and result["rejected_as_non_governing_shear_strengthening"] == 0
        and result["shear_remove_links_candidate_seen"] is False
        and result["shear_remove_links_candidate_truth_ok"] is False
        and result["shear_remove_links_candidate_dropped_reason"] is None
        and result["shear_remove_links_candidate_materiality"] == "not_evaluated",
        "mutable_collections_preserved": runtime["list_isolated"] and runtime["set_mutable"],
    }
    static_checks = {
        "solver_delegates_runtime_setup_state": (
            "_prepare_one_click_solver_runtime_setup_state_coordinator(" in solve_body
        ),
        "helper_present": "def _prepare_one_click_solver_iteration_state_coordinator(" in source,
        "helper_preserves_signature_seed": "_candidate_state_signature(init_eval)" in helper
        and "seen_sigs.add(sig0)" in helper,
        "helper_preserves_stop_status_defaults": '"stop_reason": "max_steps"' in helper
        and '"status": "exhausted"' in helper
        and '"winning_label": None' in helper
        and '"winning_action_type": None' in helper,
        "helper_preserves_governing_domain_default": "_governing_focus_from_overview((init_eval.get(\"overview\") or {}))"
        in helper,
        "helper_preserves_rejection_and_shear_defaults": '"rejected_as_non_governing_cleanup": 0' in helper
        and '"rejected_as_non_governing_shear_strengthening": 0' in helper
        and '"shear_remove_links_candidate_seen": False' in helper
        and '"shear_remove_links_candidate_materiality": "not_evaluated"' in helper,
        "solver_delegates_iteration_state": "_prepare_one_click_solver_iteration_state_coordinator("
        in runtime_setup_body,
        "runtime_setup_delegates_ready_state_packing": (
            "_build_one_click_solver_runtime_setup_ready_state_coordinator(" in runtime_setup_body
        ),
        "ready_state_rehydrates_iteration_state_fields": '"seen_sigs": solver_iteration_state["seen_sigs"]' in ready_body
        and '"final_governing_domain": solver_iteration_state["final_governing_domain"]' in ready_body
        and '"shear_remove_links_candidate_materiality": solver_iteration_state['
        in ready_body,
        "solver_no_longer_inlines_iteration_state_setup": "seen_sigs: set[tuple] = set()" not in solve_body
        and 'stop_reason = "max_steps"' not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_iteration_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_iteration_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "solver_segment": {
            "function": "_solve_one_click_to_target",
            "start_line": solve_start,
            "end_line": solve_end,
            "line_count": solve_end - solve_start + 1,
        },
        "static_checks": static_checks,
        "runtime_checks": runtime_checks,
        "runtime": {
            "calls": runtime["calls"],
            "result": {
                key: sorted(value) if isinstance(value, set) else value
                for key, value in result.items()
            },
        },
        "product_behavior_changed": False,
        "next_safe_slice": "extract current iteration evaluation setup",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_iteration_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_iteration_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Iteration State Coordinator Extraction",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Static Checks",
    ]
    for key, value in payload["static_checks"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Runtime Checks")
    for key, value in payload["runtime_checks"].items():
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
