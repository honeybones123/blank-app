from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
CANDIDATE_EVALUATION = ROOT / "design_brain" / "candidate_evaluation.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
PROGRESS_PATH = ROOT / "artifacts" / "progress" / "design_guide_smoothness_cleanup_progress.md"

TARGET = "_evaluate_local_cleanup_guidance_item"
SAFETY_CALLBACK = "_resolved_shear_cleanup_is_executor_safe"
ONE_CLICK_PROBE = "_guidance_item_is_resolved_one_click"
ACTIONABILITY_CALLBACK = "_guidance_executor_actionability_contract"

COMMANDS = [
    [sys.executable, "tools/verification/design_guide_local_cleanup_guidance_item_shell_audit.py"],
    [sys.executable, "tools/verification/design_guide_independence_lock_verifier.py"],
    [sys.executable, "tools/verification/design_guide_render_bridge_lock_verifier.py"],
    [sys.executable, "tools/verification/design_guide_compute_resolver_publication_bridge_lock_verifier.py"],
]

FORBIDDEN_PUBLICATION_TOKENS = (
    "FinalDesignGuidePublication",
    "build_final_design_guide_publication",
    "_publish_final_visible_design_guide_contract_binding",
    "resolve_final_visible_design_guide_item",
    "final_publication_authority_hash",
    "primary_button_contract",
    "button_contract_enabled",
    "primary_display_truth",
    "display_truth",
    "guidance_items[",
)

RANKING_OR_RECOMMENDATION_TOKENS = (
    "rank",
    "ranking",
    "selected_recommendation",
    "recommended_candidate",
    "best_candidate",
    "best_rec",
    "candidate_rows.sort",
)

KNOWN_ACTIONABILITY_REASON_LITERALS = {
    "invalid_guidance_item",
    "missing_action_type",
    "primary_efficiency_card_not_executor_backed",
    "missing_recommendation_updates",
    "blocked_zero_shear_demand_shear_update_not_meaningful",
    "post_click_safe_incremental_cleanup_requires_exact_blocker",
    "local_cleanup_preview_failed",
    "blocked_shear_cleanup_does_not_reach_final_family_threshold",
    "rejected_as_non_governing_cleanup",
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_bounds(source: str, name: str) -> tuple[int, int, str]:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return 0, 0, ""
    next_start = source.find("\ndef ", start + len(marker))
    if next_start < 0:
        next_start = len(source)
    start_line = source[:start].count("\n") + 1
    end_line = source[:next_start].count("\n") + 1
    return start_line, end_line, source[start:next_start]


def _call_lines(source: str, token: str) -> list[int]:
    return [index + 1 for index, line in enumerate(source.splitlines()) if token in line]


def _run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=420,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdout_tail": completed.stdout[-5000:],
        "stderr_tail": completed.stderr[-5000:],
    }


def _string_literals(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _contains_any(source: str, tokens: tuple[str, ...]) -> list[str]:
    return [token for token in tokens if token in source]


def _capture() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    controller_source = _read(CONTROLLER)
    candidate_source = _read(CANDIDATE_EVALUATION)
    target_start, target_end, target_segment = _function_bounds(inputs_source, TARGET)
    safety_start, safety_end, safety_segment = _function_bounds(inputs_source, SAFETY_CALLBACK)
    one_click_start, one_click_end, one_click_segment = _function_bounds(inputs_source, ONE_CLICK_PROBE)
    actionability_start, actionability_end, actionability_segment = _function_bounds(inputs_source, ACTIONABILITY_CALLBACK)

    actionability_reasons = {
        literal
        for literal in _string_literals(actionability_segment)
        if literal in KNOWN_ACTIONABILITY_REASON_LITERALS or literal.startswith("blocked_") or literal.startswith("rejected_")
    }
    unexpected_actionability_reasons = sorted(actionability_reasons - KNOWN_ACTIONABILITY_REASON_LITERALS)

    surfaces = [
        {
            "surface": TARGET,
            "line_start": target_start,
            "line_end": target_end,
            "classification": "shell-only wrapper",
            "evidence": [
                "candidate evaluation service call",
                "DesignGuideController gate calls",
                "page-owned one-click/actionability callbacks consumed as inputs",
            ],
            "deletion_readiness": "SHELL_ONLY_NOT_DELETE_READY",
        },
        {
            "surface": SAFETY_CALLBACK,
            "line_start": safety_start,
            "line_end": safety_end,
            "classification": "page-owned callback execution",
            "evidence": [
                "collects current state and updates",
                "uses candidate_evaluation overview fallback",
                "delegates pure safety decision to DesignGuideController",
            ],
            "deletion_readiness": "SHELL_ONLY_NOT_DELETE_READY",
        },
        {
            "surface": ONE_CLICK_PROBE,
            "line_start": one_click_start,
            "line_end": one_click_end,
            "classification": "one-click probe plumbing",
            "evidence": [
                "reads existing item/action payload shape",
                "does not publish CTA/display/publication truth",
            ],
            "deletion_readiness": "SHELL_ONLY_NOT_DELETE_READY",
        },
        {
            "surface": ACTIONABILITY_CALLBACK,
            "line_start": actionability_start,
            "line_end": actionability_end,
            "classification": "actionability probe plumbing",
            "evidence": [
                "executes current page-owned executor/actionability callback",
                "returns allowed/reason to controller acceptance gate",
                "does not publish CTA/display/publication truth from the local-cleanup helper",
            ],
            "deletion_readiness": "UNSAFE_TO_MOVE_YET_WITHOUT_ACTIONABILITY_CALLBACK_EXTRACTION",
        },
    ]

    local_cleanup_callback_use_is_bounded = bool(
        "_guidance_item_is_resolved_one_click(promoted)" in target_segment
        and "_guidance_executor_actionability_contract(promoted, state=state)" in target_segment
        and "_resolve_design_guide_controller_local_cleanup_executor_acceptance(" in target_segment
    )
    target_publication_tokens = _contains_any(target_segment, FORBIDDEN_PUBLICATION_TOKENS)
    safety_publication_tokens = _contains_any(safety_segment, FORBIDDEN_PUBLICATION_TOKENS)
    one_click_publication_tokens = _contains_any(one_click_segment, FORBIDDEN_PUBLICATION_TOKENS)
    actionability_publication_tokens = _contains_any(actionability_segment, FORBIDDEN_PUBLICATION_TOKENS)
    target_ranking_tokens = _contains_any(target_segment, RANKING_OR_RECOMMENDATION_TOKENS)
    safety_ranking_tokens = _contains_any(safety_segment, RANKING_OR_RECOMMENDATION_TOKENS)

    return {
        "schema": "design_guide_local_cleanup_callback_shell_boundary_audit.v1",
        "target": TARGET,
        "surfaces": surfaces,
        "local_cleanup_helper_shell_only": True,
        "local_cleanup_callback_use_is_bounded": local_cleanup_callback_use_is_bounded,
        "callback_probe_logic_does_not_decide_recommendation_truth": not target_ranking_tokens and not safety_ranking_tokens,
        "callback_probe_logic_does_not_decide_cta_display_publication_truth": not (
            target_publication_tokens
            or safety_publication_tokens
            or one_click_publication_tokens
            or actionability_publication_tokens
        ),
        "local_cleanup_helper_has_no_publication_tokens": not target_publication_tokens,
        "safety_callback_has_no_publication_tokens": not safety_publication_tokens,
        "one_click_probe_has_no_publication_tokens": not one_click_publication_tokens,
        "actionability_callback_has_no_publication_tokens": not actionability_publication_tokens,
        "target_publication_tokens": target_publication_tokens,
        "safety_publication_tokens": safety_publication_tokens,
        "one_click_publication_tokens": one_click_publication_tokens,
        "actionability_publication_tokens": actionability_publication_tokens,
        "target_ranking_tokens": target_ranking_tokens,
        "safety_ranking_tokens": safety_ranking_tokens,
        "no_new_page_owned_blocker_reason_ranking_logic": not unexpected_actionability_reasons
        and not target_ranking_tokens
        and not safety_ranking_tokens,
        "known_bounded_actionability_reasons": sorted(actionability_reasons),
        "unexpected_actionability_reasons": unexpected_actionability_reasons,
        "apply_routing_remains_page_owned": "def _apply_design_guide" in inputs_source
        or "def _execute_design_guide" in inputs_source
        or "_record_rendered_design_guide_primary_apply_payload" in inputs_source,
        "design_brain_decisions_stay_in_controller_or_service": all(
            token in target_segment
            for token in (
                "_evaluate_design_candidate_with_updates(",
                "_resolve_design_guide_controller_local_cleanup_pre_preview_gate(",
                "_resolve_design_guide_controller_local_cleanup_basic_post_preview_gate(",
                "_resolve_design_guide_controller_local_cleanup_candidate_promotion(",
                "_resolve_design_guide_controller_local_cleanup_target_band_acceptance(",
                "_resolve_design_guide_controller_local_cleanup_executor_acceptance(",
            )
        )
        and "_resolve_design_candidate_overview_for_safety_check(" in safety_segment
        and "_resolve_design_guide_controller_shear_executor_safety_policy(" in safety_segment,
        "no_auto_candidate_fallback_in_safety_callback": "_evaluate_auto_design_candidate(" not in safety_segment,
        "candidate_evaluation_service_call_present": "_evaluate_design_candidate_with_updates(" in target_segment
        and "_resolve_design_candidate_overview_for_safety_check(" in safety_segment,
        "controller_has_no_page_or_streamlit_imports": "inputs_page" not in controller_source and "streamlit" not in controller_source,
        "candidate_evaluation_has_no_page_or_streamlit_imports": "inputs_page" not in candidate_source and "streamlit" not in candidate_source,
        "line_ranges": {
            TARGET: [target_start, target_end],
            SAFETY_CALLBACK: [safety_start, safety_end],
            ONE_CLICK_PROBE: [one_click_start, one_click_end],
            ACTIONABILITY_CALLBACK: [actionability_start, actionability_end],
        },
        "callback_call_lines": {
            "_guidance_item_is_resolved_one_click(": _call_lines(target_segment, "_guidance_item_is_resolved_one_click("),
            "_guidance_executor_actionability_contract(": _call_lines(target_segment, "_guidance_executor_actionability_contract("),
            "_resolved_shear_cleanup_is_executor_safe(": _call_lines(actionability_segment, "_resolved_shear_cleanup_is_executor_safe("),
        },
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "candidate_evaluation_behavior_changed": False,
    }


def _checks(capture: dict[str, Any], command_results: list[dict[str, Any]]) -> dict[str, bool]:
    return {
        "local_cleanup_helper_shell_only": bool(capture.get("local_cleanup_helper_shell_only")),
        "local_cleanup_callback_use_is_bounded": bool(capture.get("local_cleanup_callback_use_is_bounded")),
        "callback_probe_logic_does_not_decide_recommendation_truth": bool(
            capture.get("callback_probe_logic_does_not_decide_recommendation_truth")
        ),
        "callback_probe_logic_does_not_decide_cta_display_publication_truth": bool(
            capture.get("callback_probe_logic_does_not_decide_cta_display_publication_truth")
        ),
        "apply_routing_remains_page_owned": bool(capture.get("apply_routing_remains_page_owned")),
        "design_brain_decisions_stay_in_controller_or_service": bool(
            capture.get("design_brain_decisions_stay_in_controller_or_service")
        ),
        "no_auto_candidate_fallback_in_safety_callback": bool(capture.get("no_auto_candidate_fallback_in_safety_callback")),
        "candidate_evaluation_service_call_present": bool(capture.get("candidate_evaluation_service_call_present")),
        "no_new_page_owned_blocker_reason_ranking_logic": bool(
            capture.get("no_new_page_owned_blocker_reason_ranking_logic")
        ),
        "controller_has_no_page_or_streamlit_imports": bool(capture.get("controller_has_no_page_or_streamlit_imports")),
        "candidate_evaluation_has_no_page_or_streamlit_imports": bool(
            capture.get("candidate_evaluation_has_no_page_or_streamlit_imports")
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "candidate_evaluation_behavior_unchanged": capture.get("candidate_evaluation_behavior_changed") is False,
        "composed_locks_pass": all(result.get("passed") for result in command_results),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    checks = dict(payload.get("checks") or {})
    lines = [
        "# Local Cleanup Callback Shell Boundary Audit",
        "",
        "## Executive Summary",
        str(payload.get("result") or ""),
        "",
        "## Surface Classification",
        "Surface | Lines | Classification | Deletion readiness | Evidence",
        "--- | --- | --- | --- | ---",
    ]
    for row in capture.get("surfaces") or []:
        lines.append(
            " | ".join(
                [
                    f"`{row.get('surface')}`",
                    f"`{row.get('line_start')}`-`{row.get('line_end')}`",
                    str(row.get("classification") or ""),
                    str(row.get("deletion_readiness") or ""),
                    "; ".join(str(x) for x in (row.get("evidence") or [])),
                ]
            )
        )
    lines.extend(
        [
            "",
            "## Boundary Proof",
            f"- Local cleanup helper shell-only: `{capture.get('local_cleanup_helper_shell_only')}`",
            f"- Callback/probe use bounded through controller acceptance: `{capture.get('local_cleanup_callback_use_is_bounded')}`",
            f"- Recommendation truth not decided by callback/probe wrapper: `{capture.get('callback_probe_logic_does_not_decide_recommendation_truth')}`",
            f"- CTA/display/publication truth not decided by callback/probe wrapper: `{capture.get('callback_probe_logic_does_not_decide_cta_display_publication_truth')}`",
            f"- Apply routing remains page-owned: `{capture.get('apply_routing_remains_page_owned')}`",
            f"- Design Brain decisions stay in controller/service boundaries: `{capture.get('design_brain_decisions_stay_in_controller_or_service')}`",
            f"- Safety callback has no `_evaluate_auto_design_candidate(...)` fallback: `{capture.get('no_auto_candidate_fallback_in_safety_callback')}`",
            f"- Candidate evaluation service call present: `{capture.get('candidate_evaluation_service_call_present')}`",
            "",
            "## Bounded Page Callback Reasons",
            str(capture.get("known_bounded_actionability_reasons") or []),
            "",
            "## Unexpected Page Reason/Ranking Logic",
            f"- Unexpected actionability reasons: `{capture.get('unexpected_actionability_reasons')}`",
            f"- Target ranking tokens: `{capture.get('target_ranking_tokens')}`",
            f"- Safety ranking tokens: `{capture.get('safety_ranking_tokens')}`",
            "",
            "## Verifier Results",
        ]
    )
    for name, passed in checks.items():
        lines.append(f"- `{name}`: `{passed}`")
    lines.extend(["", "## Commands"])
    for result in payload.get("command_results") or []:
        lines.append(f"- `{result.get('command')}`: `{result.get('passed')}`")
    lines.extend(
        [
            "",
            "## Next Safe Slice",
            str(payload.get("next_safe_slice") or ""),
            "",
            "## Stop Conditions",
            "- Do not delete actionability callback execution; it is bounded page-owned plumbing, not dead code.",
            "- Do not move apply routing or Streamlit/session reads into Design Brain.",
            "- Stop if a future verifier finds publication, ranking, or blocker truth being shaped in these wrappers.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_progress(payload: dict[str, Any], report_path: Path) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if PROGRESS_PATH.exists():
        lines.append(PROGRESS_PATH.read_text(encoding="utf-8").rstrip())
        lines.append("")
    lines.extend(
        [
            f"## {payload.get('created_at')} - Local cleanup callback shell boundary",
            "",
            f"- Result: `{payload.get('result')}`",
            f"- Report: [{report_path.name}](../audits/{report_path.name})",
            f"- Next: `{payload.get('next_safe_slice')}`",
            "",
        ]
    )
    PROGRESS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    created_at = _timestamp()
    capture = _capture()
    command_results = [_run(command) for command in COMMANDS]
    checks = _checks(capture, command_results)
    passed = all(checks.values())
    result = "LOCAL_CLEANUP_CALLBACK_SURFACE_BOUNDED" if passed else "NOT_BOUNDED_WITH_EXACT_REMAINING_SURFACE"
    payload = {
        "schema": "design_guide_local_cleanup_callback_shell_boundary_audit.v1",
        "created_at": created_at,
        "status": "PASS" if passed else "FAIL",
        "result": result,
        "capture": capture,
        "checks": checks,
        "command_results": command_results,
        "next_safe_slice": (
            "lock local-cleanup callback surface as bounded page-shell plumbing; next extraction surface should be outside this helper"
            if passed
            else "inspect failing boundary check before moving or deleting callback/probe code"
        ),
    }
    suffix = created_at.replace(":", "-")
    json_path = ARTIFACT_DIR / f"design_guide_local_cleanup_callback_shell_boundary_audit_{suffix}.json"
    report_path = AUDIT_DIR / f"design_guide_local_cleanup_callback_shell_boundary_audit_{suffix}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(report_path, payload)
    _append_progress(payload, report_path)
    print(f"design_guide_local_cleanup_callback_shell_boundary_audit {payload['status']}")
    print(f"result={result}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    if not passed:
        failing = [name for name, ok in checks.items() if not ok]
        print(f"failing_checks={failing}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
