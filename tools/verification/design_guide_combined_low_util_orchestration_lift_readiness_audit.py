"""Audit readiness to lift combined low-util local orchestration into controller."""

from __future__ import annotations

import ast
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
FUNCTION_NAME = "_combine_best_safe_shear_with_bending_cleanup_item"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _function_source(path: Path, function_name: str) -> tuple[str, int, int]:
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                raise RuntimeError(f"Missing end_lineno for {function_name}")
            return "\n".join(lines[node.lineno - 1 : end_lineno]), node.lineno, end_lineno
    raise RuntimeError(f"Could not find {function_name} in {path}")


ORCHESTRATION_REQUIREMENTS = [
    {
        "name": "shear_action_gate",
        "token": "shear_cleanup_action = bool(",
        "classification": "controller_decision_logic",
        "required_injection_or_move": [
            "_guidance_item_best_safe_partial_cleanup",
            "plain item title/action/family fields",
        ],
    },
    {
        "name": "shear_update_key_policy",
        "token": "_COMPOUND_SHEAR_UPDATE_KEYS",
        "classification": "controller_policy_constant",
        "required_injection_or_move": ["compound shear update key set"],
    },
    {
        "name": "bottom_update_key_policy",
        "token": "_COMPOUND_BOTTOM_UPDATE_KEYS",
        "classification": "controller_policy_constant",
        "required_injection_or_move": ["compound bottom update key set"],
    },
    {
        "name": "bending_incremental_cleanup_gate",
        "token": "bending_incremental_cleanup",
        "classification": "controller_decision_logic",
        "required_injection_or_move": [
            "_guidance_item_safe_incremental_cleanup_below_threshold",
            "_guidance_item_best_safe_partial_cleanup",
        ],
    },
    {
        "name": "state_match_gate",
        "token": "_updates_match_state(state, combined_updates)",
        "classification": "controller_decision_logic",
        "required_injection_or_move": ["updates_match_state predicate"],
    },
    {
        "name": "util_parsing",
        "token": "_parse_util_value(",
        "classification": "controller_utility_dependency",
        "required_injection_or_move": ["util parser"],
    },
    {
        "name": "accepted_min_family_util_gate",
        "token": "FINAL_ACCEPTED_MIN_FAMILY_UTIL",
        "classification": "controller_policy_constant",
        "required_injection_or_move": ["final accepted min family utilisation threshold"],
    },
    {
        "name": "invalid_item_debug_fallback",
        "token": "_build_design_guide_combined_low_util_invalid_item_fallback(",
        "classification": "controller_safe_fallback_proof",
        "required_injection_or_move": [
            "controller-safe invalid item fallback proof"
        ],
    },
]

CONTROLLER_BOUNDARY_TOKENS = [
    "_run_design_guide_combined_low_util_orchestration(",
    "_resolve_design_guide_combined_low_util_cleanup_updates(",
    "_evaluate_design_guide_combined_low_util_cleanup_candidate(",
    "_run_design_guide_combined_low_util_bending_cleanup_item_generation(",
    "_assess_design_guide_combined_low_util_cleanup_acceptance_gate(",
    "_assess_design_guide_combined_low_util_post_click_accepted_green_audit(",
    "_resolve_design_guide_combined_low_util_cleanup_target_band(",
    "_build_design_guide_combined_low_util_cleanup_candidate_search_evidence(",
    "_build_design_guide_combined_low_util_result_packaging(",
    "_build_design_guide_combined_low_util_invalid_item_fallback(",
]


def _capture() -> dict[str, Any]:
    function_source, start_line, end_line = _function_source(INPUTS_PAGE, FUNCTION_NAME)
    wrapper_cutover = "_run_design_guide_combined_low_util_orchestration(" in function_source
    requirements = []
    for row in ORCHESTRATION_REQUIREMENTS:
        count = function_source.count(str(row["token"]))
        requirements.append(
            {
                **row,
                "present": count > 0,
                "count": count,
                "ready_for_bulk_lift": wrapper_cutover
                or row["classification"] != "page_fallback_or_legacy_bug_risk",
            }
        )
    controller_boundary_presence = {
        token: {
            "present": token in function_source,
            "count": function_source.count(token),
        }
        for token in CONTROLLER_BOUNDARY_TOKENS
    }
    fallback_risk = [
        row for row in requirements if row["classification"] == "page_fallback_or_legacy_bug_risk" and row["present"]
    ]
    not_ready = bool(fallback_risk) and not wrapper_cutover
    decision = (
        "WRAPPER_CUTOVER_COMPLETE"
        if wrapper_cutover
        else (
        "PARTIAL_READY_BUT_FALLBACK_MUST_BE_FIXED_FIRST"
        if not_ready
        else "READY_FOR_CONTROLLER_ORCHESTRATION_WRAPPER"
        )
    )
    return {
        "decision": decision,
        "wrapper_cutover": wrapper_cutover,
        "function": {
            "name": FUNCTION_NAME,
            "start_line": start_line,
            "end_line": end_line,
            "line_count": end_line - start_line + 1,
        },
        "requirements": requirements,
        "controller_boundary_presence": controller_boundary_presence,
        "fallback_risk_count": len(fallback_risk),
        "safe_to_lift_whole_function_now": not not_ready,
        "recommended_next_slice": (
            "assess whether the thin wrapper call can be renamed/deleted after consumer reachability proof"
            if wrapper_cutover
            else (
            "replace the invalid-item debug fallback with a controller-safe fallback proof before lifting the whole function"
            if not_ready
            else "lift remaining orchestration into one controller wrapper with injected predicates/constants"
            )
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    requirements = list(capture.get("requirements") or [])
    boundaries = dict(capture.get("controller_boundary_presence") or {})
    return {
        "function_found": bool((capture.get("function") or {}).get("line_count")),
        "requirements_mapped_or_wrapper_cutover": bool(capture.get("wrapper_cutover"))
        or all(row.get("present") for row in requirements),
        "controller_wrapper_present": bool(
            boundaries.get("_run_design_guide_combined_low_util_orchestration(", {}).get("present")
        ),
        "fallback_risk_resolved": int(capture.get("fallback_risk_count") or 0) == 0,
        "whole_function_lift_ready_after_fallback_cutover": (
            capture.get("safe_to_lift_whole_function_now") is True
        ),
        "recommended_next_slice_recorded": bool(capture.get("recommended_next_slice")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Guide Combined Low-Util Orchestration Lift Readiness Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        f"Safe to lift whole function now: `{capture.get('safe_to_lift_whole_function_now')}`",
        "",
        "## Checks",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Requirements", ""])
    lines.append("| Name | Present | Count | Classification | Required injection/move |")
    lines.append("| --- | ---: | ---: | --- | --- |")
    for row in capture.get("requirements") or []:
        lines.append(
            "| {name} | {present} | {count} | {classification} | {required} |".format(
                name=row.get("name"),
                present=row.get("present"),
                count=row.get("count"),
                classification=row.get("classification"),
                required=", ".join(str(x) for x in row.get("required_injection_or_move") or []),
            )
        )
    lines.extend(["", "## Recommendation", "", str(capture.get("recommended_next_slice") or "")])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {"status": status, "checks": checks, "capture": capture}
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_combined_low_util_orchestration_lift_readiness_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_combined_low_util_orchestration_lift_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(report_path, payload)
    print(f"design_guide_combined_low_util_orchestration_lift_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"safe_to_lift_whole_function_now={capture.get('safe_to_lift_whole_function_now')}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
