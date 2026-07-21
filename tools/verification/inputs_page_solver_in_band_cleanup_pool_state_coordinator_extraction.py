"""Verify one-click solver in-band cleanup and pool state coordinator extraction."""

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
    original_cleanup = getattr(module, "_one_click_in_band_shear_cleanup_deferral", None)
    calls: list[dict[str, Any]] = []

    try:
        module._one_click_in_band_shear_cleanup_deferral = lambda working, cur_eval, mode_config: {
            "active": False,
            "reason": "not_needed",
            "recommendation": None,
            "candidate_eval": None,
        }
        stop_ready = module._prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator(
            working={"D": 650},
            cur_eval={"overview": {}},
            mode_config={"mode": "probe"},
            cur_pass=True,
            cur_ib=True,
            tightening_mode_active=False,
            governing_domain="bending",
        )

        def _cleanup(working: dict, cur_eval: dict, mode_config: dict) -> dict[str, Any]:
            calls.append({"working": dict(working), "mode_config": dict(mode_config)})
            return {
                "active": True,
                "reason": "blocked_non_governing_shear_cleanup_available",
                "recommendation": {"label": "Remove excess shear links"},
                "candidate_eval": {"overview": {}},
            }

        module._one_click_in_band_shear_cleanup_deferral = _cleanup
        cleanup_active = module._prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator(
            working={"D": 650},
            cur_eval={"overview": {}},
            mode_config={"mode": "probe"},
            cur_pass=True,
            cur_ib=True,
            tightening_mode_active=False,
            governing_domain="bending",
        )

        not_in_band = module._prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator(
            working={"D": 650},
            cur_eval={"overview": {}},
            mode_config={"mode": "probe"},
            cur_pass=False,
            cur_ib=False,
            tightening_mode_active=True,
            governing_domain="crack",
        )
    finally:
        if original_cleanup is not None:
            module._one_click_in_band_shear_cleanup_deferral = original_cleanup

    return {
        "stop_ready": stop_ready,
        "cleanup_active": cleanup_active,
        "not_in_band": not_in_band,
        "calls": calls,
    }


def _pool_defaults_ok(result: dict[str, Any], governing_domain: str, shear_active: bool) -> bool:
    return (
        result["final_governing_domain"] == governing_domain
        and result["shear_governing_mode_active"] is shear_active
        and result["shear_governing_family_detected"] is False
        and result["pruned_non_shear_family_count"] == 0
        and result["domain_match_prune_used"] is False
        and result["shear_prune_rule_source"] is None
        and result["material_improvement_threshold"] == 1e-3
        and result["tightening_meta"] == {
            "candidate_families_considered": [],
            "candidate_families_pruned": [],
            "governing_domain": governing_domain,
        }
    )


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    iteration_gate_start, iteration_gate_end, iteration_gate_body = _function_segment(
        source, "_prepare_one_click_solver_iteration_gate_state_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    stop_ready = runtime["stop_ready"]
    cleanup_active = runtime["cleanup_active"]
    not_in_band = runtime["not_in_band"]
    runtime_checks = {
        "stop_ready_state_preserved": stop_ready["in_band_shear_cleanup_deferral"] == {
            "active": False,
            "reason": "not_needed",
            "recommendation": None,
            "candidate_eval": None,
        }
        and stop_ready["tightening_mode_active"] is False
        and stop_ready["governing_domain"] == "bending"
        and stop_ready["should_stop_current_reached_target_band"] is True
        and _pool_defaults_ok(stop_ready, "bending", False),
        "active_cleanup_forces_shear_and_blocks_stop": cleanup_active["in_band_shear_cleanup_deferral"]["active"]
        is True
        and cleanup_active["tightening_mode_active"] is True
        and cleanup_active["governing_domain"] == "shear"
        and cleanup_active["should_stop_current_reached_target_band"] is False
        and _pool_defaults_ok(cleanup_active, "shear", True)
        and runtime["calls"] == [{"working": {"D": 650}, "mode_config": {"mode": "probe"}}],
        "not_in_band_defaults_preserved": not_in_band["in_band_shear_cleanup_deferral"] == {
            "active": False,
            "reason": "not_applicable",
            "recommendation": None,
            "candidate_eval": None,
        }
        and not_in_band["tightening_mode_active"] is True
        and not_in_band["governing_domain"] == "crack"
        and not_in_band["should_stop_current_reached_target_band"] is False
        and _pool_defaults_ok(not_in_band, "crack", False),
    }
    static_checks = {
        "solver_delegates_iteration_gate_state": (
            "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator("
            in solve_body
            and "_prepare_one_click_solver_iteration_gate_state_coordinator(" in source
        ),
        "helper_present": "def _prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator(" in source,
        "helper_preserves_default_deferral": '"reason": "not_applicable"' in helper,
        "helper_preserves_cleanup_probe": "_one_click_in_band_shear_cleanup_deferral(" in helper,
        "helper_preserves_active_cleanup_shear_override": 'governing_domain = "shear"' in helper
        and "tightening_mode_active = True" in helper,
        "helper_preserves_pool_defaults": '"shear_governing_family_detected": False' in helper
        and '"pruned_non_shear_family_count": 0' in helper
        and '"material_improvement_threshold": 1e-3' in helper
        and '"candidate_families_considered": []' in helper,
        "helper_preserves_stop_gate": '"should_stop_current_reached_target_band"' in helper
        and "cur_pass and cur_ib and not bool(in_band_shear_cleanup_deferral.get(\"active\"))" in helper,
        "solver_delegates_in_band_cleanup_pool_state": "_prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator("
        in iteration_gate_body,
        "solver_preserves_current_stop_call": "_trace_current_reached_target_band_solver_stop_coordinator("
        in iteration_gate_body,
        "solver_rehydrates_in_band_cleanup_pool_fields": 'in_band_shear_cleanup_deferral = in_band_cleanup_pool_state["in_band_shear_cleanup_deferral"]'
        in iteration_gate_body
        and 'tightening_meta = in_band_cleanup_pool_state["tightening_meta"]' in iteration_gate_body
        and 'if in_band_cleanup_pool_state["should_stop_current_reached_target_band"]:' in iteration_gate_body,
        "solver_no_longer_inlines_cleanup_pool_state": '"reason": "not_applicable"' not in solve_body
        and "_one_click_in_band_shear_cleanup_deferral(\n                working,\n                cur_eval,\n                mode_config,"
        not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_in_band_cleanup_pool_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_in_band_cleanup_and_pool_state_coordinator",
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
        "next_safe_slice": "extract tightening-depth budget gate state",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_in_band_cleanup_pool_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_in_band_cleanup_pool_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver In-Band Cleanup Pool State Coordinator Extraction",
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
