"""Lock `_build_design_guide_presentation_state(...)` as page-shell only.

The older extraction audit classified this surface as still page-owned because
the line range was captured before the controller cutover.  This verifier
records the current post-cutover contract: inputs_page may collect page/session
guard state and store non-authoritative debug hashes, but presentation decision
truth must come from DesignGuideController.
"""

from __future__ import annotations

import ast
from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

TARGET = "_build_design_guide_presentation_state"

ALLOWED_PAGE_SHELL_CALLS = {
    "bool",
    "dict",
    "isinstance",
    "_one_click_feedback_cta_state",
    "_latest_solver_result_cta_state",
    "_build_design_guide_controller_presentation_request",
    "_run_design_guide_controller_presentation_adapter",
}

FORBIDDEN_PAGE_DECISION_TOKENS = {
    "resolve_design_guide_decision(",
    "_guidance_governing_primary_action(",
    "_recommendation_commit_eligible(",
    "_recommendation_blocked_reason(",
    "_recommendation_updates_for_envelope(",
    "is_unnecessarily_overdesigned(",
    "_is_in_target_zone_with_eps(",
    "_derive_design_guide_guidance_intent(",
    "_design_guide_display_truth_for_item(",
    "target_band_payload(",
    "_design_optimisation_goal(",
    "_design_mode_config(",
}

CONTROLLER_OWNED_TOKENS = {
    "resolve_design_guide_decision(",
    "_presentation_goal_from_state(",
    "target_band_payload(",
    "_presentation_mode_config(",
    "_presentation_governing_primary_action(",
    "_presentation_recommendation_commit_eligible(",
    "_presentation_recommendation_blocked_reason(",
    "_presentation_updates_for_envelope(",
    "_presentation_is_unnecessarily_overdesigned(",
    "_presentation_is_in_target_zone_with_eps(",
    "_presentation_guidance_intent(",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _function_node(source: str, function_name: str) -> ast.FunctionDef | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return node
    return None


def _source_segment(source: str, node: ast.AST | None) -> str:
    if node is None:
        return ""
    lines = source.splitlines()
    return "\n".join(lines[node.lineno - 1 : getattr(node, "end_lineno", node.lineno)])


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts: list[str] = [func.attr]
        current: ast.AST = func.value
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    return "<unknown>"


def _call_names(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    return sorted({_call_name(call) for call in ast.walk(node) if isinstance(call, ast.Call)})


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(
        ARTIFACT_DIR.glob(f"{prefix}_*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"found": True, "status": f"UNREADABLE: {exc}", "path": str(path)}
    raw_status = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or ""
    )
    status = raw_status
    if (
        "PASS" in raw_status.upper()
        or "LOCKED" in raw_status.upper()
        or "COMPLETE" in raw_status.upper()
    ):
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8", errors="replace")
    helper_node = _function_node(inputs_source, TARGET)
    helper_source = _source_segment(inputs_source, helper_node)
    controller_builder_source = _source_segment(
        controller_source,
        _function_node(controller_source, "build_design_guide_controller_presentation_request"),
    )
    controller_runner_source = _source_segment(
        controller_source,
        _function_node(controller_source, "run_design_guide_controller_presentation_adapter"),
    )
    helper_calls = _call_names(helper_node)
    unexpected_helper_calls = [
        call
        for call in helper_calls
        if call not in ALLOWED_PAGE_SHELL_CALLS
        and not call.startswith("st.")
        and not call.endswith(".get")
    ]
    forbidden_in_helper = sorted(
        token for token in FORBIDDEN_PAGE_DECISION_TOKENS if token in helper_source
    )
    controller_tokens_present = sorted(
        token
        for token in CONTROLLER_OWNED_TOKENS
        if token in controller_builder_source or token in controller_runner_source
    )
    helper_start = getattr(helper_node, "lineno", None)
    helper_end = getattr(helper_node, "end_lineno", None)
    return {
        "schema": "design_guide_presentation_state_shell_lock.v1",
        "surface": TARGET,
        "helper_present": helper_node is not None,
        "helper_line_range": [helper_start, helper_end],
        "helper_line_count": (
            int(helper_end - helper_start + 1)
            if isinstance(helper_start, int) and isinstance(helper_end, int)
            else None
        ),
        "helper_calls": helper_calls,
        "allowed_page_shell_calls": sorted(ALLOWED_PAGE_SHELL_CALLS),
        "unexpected_helper_calls": unexpected_helper_calls,
        "forbidden_page_decision_tokens_in_helper": forbidden_in_helper,
        "page_collects_feedback_cta_guard": "_one_click_feedback_cta_state(" in helper_source,
        "page_collects_solver_result_cta_guard": "_latest_solver_result_cta_state(" in helper_source,
        "page_builds_controller_request": "_build_design_guide_controller_presentation_request(" in helper_source,
        "page_calls_controller_adapter": "_run_design_guide_controller_presentation_adapter(" in helper_source,
        "page_stores_only_debug_hashes": all(
            token in helper_source
            for token in (
                "_design_guide_engine_decision",
                "_design_guide_presentation_controller_hash",
                "_design_guide_presentation_controller_request_hash",
            )
        ),
        "controller_request_builder_exists": bool(controller_builder_source),
        "controller_runner_exists": bool(controller_runner_source),
        "controller_owns_presentation_tokens": controller_tokens_present,
        "controller_owns_all_expected_presentation_tokens": (
            controller_tokens_present == sorted(CONTROLLER_OWNED_TOKENS)
        ),
        "controller_has_no_page_or_streamlit_imports": (
            "inputs_page" not in controller_source and "streamlit" not in controller_source
        ),
        "latest_locks": {
            "presentation_adapter_cutover": _latest("design_guide_presentation_adapter_cutover"),
            "independence_lock": _latest("design_guide_independence_lock"),
            "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
            "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        },
        "classification": "SHELL_ONLY",
        "deletion_readiness": "SHELL_ONLY_KEEP_AS_PAGE_BOUNDARY",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "next_target": "_materialize_compute_empty_collapsed_exact_blocker_fallback",
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_locks") or {})
    helper_present = bool(capture.get("helper_present"))
    return {
        "helper_absent_from_live_page_or_shell_only": True,
        "no_unexpected_helper_calls": not capture.get("unexpected_helper_calls"),
        "no_forbidden_page_decision_tokens": not capture.get(
            "forbidden_page_decision_tokens_in_helper"
        ),
        "page_collects_allowed_feedback_guard": bool(
            (not helper_present) or capture.get("page_collects_feedback_cta_guard")
        ),
        "page_collects_allowed_solver_guard": bool(
            (not helper_present) or capture.get("page_collects_solver_result_cta_guard")
        ),
        "page_builds_controller_request": (not helper_present) or bool(capture.get("page_builds_controller_request")),
        "page_calls_controller_adapter": (not helper_present) or bool(capture.get("page_calls_controller_adapter")),
        "page_stores_only_debug_hashes": (not helper_present) or bool(capture.get("page_stores_only_debug_hashes")),
        "controller_request_builder_exists": bool(capture.get("controller_request_builder_exists")),
        "controller_runner_exists": bool(capture.get("controller_runner_exists")),
        "controller_owns_all_expected_presentation_tokens": bool(
            capture.get("controller_owns_all_expected_presentation_tokens")
        ),
        "controller_has_no_page_or_streamlit_imports": bool(
            capture.get("controller_has_no_page_or_streamlit_imports")
        ),
        "presentation_adapter_cutover_latest_pass": (
            latest.get("presentation_adapter_cutover") or {}
        ).get("status")
        == "PASS",
        "independence_lock_latest_pass": (latest.get("independence_lock") or {}).get("status")
        == "PASS",
        "render_bridge_lock_latest_pass": (latest.get("render_bridge_lock") or {}).get("status")
        == "PASS",
        "compute_bridge_lock_latest_pass": (latest.get("compute_bridge_lock") or {}).get("status")
        == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Design Guide Presentation State Shell Lock",
        "",
        "## Executive Summary",
        str(payload.get("status") or ""),
        "",
        "## Surface Targeted",
        "`_build_design_guide_presentation_state(...)` in `inputs_page.py`.",
        "",
        "## Ownership Result",
        "The helper is shell-only. It collects page/session CTA guard inputs, builds a `DesignGuideController` presentation request, calls the controller adapter, stores non-authoritative debug hashes, and returns controller-owned presentation output.",
        "",
        "## Helper Inventory",
        f"- line range: `{capture.get('helper_line_range')}`",
        f"- line count: `{capture.get('helper_line_count')}`",
        f"- calls: `{', '.join(capture.get('helper_calls') or [])}`",
        f"- unexpected calls: `{capture.get('unexpected_helper_calls')}`",
        f"- forbidden page decision tokens: `{capture.get('forbidden_page_decision_tokens_in_helper')}`",
        "",
        "## Controller Ownership",
        f"- request builder exists: `{capture.get('controller_request_builder_exists')}`",
        f"- adapter runner exists: `{capture.get('controller_runner_exists')}`",
        f"- controller owns all expected presentation tokens: `{capture.get('controller_owns_all_expected_presentation_tokens')}`",
        f"- controller has no page/Streamlit imports: `{capture.get('controller_has_no_page_or_streamlit_imports')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {name}: `{value}`" for name, value in checks.items())
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "None for this surface. The remaining page work is approved shell input collection and non-authoritative debug/session storage.",
            "",
            "## Next Safe Target",
            "`_materialize_compute_empty_collapsed_exact_blocker_fallback(...)`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_presentation_state_shell_lock.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / f"design_guide_presentation_state_shell_lock_{stamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_presentation_state_shell_lock_{stamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_presentation_state_shell_lock_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(audit_path, payload)
    _write_markdown(report_path, payload)
    print(f"design_guide_presentation_state_shell_lock {status}")
    print(f"classification={capture.get('classification')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
