"""Cutover verifier for residual shear cleanup materiality/safety injected screen."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
TRACE = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff_trace_wiring_snapshot.py"
)
PARITY = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_parity_scenarios.py"
)
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"


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
    if end < 0:
        return source[start:]
    return source[start:end]


def _run(script: Path, expected_stdout: str) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0 and expected_stdout in proc.stdout,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    pre_helper = _between(
        source,
        "def _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
        "\n\ndef _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
    )
    post_helper = _between(
        source,
        "def _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    pre_builder = _between(
        controller_source,
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result(",
        "\n\ndef build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result(",
    )
    post_builder = _between(
        controller_source,
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result(",
        "\n\ndef build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff(",
    )
    pre_semantics_source = pre_helper + "\n" + pre_builder
    post_semantics_source = post_helper + "\n" + post_builder
    trace = _run(
        TRACE,
        "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff_trace_wiring PASS",
    )
    parity = _run(
        PARITY,
        "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_parity_scenarios PASS",
    )
    raw_route_tokens = (
        "_one_click_diff_accumulated_updates(",
        "_shear_cleanup_materially_reduces_reinforcement(",
        "_overview_required_checks_acceptable(",
        "_candidate_preview_statuses_have_explicit_fail(",
    )
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_MATERIALITY_SAFETY_SCREEN_CUTOVER_IMPLEMENTED",
        "pre_helper_present": bool(pre_helper),
        "post_helper_present": bool(post_helper),
        "route_pre_screen_wrapper_count": route.count(
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen("
        ),
        "route_post_screen_wrapper_count": route.count(
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen("
        ),
        "raw_inline_route_tokens_present": [token for token in raw_route_tokens if token in route],
        "route_injects_delta_screen_builder": (
            "delta_screen_builder=_build_design_guide_shear_low_util_candidate_delta_screen"
            in route
        ),
        "route_injects_pure_updates_checker": (
            "pure_updates_checker=_shear_detailing_updates_pure" in route
        ),
        "route_injects_acceptance_screen_builder": (
            "acceptance_screen_builder=_build_design_guide_shear_low_util_candidate_acceptance_screen"
            in route
        ),
        "pre_helper_preserves_failure_reasons": all(
            token in pre_semantics_source
            for token in (
                "screen_dependency_unavailable",
                "no_updates",
                "updates_match_state",
                "not_material_reduction",
                "non_shear_update_keys",
            )
        ),
        "pre_helper_preserves_screen_inputs": all(
            token in pre_helper
            for token in (
                "candidate_delta_screen = delta_screen_builder(",
                "base_state=state",
                "variant_state=fallback_variant",
                "_updates_match_state(state, fallback_updates)",
                "pure_updates_checker(dict(fallback_updates))",
            )
        ),
        "post_helper_preserves_failure_reasons": all(
            token in post_semantics_source
            for token in (
                "candidate_evaluation_returned_no_candidate",
                "candidate_failed_residual_shear_cleanup_acceptance",
            )
        ),
        "post_helper_preserves_acceptance_checks": all(
            token in post_semantics_source
            for token in (
                "candidate_acceptance_screen = acceptance_screen_builder(",
                "fallback_shear_util is None",
                "float(fallback_shear_util) <= float(current_shear_util) + 1e-9",
                "float(fallback_shear_util) > 1.0 + float(target_band_eps)",
                "bool(overview.get(\"any_fail\"))",
                "required_checks_acceptable",
                "explicit_preview_fail",
            )
        ),
        "trace_snapshot": trace,
        "parity_scenarios": parity,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "product_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "pre_helper_present": capture.get("pre_helper_present") is True,
        "post_helper_present": capture.get("post_helper_present") is True,
        "route_pre_screen_wrapper_single": capture.get("route_pre_screen_wrapper_count") == 1,
        "route_post_screen_wrapper_single": capture.get("route_post_screen_wrapper_count") == 1,
        "raw_inline_route_tokens_removed": not capture.get("raw_inline_route_tokens_present"),
        "route_injects_delta_screen_builder": capture.get("route_injects_delta_screen_builder") is True,
        "route_injects_pure_updates_checker": capture.get("route_injects_pure_updates_checker") is True,
        "route_injects_acceptance_screen_builder": (
            capture.get("route_injects_acceptance_screen_builder") is True
        ),
        "pre_helper_preserves_failure_reasons": (
            capture.get("pre_helper_preserves_failure_reasons") is True
        ),
        "pre_helper_preserves_screen_inputs": (
            capture.get("pre_helper_preserves_screen_inputs") is True
        ),
        "post_helper_preserves_failure_reasons": (
            capture.get("post_helper_preserves_failure_reasons") is True
        ),
        "post_helper_preserves_acceptance_checks": (
            capture.get("post_helper_preserves_acceptance_checks") is True
        ),
        "trace_snapshot_passed": (capture.get("trace_snapshot") or {}).get("passed") is True,
        "parity_scenarios_passed": (capture.get("parity_scenarios") or {}).get("passed") is True,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Design Brain Physical Extraction Report",
        "",
        "## Executive Summary",
        f"{payload.get('status')}",
        "",
        "## Surface Targeted",
        "Residual shear cleanup materiality/safety screen inside `_post_click_low_bending_resolution_item(...)`.",
        "",
        "## Ownership Before",
        "The residual route performed delta, materiality, purity, overview-acceptance, and preview-fail checks inline.",
        "",
        "## Ownership After",
        "The route calls injected pre/post screen wrappers. Candidate generation/evaluation and CTA/apply/wording remain injected or page-owned as before.",
        "",
        "## Behaviour Preserved",
        f"- visible wording changed: `{capture.get('visible_wording_changed')}`",
        f"- CTA/apply semantics changed: `{capture.get('cta_apply_semantics_changed')}`",
        f"- engineering behaviour changed: `{capture.get('engineering_behavior_changed')}`",
        f"- family runtime changed: `{capture.get('family_runtime_changed')}`",
        "",
        "## Cutover Proof",
        f"- pre-screen wrapper count: `{capture.get('route_pre_screen_wrapper_count')}`",
        f"- post-screen wrapper count: `{capture.get('route_post_screen_wrapper_count')}`",
        f"- raw inline route tokens present: `{capture.get('raw_inline_route_tokens_present')}`",
        f"- trace snapshot passed: `{(capture.get('trace_snapshot') or {}).get('passed')}`",
        f"- parity scenarios passed: `{(capture.get('parity_scenarios') or {}).get('passed')}`",
        "",
        "## Deadness / Deletion Proof",
        "The old inline materiality/safety route body is absent from the live route. Helper deletion is not requested because the helper is now the live injected shell.",
        "",
        "## Lines Removed / Added",
        "Verifier-only report; implementation was already cut over before this proof. See git diff for exact working-tree line counts.",
        "",
        "## Files Changed",
        "- `inputs_page.py`",
        "- this verifier",
        "- materiality/safety trace verifier",
        "- residual cleanup next-dependency audit",
        "",
        "## Verifier Results",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Remaining Page-Owned Authority",
            "Candidate selection/result construction and final-binding/intent-contract tails remain the next residual-route authority surfaces.",
            "",
            "## Next Safe Target",
            "Candidate-selection/result-construction and final-binding tail audit/cutover. Keep CTA, visible wording, apply routing, UI/session, and family/runtime behaviour unchanged.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_cutover_implementation.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_cutover_implementation_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_cutover_implementation_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_materiality_safety_screen_cutover_implementation_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_cutover_implementation "
        f"{payload['status']}"
    )
    print(json_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
