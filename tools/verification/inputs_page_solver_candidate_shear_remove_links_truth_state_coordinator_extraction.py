"""Verify one-click solver shear remove-links truth-state coordinator extraction."""

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
        "_float_from_state": getattr(module, "_float_from_state", None),
        "_int_from_state": getattr(module, "_int_from_state", None),
        "_build_design_actions_context": getattr(module, "_build_design_actions_context", None),
        "_parse_util_value": getattr(module, "_parse_util_value", None),
        "_shear_demands_negligible": getattr(module, "_shear_demands_negligible", None),
        "GUIDANCE_SHEAR_UTIL_NEGLIGIBLE": getattr(module, "GUIDANCE_SHEAR_UTIL_NEGLIGIBLE", None),
    }
    action_context_calls: list[dict[str, Any]] = []
    negligible_calls: list[dict[str, Any]] = []

    def _float_from_state(state: dict[str, Any], key: str, default: float) -> float:
        return float(state.get(key, default) or default)

    def _int_from_state(state: dict[str, Any], key: str, default: int) -> int:
        return int(state.get(key, default) or default)

    def _actions_context(state: dict[str, Any]) -> dict[str, Any]:
        action_context_calls.append(dict(state))
        return {"actions": dict(state.get("actions") or {})}

    def _parse_util(value: Any) -> float | None:
        return None if value is None else float(value)

    def _negligible(actions: dict[str, Any]) -> bool:
        negligible_calls.append(dict(actions))
        return bool(actions.get("negligible"))

    try:
        module._float_from_state = _float_from_state
        module._int_from_state = _int_from_state
        module._build_design_actions_context = _actions_context
        module._parse_util_value = _parse_util
        module._shear_demands_negligible = _negligible
        module.GUIDANCE_SHEAR_UTIL_NEGLIGIBLE = 0.05

        truth_ok = module._prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(
            peval={"overview": {"all_key_pass": True, "utils": {"shear": "0.04"}}},
            preview={
                "s_lig": 0,
                "lig_legs": 0,
                "lig_d": 0,
                "actions": {"negligible": True},
            },
            working={"s_lig": 125},
            norm_u={"s_lig": 0, "lig_legs": 0, "lig_d": 0},
            shear_remove_links_candidate_seen=False,
            shear_remove_links_candidate_truth_ok=False,
            shear_remove_links_candidate_dropped_reason=None,
            shear_remove_links_candidate_materiality="not_evaluated",
        )
        truth_rejected = module._prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(
            peval={"overview": {"all_key_pass": True, "utils": {"shear": "0.09"}}},
            preview={
                "s_lig": 0,
                "lig_legs": 0,
                "lig_d": 0,
                "actions": {"negligible": True},
            },
            working={"s_lig": 125},
            norm_u={"s_lig": 0, "lig_legs": 0, "lig_d": 0},
            shear_remove_links_candidate_seen=False,
            shear_remove_links_candidate_truth_ok=False,
            shear_remove_links_candidate_dropped_reason=None,
            shear_remove_links_candidate_materiality="not_evaluated",
        )
        ordinary_shear = module._prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(
            peval={"overview": {"all_key_pass": False, "utils": {"shear": "1.10"}}},
            preview={"s_lig": 85, "lig_legs": 6, "lig_d": 16},
            working={"s_lig": 125},
            norm_u={"D": 650, "lig_legs": 6, "lig_d": 16},
            shear_remove_links_candidate_seen=True,
            shear_remove_links_candidate_truth_ok=False,
            shear_remove_links_candidate_dropped_reason="existing",
            shear_remove_links_candidate_materiality="not_evaluated",
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "truth_ok": truth_ok,
        "truth_rejected": truth_rejected,
        "ordinary_shear": ordinary_shear,
        "action_context_calls": action_context_calls,
        "negligible_calls": negligible_calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator",
    )
    gate_start, gate_end, gate_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator",
    )
    aggregate_start, aggregate_end, aggregate_body = _function_segment(
        source,
        "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    scoring_loop_start, scoring_loop_end, scoring_loop_body = _function_segment(
        source, "_run_one_click_solver_candidate_scoring_loop_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "truth_ok_flags_preserved": runtime["truth_ok"] == {
            "s_new": 125.0,
            "legs_new": 0,
            "dia_new": 0,
            "has_geometry_change": False,
            "remove_links_candidate": True,
            "remove_links_truth_ok": True,
            "shear_remove_links_candidate_seen": True,
            "shear_remove_links_candidate_truth_ok": True,
            "shear_remove_links_candidate_dropped_reason": None,
            "shear_remove_links_candidate_materiality": "material_remove_links_truth_ok",
        },
        "truth_rejected_flags_preserved": runtime["truth_rejected"] == {
            "s_new": 125.0,
            "legs_new": 0,
            "dia_new": 0,
            "has_geometry_change": False,
            "remove_links_candidate": True,
            "remove_links_truth_ok": False,
            "shear_remove_links_candidate_seen": True,
            "shear_remove_links_candidate_truth_ok": False,
            "shear_remove_links_candidate_dropped_reason": "remove_links_truth_not_confirmed",
            "shear_remove_links_candidate_materiality": "not_evaluated",
        },
        "ordinary_geometry_values_preserved": runtime["ordinary_shear"] == {
            "s_new": 85.0,
            "legs_new": 6,
            "dia_new": 16,
            "has_geometry_change": True,
            "remove_links_candidate": False,
            "remove_links_truth_ok": False,
            "shear_remove_links_candidate_seen": True,
            "shear_remove_links_candidate_truth_ok": False,
            "shear_remove_links_candidate_dropped_reason": "existing",
            "shear_remove_links_candidate_materiality": "not_evaluated",
        },
        "truth_probe_only_runs_for_remove_links_candidates": len(runtime["action_context_calls"]) == 2
        and len(runtime["negligible_calls"]) == 2,
    }
    static_checks = {
        "solver_delegates_candidate_scoring_loop": (
            "_run_one_click_solver_candidate_scoring_loop_coordinator(" in solve_body
        ),
        "helper_present": "def _prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(" in source,
        "helper_preserves_spacing_leg_diameter_reads": (
            '_float_from_state(preview, "s_lig", s_now)' in helper
            and '_int_from_state(preview, "lig_legs", 0)' in helper
            and '_int_from_state(preview, "lig_d", 0)' in helper
        ),
        "helper_preserves_remove_links_candidate_gate": (
            'any(k in norm_u for k in ("lig_d", "lig_legs", "s_lig"))' in helper
            and "legs_new <= 0" in helper
            and "dia_new <= 0" in helper
        ),
        "helper_preserves_truth_probe": "_build_design_actions_context(preview)" in helper
        and "_shear_demands_negligible(preview_actions)" in helper
        and "GUIDANCE_SHEAR_UTIL_NEGLIGIBLE" in helper,
        "helper_preserves_truth_and_failure_flags": "material_remove_links_truth_ok" in helper
        and "remove_links_truth_not_confirmed" in helper,
        "helper_returns_layout_values": '"s_new": s_new' in helper
        and '"legs_new": legs_new' in helper
        and '"dia_new": dia_new' in helper
        and '"has_geometry_change": any(k in norm_u for k in ("D", "b", "bw"))' in helper,
        "aggregate_delegates_remove_links_truth_state": (
            "_prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(" in aggregate_body
        ),
        "aggregate_rehydrates_remove_links_truth_state": (
            's_new = shear_remove_links_truth_state["s_new"]' in aggregate_body
            and 'remove_links_truth_ok = shear_remove_links_truth_state[' in aggregate_body
            and 'shear_remove_links_candidate_materiality = shear_remove_links_truth_state[' in aggregate_body
        ),
        "aggregate_keeps_shear_rejection_order_after_truth_state": (
            aggregate_body.index("_prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(")
            < aggregate_body.index("_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(")
            and gate_body.index('rejection_reason="spacing_too_weak_for_shear_recovery"')
            < gate_body.index('rejection_reason="web_crushing_marginal"')
            < gate_body.index('rejection_reason="impractical_shear_layout"')
        ),
        "solver_delegates_shear_truth_preview_gate": (
            "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator(" in scoring_loop_body
        ),
        "solver_no_longer_builds_truth_probe_inline": "_build_design_actions_context(preview)" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_shear_remove_links_truth_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "gate_segment": {
            "function": "_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator",
            "start_line": gate_start,
            "end_line": gate_end,
            "line_count": gate_end - gate_start + 1,
        },
        "aggregate_segment": {
            "function": "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator",
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
        "runtime_checks": runtime_checks,
        "runtime": runtime,
        "product_behavior_changed": False,
        "next_safe_slice": "extract shear preview rejection gate coordinator",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_shear_remove_links_truth_state_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_shear_remove_links_truth_state_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Shear Remove Links Truth State Coordinator Extraction",
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
