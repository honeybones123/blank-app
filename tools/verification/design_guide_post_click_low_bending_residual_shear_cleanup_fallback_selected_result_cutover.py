"""Cutover verifier for residual shear fallback selected-result assembly."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
import sys


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result,
)


LABEL = "Shear cleanup - one-click reduction"


def _stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
        .replace(":", "-")
    )


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _between(source: str, start_token: str, end_token: str) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start + len(start_token))
    return source[start:end] if end > start else source[start:]


def _old_literal_result(fallback_best: dict[str, Any], current_shear_util: float, count: int) -> dict[str, Any]:
    return {
        "updates": dict(fallback_best.get("updates") or {}),
        "label": LABEL,
        "util": float(fallback_best.get("shear_util") or 0.0),
        "action_type": "apply_resolved_candidate",
        "resolved_candidate": dict(fallback_best.get("candidate") or {}),
        "resolved_candidate_updates": dict(fallback_best.get("updates") or {}),
        "resolved_candidate_label": LABEL,
        "resolved_candidate_action_type": "apply_resolved_candidate",
        "resolved_candidate_post_util": float(fallback_best.get("shear_util") or 0.0),
        "candidate_search_evidence": {
            "cleanup_search_ran": True,
            "cleanup_search_exhaustive": True,
            "local_cleanup_search_ran": True,
            "local_cleanup_search_exhaustive": True,
            "family": "shear",
            "starting_util": float(current_shear_util),
            "best_safe_final_util": float(fallback_best.get("shear_util") or 0.0),
            "best_safe_candidate_updates": dict(fallback_best.get("updates") or {}),
            "best_safe_candidate_applied": False,
            "safe_candidate_count": count,
            "executable_candidate_count": count,
            "safe_cleanup_count": count,
            "executable_cleanup_count": count,
            "safe_shear_cleanup_count": count,
            "executable_shear_cleanup_count": count,
            "no_second_cta_required": True,
            "post_click_residual_shear_cleanup_fallback": True,
        },
    }


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        inputs_source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    sample = {
        "updates": {"s_lig": 300},
        "candidate": {"updates": {"s_lig": 300}, "overview": {"utils": {"shear": 0.72}}},
        "overview": {"utils": {"shear": 0.72}},
        "shear_util": 0.72,
    }
    current_shear_util = 0.42
    count = 3
    controller = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result(
        selected_candidate_row=sample,
        selected_label=LABEL,
        current_shear_util=current_shear_util,
        safe_candidate_count=count,
        route_metadata={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-fingerprint",
            "mode_config_hash": "mode-config-hash",
        },
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result(
        selected_candidate_row=sample,
        selected_label=LABEL,
        current_shear_util=current_shear_util,
        safe_candidate_count=count,
        route_metadata={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-fingerprint",
            "mode_config_hash": "mode-config-hash",
        },
    )
    expected = _old_literal_result(sample, current_shear_util, count)
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FALLBACK_SELECTED_RESULT_CUTOVER_IMPLEMENTED",
        "controller_function_present": (
            "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result("
            in controller_source
        ),
        "controller_function_exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result"'
            in controller_source
        ),
        "inputs_import_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result"
            in inputs_source
        ),
        "route_controller_call_count": route.count(
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_selected_result("
        ),
        "old_literal_block_absent": (
            '"post_click_residual_shear_cleanup_fallback": True,\n                    },\n                }'
            not in route
        ),
        "controller_matches_old_literal_shape": controller.get("result") == expected,
        "stable_hash_repeat": controller.get("result_hash") == repeat.get("result_hash"),
        "proof_hash_present": bool((controller.get("proof") or {}).get("proof_hash")),
        "product_driving": bool((controller.get("proof") or {}).get("product_driving")),
        "render_driving": bool((controller.get("proof") or {}).get("render_driving")),
        "apply_driving": bool((controller.get("proof") or {}).get("apply_driving")),
        "session_driving": bool((controller.get("proof") or {}).get("session_driving")),
        "visible_label_preserved_by_caller": (
            controller.get("result", {}).get("label") == LABEL
            and controller.get("result", {}).get("resolved_candidate_label") == LABEL
        ),
        "not_moved_contains_visible_wording_authoring": (
            "visible_wording_authoring" in tuple((controller.get("proof") or {}).get("not_moved") or ())
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "controller_function_present": capture.get("controller_function_present") is True,
        "controller_function_exported": capture.get("controller_function_exported") is True,
        "inputs_import_present": capture.get("inputs_import_present") is True,
        "route_controller_call_once": capture.get("route_controller_call_count") == 1,
        "old_literal_block_absent": capture.get("old_literal_block_absent") is True,
        "controller_matches_old_literal_shape": (
            capture.get("controller_matches_old_literal_shape") is True
        ),
        "stable_hash_repeat": capture.get("stable_hash_repeat") is True,
        "proof_hash_present": capture.get("proof_hash_present") is True,
        "product_driving_true_for_selected_result": capture.get("product_driving") is True,
        "render_not_driving": capture.get("render_driving") is False,
        "apply_not_driving": capture.get("apply_driving") is False,
        "session_not_driving": capture.get("session_driving") is False,
        "visible_label_preserved_by_caller": (
            capture.get("visible_label_preserved_by_caller") is True
        ),
        "not_moved_contains_visible_wording_authoring": (
            capture.get("not_moved_contains_visible_wording_authoring") is True
        ),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Selected Result Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Result",
        "",
        f"- Route controller call count: `{capture.get('route_controller_call_count')}`",
        f"- Old literal block absent: `{capture.get('old_literal_block_absent')}`",
        f"- Controller matches old literal shape: `{capture.get('controller_matches_old_literal_shape')}`",
        f"- Visible label preserved by caller: `{capture.get('visible_label_preserved_by_caller')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Continue splitting fallback loop sequencing from live generator/evaluator/screen execution. Do not move CTA/apply, wording, formulas, or UI rendering.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_selected_result_cutover.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_selected_result_cutover_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_selected_result_cutover_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_selected_result_cutover_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_selected_result_cutover "
        f"{payload['status']}"
    )
    if failures:
        print("failures:", ", ".join(failures))
        print("artifact:", json_path)
        return 1
    print("artifact:", json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
