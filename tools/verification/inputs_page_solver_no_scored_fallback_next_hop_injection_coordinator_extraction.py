"""Verify no-scored fallback next-hop injection coordinator extraction."""

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
        "_one_click_still_materially_under_target": getattr(module, "_one_click_still_materially_under_target", None),
        "_one_click_best_next_hop_improving_candidate": getattr(module, "_one_click_best_next_hop_improving_candidate", None),
        "_one_click_exhaustion_next_hop_allowed": getattr(module, "_one_click_exhaustion_next_hop_allowed", None),
        "_one_click_diff_accumulated_updates": getattr(module, "_one_click_diff_accumulated_updates", None),
        "_build_target_band_fallback_scored_candidate": getattr(module, "_build_target_band_fallback_scored_candidate", None),
        "_candidate_state_signature": getattr(module, "_candidate_state_signature", None),
    }
    calls: list[dict[str, Any]] = []
    payloads = {
        "direct": {"updates": {"D": 650}, "eval": {"id": "direct"}, "state": {"D": 650}},
        "diff": {"updates": {}, "eval": {"id": "diff"}, "state": {"b": 350}},
        "denied": {"updates": {"D": 700}, "eval": {"id": "denied"}, "state": {"D": 700}},
    }
    active_case = {"name": "direct"}

    def _still_under(cur_eval: dict[str, Any], mode_config: Any, margin: float) -> bool:
        calls.append({"fn": "still_under", "margin": margin})
        return bool(cur_eval.get("still_under", True))

    def _next_hop(cur_eval: dict[str, Any], mode_config: Any) -> dict[str, Any]:
        calls.append({"fn": "next_hop", "case": active_case["name"]})
        return dict(payloads[active_case["name"]])

    def _allowed(cur_eval: dict[str, Any], next_hop_payload: dict[str, Any] | None, mode_config: Any) -> bool:
        calls.append({"fn": "allowed", "has_payload": isinstance(next_hop_payload, dict)})
        return active_case["name"] != "denied" and isinstance(next_hop_payload, dict)

    def _diff(base: dict[str, Any], final: dict[str, Any]) -> dict[str, Any]:
        calls.append({"fn": "diff", "base": dict(base), "final": dict(final)})
        return {"diffed": True, **final}

    def _row(*, next_hop_payload: dict[str, Any], updates: dict[str, Any], signature: Any) -> dict[str, Any]:
        calls.append({"fn": "row", "updates": dict(updates), "signature": signature})
        return {"row": True, "updates": dict(updates), "signature": signature}

    def _sig(eval_obj: dict[str, Any]) -> tuple[str, str]:
        return ("sig", str(eval_obj.get("id")))

    try:
        module._one_click_still_materially_under_target = _still_under
        module._one_click_best_next_hop_improving_candidate = _next_hop
        module._one_click_exhaustion_next_hop_allowed = _allowed
        module._one_click_diff_accumulated_updates = _diff
        module._build_target_band_fallback_scored_candidate = _row
        module._candidate_state_signature = _sig

        active_case["name"] = "direct"
        direct_scored: list[dict[str, Any]] = []
        direct = module._handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(
            scored=direct_scored,
            cur_eval={"still_under": True},
            working={"D": 600},
            mode_config={"mode": "balanced"},
            tightening_mode_active=True,
        )
        active_case["name"] = "diff"
        diff_scored: list[dict[str, Any]] = []
        diff = module._handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(
            scored=diff_scored,
            cur_eval={"still_under": True},
            working={"D": 600},
            mode_config={"mode": "balanced"},
            tightening_mode_active=True,
        )
        active_case["name"] = "denied"
        denied_scored: list[dict[str, Any]] = []
        denied = module._handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(
            scored=denied_scored,
            cur_eval={"still_under": True},
            working={"D": 600},
            mode_config={"mode": "balanced"},
            tightening_mode_active=True,
        )
        already_scored = module._handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(
            scored=[{"existing": True}],
            cur_eval={"still_under": True},
            working={"D": 600},
            mode_config={"mode": "balanced"},
            tightening_mode_active=True,
        )
    finally:
        for name, original in originals.items():
            if original is not None:
                setattr(module, name, original)
            elif hasattr(module, name):
                delattr(module, name)

    return {
        "direct": direct,
        "diff": diff,
        "denied": denied,
        "already_scored": already_scored,
        "calls": calls,
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator",
    )
    aggregate_start, aggregate_end, aggregate = _function_segment(
        source,
        "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator",
    )
    solve_start, solve_end, solve_body = _function_segment(source, "_solve_one_click_to_target")
    selection_state_start, selection_state_end, selection_state_body = _function_segment(
        source, "_resolve_one_click_solver_scored_candidate_selection_state_coordinator"
    )
    _, _, post_selection_dispatch_body = _function_segment(
        source, "_dispatch_one_click_solver_post_selection_candidate_selection_state_coordinator"
    )
    _, _, fallback_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_fallback_pool_trace_from_selection_coordinator",
    )
    _, _, fallback_unpack_body = _function_segment(
        source,
        "_unpack_one_click_solver_candidate_fallback_pool_trace_state_coordinator",
    )
    _, _, selection_result_body = _function_segment(
        source,
        "_build_one_click_solver_scored_candidate_selection_state_result_coordinator",
    )
    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_cases(module)
    runtime_checks = {
        "direct_updates_injects_row_and_flags": runtime["direct"] == {
            "scored": [{"row": True, "updates": {"D": 650}, "signature": ("sig", "direct")}],
            "fallback_next_hop_injected": True,
            "fallback_next_hop_reason": "guidance_exhausted_but_refinement_next_hop_exists",
        },
        "diff_fallback_injects_row_and_flags": runtime["diff"] == {
            "scored": [{"row": True, "updates": {"diffed": True, "b": 350}, "signature": ("sig", "diff")}],
            "fallback_next_hop_injected": True,
            "fallback_next_hop_reason": "guidance_exhausted_but_refinement_next_hop_exists",
        },
        "denied_path_preserves_empty_scored_and_flags": runtime["denied"] == {
            "scored": [],
            "fallback_next_hop_injected": False,
            "fallback_next_hop_reason": None,
        },
        "already_scored_skips_probe": runtime["already_scored"] == {
            "scored": [{"existing": True}],
            "fallback_next_hop_injected": False,
            "fallback_next_hop_reason": None,
        },
        "diff_called_for_empty_updates_only": len([c for c in runtime["calls"] if c["fn"] == "diff"]) == 1,
    }
    static_checks = {
        "solver_delegates_scored_candidate_selection_state": (
            "_resolve_one_click_solver_scored_candidate_selection_state_coordinator("
            in post_selection_dispatch_body
        ),
        "helper_present": "def _handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(" in source,
        "helper_preserves_empty_scored_gate": "if not scored:" in helper,
        "helper_preserves_still_under_gate": "_one_click_still_materially_under_target(cur_eval, mode_config, margin=0.03)" in helper,
        "helper_preserves_tightening_next_hop_lookup": (
            "tightening_mode_active and still_under_for_fallback" in helper
            and "_one_click_best_next_hop_improving_candidate(cur_eval, mode_config)" in helper
        ),
        "helper_preserves_exhaustion_allowance": "_one_click_exhaustion_next_hop_allowed(cur_eval, next_hop_payload, mode_config)" in helper,
        "helper_preserves_diff_fallback": "_one_click_diff_accumulated_updates(" in helper,
        "helper_preserves_fallback_row_builder": "_build_target_band_fallback_scored_candidate(" in helper,
        "helper_preserves_reason_flags": "guidance_exhausted_but_refinement_next_hop_exists" in helper,
        "aggregate_delegates_fallback_next_hop": (
            "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator(" in aggregate
        ),
        "aggregate_rehydrates_fallback_state": (
            'scored = fallback_next_hop_state["scored"]' in aggregate
            and 'fallback_next_hop_injected = fallback_next_hop_state["fallback_next_hop_injected"]' in aggregate
            and 'fallback_next_hop_reason = fallback_next_hop_state["fallback_next_hop_reason"]' in aggregate
        ),
        "solver_delegates_candidate_fallback_pool_trace": (
            "_dispatch_one_click_solver_candidate_fallback_pool_trace_from_selection_coordinator("
            in selection_state_body
            and "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator("
            in fallback_dispatch_body
        ),
        "selection_state_rehydrates_candidate_fallback_state": (
            'candidate_fallback_pool_trace_state["scored"]' in fallback_unpack_body
            and '"fallback_next_hop_injected": fallback_next_hop_injected'
            in selection_result_body
            and '"fallback_next_hop_reason": fallback_next_hop_reason'
            in selection_result_body
        ),
        "solver_no_longer_owns_next_hop_lookup_inline": "_one_click_best_next_hop_improving_candidate(cur_eval, mode_config)" not in solve_body,
    }
    status = "PASS"
    if not all(static_checks.values()) or not all(runtime_checks.values()):
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_no_scored_fallback_next_hop_injection_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_no_scored_fallback_next_hop_injection_coordinator",
            "start_line": helper_start,
            "end_line": helper_end,
            "line_count": helper_end - helper_start + 1,
        },
        "aggregate_segment": {
            "function": "_handle_one_click_solver_candidate_fallback_pool_trace_coordinator",
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
        "next_safe_slice": "extract no-scored stop branch state handoff",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_no_scored_fallback_next_hop_injection_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_no_scored_fallback_next_hop_injection_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver No-Scored Fallback Next-Hop Injection Coordinator Extraction",
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
