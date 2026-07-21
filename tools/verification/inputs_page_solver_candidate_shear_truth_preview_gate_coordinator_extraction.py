"""Verify candidate shear truth and preview gate coordinator extraction."""

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
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            lines = source.splitlines()
            return start, end, "\n".join(lines[start - 1 : end])
    raise AssertionError(f"Function not found: {name}")


def _patch(module: Any, replacements: dict[str, Any]) -> dict[str, Any]:
    originals = {name: getattr(module, name, _MISSING) for name in replacements}
    for name, value in replacements.items():
        setattr(module, name, value)
    return originals


def _restore(module: Any, originals: dict[str, Any]) -> None:
    for name, original in originals.items():
        if original is _MISSING:
            delattr(module, name)
        else:
            setattr(module, name, original)


def _call(module: Any, **overrides: Any) -> dict[str, Any]:
    kwargs = {
        "governing_domain": "shear",
        "peval": {"overview": {}},
        "preview": {"D": 650},
        "working": {"D": 600},
        "norm_u": {"s_lig": 80},
        "mode_config": {"mode": "tight"},
        "step_idx": 2,
        "rc": {"title": "candidate"},
        "new_d": 0.12,
        "family_hint": "spacing_reduction",
        "shear_util_preview": 0.90,
        "web_util_preview": 0.80,
        "remove_links_candidate": False,
        "remove_links_truth_ok": False,
        "shear_remove_links_candidate_seen": False,
        "shear_remove_links_candidate_truth_ok": False,
        "shear_remove_links_candidate_dropped_reason": None,
        "shear_remove_links_candidate_materiality": "not_evaluated",
        "rejected_as_spacing_too_weak": 10,
        "rejected_as_web_crushing_marginal": 20,
        "rejected_as_impractical_shear_layout": 30,
        "trace_callback": lambda ev, dat: None,
    }
    kwargs.update(overrides)
    return module._handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator(**kwargs)


def _run_case(module: Any) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []

    def _truth(**kwargs: Any) -> dict[str, Any]:
        calls.append({"helper": "truth", "governing_domain": kwargs.get("governing_domain")})
        return {
            "s_new": 82.0,
            "legs_new": 6,
            "dia_new": 16,
            "has_geometry_change": False,
            "remove_links_candidate": True,
            "remove_links_truth_ok": True,
            "shear_remove_links_candidate_seen": True,
            "shear_remove_links_candidate_truth_ok": True,
            "shear_remove_links_candidate_dropped_reason": "truth-updated",
            "shear_remove_links_candidate_materiality": "material_remove_links_truth_ok",
        }

    def _gate(**kwargs: Any) -> dict[str, Any]:
        calls.append(
            {
                "helper": "gate",
                "s_new": kwargs.get("s_new"),
                "legs_new": kwargs.get("legs_new"),
                "dia_new": kwargs.get("dia_new"),
                "has_geometry_change": kwargs.get("has_geometry_change"),
            }
        )
        return {
            "rejected_as_spacing_too_weak": int(kwargs["rejected_as_spacing_too_weak"]) + 1,
            "rejected_as_web_crushing_marginal": int(kwargs["rejected_as_web_crushing_marginal"]),
            "rejected_as_impractical_shear_layout": int(kwargs["rejected_as_impractical_shear_layout"]),
            "should_continue": bool(kwargs.get("shear_util_preview", 0) > 1.04),
        }

    originals = _patch(
        module,
        {
            "_prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator": _truth,
            "_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator": _gate,
        },
    )
    try:
        non_shear = _call(module, governing_domain="bending")
        shear_pass = _call(module, shear_util_preview=0.90)
        shear_continue = _call(module, shear_util_preview=1.10)
    finally:
        _restore(module, originals)

    return {
        "calls": calls,
        "non_shear": non_shear,
        "shear_pass": shear_pass,
        "shear_continue": shear_continue,
        "matches": (
            calls == [
                {"helper": "truth", "governing_domain": None},
                {"helper": "gate", "s_new": 82.0, "legs_new": 6, "dia_new": 16, "has_geometry_change": False},
                {"helper": "truth", "governing_domain": None},
                {"helper": "gate", "s_new": 82.0, "legs_new": 6, "dia_new": 16, "has_geometry_change": False},
            ]
            and non_shear["should_continue"] is False
            and non_shear["remove_links_candidate"] is False
            and non_shear["rejected_as_spacing_too_weak"] == 10
            and shear_pass["remove_links_candidate"] is True
            and shear_pass["remove_links_truth_ok"] is True
            and shear_pass["shear_remove_links_candidate_seen"] is True
            and shear_pass["shear_remove_links_candidate_truth_ok"] is True
            and shear_pass["shear_remove_links_candidate_dropped_reason"] == "truth-updated"
            and shear_pass["rejected_as_spacing_too_weak"] == 11
            and shear_pass["should_continue"] is False
            and shear_continue["should_continue"] is True
        ),
    }


def build_payload() -> dict[str, Any]:
    source = _read(AUTO_DESIGN_COMPUTE)
    helper_start, helper_end, helper = _function_segment(
        source,
        "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator",
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
    _, _, post_metric_shear_dispatch_body = _function_segment(
        source,
        "_dispatch_one_click_solver_candidate_shear_truth_preview_gate_from_post_metric_coordinator",
    )
    _, _, pre_selection_body = _function_segment(
        source, "_run_one_click_solver_iteration_pre_selection_candidate_evaluation_coordinator"
    )

    import inputs_page_modules.auto_design_compute as module  # noqa: E402

    runtime = _run_case(module)
    static_checks = {
        "solver_delegates_iteration_loop": "_dispatch_one_click_solver_iteration_loop_from_solver_runtime_setup_coordinator(" in solve_body,
        "pre_selection_delegates_candidate_scoring_loop": (
            "_dispatch_one_click_solver_candidate_scoring_loop_from_pre_selection_coordinator(" in pre_selection_body
        ),
        "scoring_loop_delegates_single_candidate_flow": (
            "_run_one_click_solver_single_candidate_scoring_flow_coordinator(" in scoring_loop_body
        ),
        "single_candidate_flow_delegates_post_metric_scoring_flow": (
            "_run_one_click_solver_single_candidate_post_metric_scoring_flow_coordinator(" in single_candidate_body
        ),
        "helper_present": "def _handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator(" in source,
        "helper_preserves_non_shear_noop": 'if governing_domain != "shear":' in helper,
        "helper_delegates_truth_state": (
            "_prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(" in helper
        ),
        "helper_delegates_preview_gate": (
            "_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(" in helper
        ),
        "helper_orders_truth_before_preview_gate": (
            helper.index("_prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(")
            < helper.index("_handle_one_click_solver_candidate_shear_preview_rejection_gate_coordinator(")
        ),
        "helper_returns_truth_flags_and_preview_counters": all(
            token in helper
            for token in (
                '"remove_links_candidate"',
                '"remove_links_truth_ok"',
                '"shear_remove_links_candidate_seen"',
                '"shear_remove_links_candidate_truth_ok"',
                '"shear_remove_links_candidate_dropped_reason"',
                '"shear_remove_links_candidate_materiality"',
                '"rejected_as_spacing_too_weak"',
                '"rejected_as_web_crushing_marginal"',
                '"rejected_as_impractical_shear_layout"',
                '"should_continue"',
            )
        ),
        "post_metric_flow_delegates_shear_truth_preview_dispatch": (
            "_dispatch_one_click_solver_candidate_shear_truth_preview_gate_from_post_metric_coordinator("
            in post_metric_body
        ),
        "post_metric_shear_truth_preview_dispatch_delegates_gate": (
            "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator("
            in post_metric_shear_dispatch_body
            and "post_metric_scope[" in post_metric_shear_dispatch_body
        ),
        "post_metric_flow_rehydrates_truth_preview_state": all(
            token in post_metric_body
            for token in (
                'remove_links_candidate = shear_truth_preview_gate_state["remove_links_candidate"]',
                'remove_links_truth_ok = shear_truth_preview_gate_state["remove_links_truth_ok"]',
                'shear_remove_links_candidate_seen = shear_truth_preview_gate_state[',
                'rejected_as_spacing_too_weak = shear_truth_preview_gate_state[',
                'if shear_truth_preview_gate_state["should_continue"]:',
            )
        ),
        "scoring_loop_no_longer_delegates_shear_truth_preview_directly": (
            "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator(" not in scoring_loop_body
        ),
        "solver_no_longer_inlines_truth_state_call": (
            "_prepare_one_click_solver_candidate_shear_remove_links_truth_state_coordinator(" not in solve_body
        ),
    }
    status = "PASS"
    if not all(static_checks.values()) or not runtime["matches"]:
        status = "FAIL"
    return {
        "status": status,
        "surface": "_solve_one_click_to_target_shear_truth_preview_gate_coordinator",
        "helper_segment": {
            "function": "_handle_one_click_solver_candidate_shear_truth_and_preview_gate_coordinator",
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
        "runtime": {"matches": runtime["matches"]},
        "product_behavior_changed": False,
        "next_safe_slice": "extract wrong-direction and non-material scoring gates",
    }


def write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().isoformat(timespec="seconds").replace(":", "-")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_solver_candidate_shear_truth_preview_gate_coordinator_extraction_{stamp}.json"
    )
    md_path = AUDIT_DIR / (
        f"inputs_page_solver_candidate_shear_truth_preview_gate_coordinator_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Solver Candidate Shear Truth Preview Gate Coordinator Extraction",
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
            f"- Shear truth preview gate matches: `{payload['runtime']['matches']}`",
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
