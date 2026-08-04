"""Verify one-click solver candidate scalar metric state coordinator extraction."""

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


def _run_cases(module: Any) -> dict[str, Any]:
    originals = {
        "_candidate_objective_util": getattr(module, "_candidate_objective_util", None),
        "_candidate_target_band_distance": getattr(module, "_candidate_target_band_distance", None),
        "_shear_preview_for_updates": getattr(module, "_shear_preview_for_updates", None),
    }
    distance_calls: list[dict[str, Any]] = []
    preview_calls: list[dict[str, Any]] = []

    def _objective(peval: dict[str, Any]) -> float:
        return float(peval.get("u", 0.0) or 0.0)

    def _distance(eval_obj: dict[str, Any], mode_config: Any) -> float:
        distance_calls.append({"kind": eval_obj.get("kind"), "mode": mode_config})
        return float(eval_obj.get("d", 0.0) or 0.0)

    def _preview(working: dict[str, Any], norm_u: dict[str, Any]) -> dict[str, Any]:
        preview_calls.append({"working": dict(working), "norm_u": dict(norm_u)})
        if norm_u.get("bad"):
            return {"util": "bad", "web_util": "bad"}
        return {"util": "0.91", "web_util": "0.72"}

    try:
        module._candidate_objective_util = _objective
        module._candidate_target_band_distance = _distance
        module._shear_preview_for_updates = _preview
        shear = module._prepare_one_click_solver_candidate_scalar_metric_state_coordinator(
            peval={"kind": "peval", "u": 0.88, "d": 0.04},
            cur_eval={"kind": "cur", "d": 0.11},
            working={"D": 600},
            norm_u={"lig_d": 12},
            mode_config={"mode": "balanced"},
            governing_domain="shear",
        )
        non_shear = module._prepare_one_click_solver_candidate_scalar_metric_state_coordinator(
            peval={"kind": "peval2", "u": 0.77, "d": 0.02},
            cur_eval={"kind": "cur2", "d": 0.08},
            working={"D": 600},
            norm_u={"D": 650},
            mode_config={"mode": "balanced"},
            governing_domain="bending",
        )
        bad_preview = module._prepare_one_click_solver_candidate_scalar_metric_state_coordinator(
            peval={"kind": "peval3", "u": 0.99, "d": 0.01},
            cur_eval={"kind": "cur3", "d": 0.03},
            working={"D": 600},
            norm_u={"bad": True},
            mode_config={"mode": "balanced"},
            governing_domain="shear",
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "shear": shear,
        "non_shear": non_shear,
        "bad_preview": bad_preview,
        "distance_calls": distance_calls,
        "preview_calls": preview_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_scalar_metric_state_coordinator",
    )
    _, _, post_metric_scalar_helper = _function_segment(
        source,
        "_prepare_one_click_solver_single_candidate_post_metric_scalar_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    _, _, single_candidate_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_scoring_flow_coordinator"
    )
    _, _, post_metric_body = _function_segment(
        source, "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator"
    )
    _, _, pre_selection_body = _function_segment(
        source, "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    common_false_state = {
        "remove_links_candidate": False,
        "remove_links_truth_ok": False,
    }
    runtime_checks = {
        "shear_metrics_preserved": runtime["shear"] == {
            "new_u": 0.88,
            "new_d": 0.04,
            "old_d": 0.11,
            "shear_preview": {"util": "0.91", "web_util": "0.72"},
            **common_false_state,
            "shear_util_preview": 0.91,
            "web_util_preview": 0.72,
        },
        "non_shear_metrics_preserved": runtime["non_shear"] == {
            "new_u": 0.77,
            "new_d": 0.02,
            "old_d": 0.08,
            "shear_preview": None,
            **common_false_state,
            "shear_util_preview": None,
            "web_util_preview": None,
        },
        "bad_preview_fallback_preserved": runtime["bad_preview"] == {
            "new_u": 0.99,
            "new_d": 0.01,
            "old_d": 0.03,
            "shear_preview": runtime["bad_preview"]["shear_preview"],
            **common_false_state,
            "shear_util_preview": None,
            "web_util_preview": None,
        },
        "distance_calls_preserved": runtime["distance_calls"] == [
            {"kind": "peval", "mode": {"mode": "balanced"}},
            {"kind": "cur", "mode": {"mode": "balanced"}},
            {"kind": "peval2", "mode": {"mode": "balanced"}},
            {"kind": "cur2", "mode": {"mode": "balanced"}},
            {"kind": "peval3", "mode": {"mode": "balanced"}},
            {"kind": "cur3", "mode": {"mode": "balanced"}},
        ],
        "shear_preview_only_for_shear": runtime["preview_calls"] == [
            {"working": {"D": 600}, "norm_u": {"lig_d": 12}},
            {"working": {"D": 600}, "norm_u": {"bad": True}},
        ],
    }
    static_checks = {
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "pre_selection_delegates_candidate_scoring_loop": (
            "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(" in pre_selection_body
            or "_run_one_click_solver_pre_selection_candidate_pipeline_and_scoring_coordinator(" in pre_selection_body
        ),
        "scoring_loop_delegates_single_candidate_flow": (
            "_run_one_click_solver_single_candidate_scoring_flow_coordinator(" in scoring_loop_body
        ),
        "single_candidate_flow_delegates_post_metric_scoring_flow": (
            "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator(" in single_candidate_body
        ),
        "helper_present": "def _prepare_one_click_solver_candidate_scalar_metric_state_coordinator(" in source,
        "helper_preserves_objective_and_distances": "_candidate_objective_util(peval)" in helper
        and "_candidate_target_band_distance(peval, mode_config)" in helper
        and "_candidate_target_band_distance(cur_eval, mode_config)" in helper,
        "helper_preserves_shear_preview_gate": (
            '_shear_preview_for_updates(working, norm_u) if governing_domain == "shear" else None' in helper
        ),
        "helper_preserves_false_remove_link_defaults": '"remove_links_candidate": False' in helper
        and '"remove_links_truth_ok": False' in helper,
        "helper_preserves_preview_float_fallbacks": "except Exception:" in helper
        and "shear_util_preview = None" in helper
        and "web_util_preview = None" in helper,
        "post_metric_flow_delegates_scalar_metric_state": (
            "_prepare_one_click_solver_single_candidate_post_metric_scalar_state_coordinator(" in post_metric_body
            and "_prepare_one_click_solver_candidate_scalar_metric_state_coordinator(" in post_metric_scalar_helper
        ),
        "post_metric_flow_rehydrates_scalar_metric_fields": (
            'new_u = scalar_metric_state["new_u"]' in post_metric_body
            and 'remove_links_candidate = scalar_metric_state["remove_links_candidate"]' in post_metric_body
            and 'web_util_preview = scalar_metric_state["web_util_preview"]' in post_metric_body
        ),
        "scoring_loop_no_longer_delegates_scalar_metric_directly": (
            "_prepare_one_click_solver_candidate_scalar_metric_state_coordinator(" not in scoring_loop_body
        ),
        "solver_no_longer_builds_shear_preview_inline": "_shear_preview_for_updates(" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_candidate_scalar_metric_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_candidate_scalar_metric_state_coordinator",
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
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract shear remove-links truth probe setup branch",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_scalar_metric_state_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_scalar_metric_state_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Scalar Metric State Coordinator Extraction",
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
