"""Verify one-click solver initial state coordinator extraction."""

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
        "_rescue_mode_default_debug": getattr(module, "_rescue_mode_default_debug", None),
        "_build_one_click_solver_trace_callback_coordinator": getattr(
            module,
            "_build_one_click_solver_trace_callback_coordinator",
            None,
        ),
        "_guidance_state_snapshot": getattr(module, "_guidance_state_snapshot", None),
        "_overlay_current_normalized_shear_truth": getattr(
            module,
            "_overlay_current_normalized_shear_truth",
            None,
        ),
        "_build_canonical_design_state_pack": getattr(module, "_build_canonical_design_state_pack", None),
        "_design_state_coherence_check": getattr(module, "_design_state_coherence_check", None),
        "_canonical_pack_is_valid": getattr(module, "_canonical_pack_is_valid", None),
    }
    calls: list[dict[str, Any]] = []
    pack = {
        "canonical_pack_error": "bad_pack",
        "canonical_pack_error_stage": "canonical",
        "nested": {"value": 1},
    }

    def _trace_factory(**kwargs: Any):
        calls.append({"factory": dict(kwargs)})

        def _trace(event: str, data: dict[str, Any]) -> None:
            calls.append({"trace": event, "data": dict(data)})

        return _trace

    try:
        module._rescue_mode_default_debug = lambda: {"rescue": "default"}
        module._build_one_click_solver_trace_callback_coordinator = _trace_factory
        module._guidance_state_snapshot = lambda state: {"snap": dict(state)}
        module._overlay_current_normalized_shear_truth = lambda state: {"truth": dict(state)}
        module._build_canonical_design_state_pack = lambda state: pack
        module._design_state_coherence_check = lambda snapshot: {
            "coherence_should_block": False,
            "coherence_blocking_issues": ["coherence_issue"],
        }
        module._canonical_pack_is_valid = lambda snapshot: False
        result = module._prepare_one_click_solver_initial_state_coordinator(
            state={"D": 650},
            trace_run_id="run-123",
            trace_source="unit_source",
            rescue_attempted_seed_keys=("", "seed-a", 7),
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)

    result["initial_snapshot"]["nested"]["value"] = 2
    copy_isolated = pack["nested"]["value"] == 1
    result["initial_snapshot"]["nested"]["value"] = 1
    result["trace_callback"]("probe", {"ok": True})
    return {"result": result, "calls": calls, "copy_isolated": copy_isolated}


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_prepare_one_click_solver_initial_state_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    runtime_setup_start, runtime_setup_end, runtime_setup_body = _function_segment(
        source, "_prepare_one_click_solver_runtime_setup_state_coordinator"
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    result = runtime["result"]
    runtime_checks = {
        "trace_factory_args_preserved": runtime["calls"][0] == {
            "factory": {
                "rid": "run-123",
                "stop_traced": [False],
                "trace_source": "unit_source",
            },
        },
        "trace_callback_preserved": runtime["calls"][-1] == {"trace": "probe", "data": {"ok": True}},
        "rescue_and_seed_state_preserved": result["rescue_debug"] == {"rescue": "default"}
        and result["attempted_seed_keys"] == {"seed-a", "7"},
        "initial_snapshot_copy_preserved": result["initial_snapshot"] == {
            "canonical_pack_error": "bad_pack",
            "canonical_pack_error_stage": "canonical",
            "nested": {"value": 1},
        }
        and runtime["copy_isolated"],
        "initial_block_state_preserved": result["rid"] == "run-123"
        and result["initial_coherence"] == {
            "coherence_should_block": False,
            "coherence_blocking_issues": ["coherence_issue"],
        }
        and result["initial_pack_valid"] is False
        and result["initial_coherence_should_block"] is False
        and result["initial_stop_reason"] == "bad_pack",
    }
    static_checks = {
        "solver_delegates_runtime_setup_state": (
            "_prepare_one_click_solver_runtime_setup_state_coordinator(" in solve_body
        ),
        "helper_present": "def _prepare_one_click_solver_initial_state_coordinator(" in source,
        "helper_preserves_trace_factory": "_build_one_click_solver_trace_callback_coordinator(" in helper,
        "helper_preserves_rescue_debug": "_rescue_mode_default_debug()" in helper,
        "helper_preserves_attempted_seed_filter": "set(str(k) for k in (rescue_attempted_seed_keys or ()) if str(k))"
        in helper,
        "helper_preserves_initial_snapshot_pipeline": "_guidance_state_snapshot(dict(state or {}))" in helper
        and "_overlay_current_normalized_shear_truth(" in helper
        and "_build_canonical_design_state_pack(" in helper
        and "copy.deepcopy(" in helper,
        "helper_preserves_initial_stop_reason": "canonical_pack_error" in helper
        and "state_incoherent_after_rebuild" in helper,
        "solver_delegates_initial_state": "_prepare_one_click_solver_initial_state_coordinator(" in runtime_setup_body,
        "solver_rehydrates_initial_state_fields": 'rid = solver_initial_state["rid"]' in runtime_setup_body
        and 'initial_snapshot = solver_initial_state["initial_snapshot"]' in runtime_setup_body
        and 'initial_stop_reason = solver_initial_state["initial_stop_reason"]' in runtime_setup_body,
        "solver_no_longer_inlines_initial_snapshot_pipeline": "_guidance_state_snapshot(dict(state or {}))"
        not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_initial_state_coordinator",
        "helper_segment": {
            "function": "_prepare_one_click_solver_initial_state_coordinator",
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
            "copy_isolated": runtime["copy_isolated"],
            "result_without_callback": {
                key: sorted(value) if isinstance(value, set) else value
                for key, value in result.items()
                if key != "trace_callback"
            },
        },
        "product_behavior_changed": False,
        "next_safe_slice": "extract initial solver mode and target-band setup",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / f"inputs_page_solver_initial_state_coordinator_extraction_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_page_solver_initial_state_coordinator_extraction_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Initial State Coordinator Extraction",
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
