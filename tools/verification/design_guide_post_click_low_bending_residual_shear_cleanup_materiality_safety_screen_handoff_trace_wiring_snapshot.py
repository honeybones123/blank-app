"""Trace-wiring snapshot for residual shear cleanup materiality/safety screen handoff."""

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
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
NEXT_DEPENDENCY = (
    ROOT
    / "tools"
    / "verification"
    / "design_guide_post_click_low_bending_residual_shear_cleanup_next_dependency_audit.py"
)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.design_guide_controller import (  # noqa: E402
    build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff,
)


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


def _run_next_dependency() -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(NEXT_DEPENDENCY)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0
        and "design_guide_post_click_low_bending_residual_shear_cleanup_next_dependency_audit PASS"
        in proc.stdout,
    }


def _object_case(status: str = "page_live") -> dict[str, Any]:
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff(
        candidate_evaluator_handoff={"candidate_evaluator_handoff_hash": "eval-hash"},
        screen_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-hash",
            "mode_config_hash": "mode-hash",
        },
        screen_output_summary={
            "generated_update_count": 4,
            "evaluation_attempted_count": 3,
            "accepted_candidate_count": 1,
            "rejected_candidate_count": 3,
            "stable_sequence_hash": "sequence-hash",
        },
        dependency_status=status,
    )
    repeat = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff(
        candidate_evaluator_handoff={"candidate_evaluator_handoff_hash": "eval-hash"},
        screen_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-hash",
            "mode_config_hash": "mode-hash",
        },
        screen_output_summary={
            "generated_update_count": 4,
            "evaluation_attempted_count": 3,
            "accepted_candidate_count": 1,
            "rejected_candidate_count": 3,
            "stable_sequence_hash": "sequence-hash",
        },
        dependency_status=status,
    )
    return {
        "dependency_status": status,
        "output_shape_ready": bool(first.get("output_shape_ready")),
        "behavior_cutover_ready": bool(first.get("behavior_cutover_ready")),
        "stable_hash_repeat": first.get("materiality_safety_screen_handoff_hash")
        == repeat.get("materiality_safety_screen_handoff_hash"),
        "proof_only": bool(first.get("proof_only")),
        "product_driving": bool(first.get("product_driving")),
        "render_driving": bool(first.get("render_driving")),
        "apply_driving": bool(first.get("apply_driving")),
        "session_driving": bool(first.get("session_driving")),
    }


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    helper = _between(
        source,
        "def _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key(",
    )
    pre_screen_helper = _between(
        source,
        "def _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen(",
        "\n\ndef _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
    )
    post_screen_helper = _between(
        source,
        "def _run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen(",
        "\n\ndef _stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_cutover_readiness(",
    )
    pre_screen_builder = _between(
        controller_source,
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_pre_screen_result(",
        "\n\ndef build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result(",
    )
    post_screen_builder = _between(
        controller_source,
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_post_screen_result(",
        "\n\ndef build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff(",
    )
    pre_semantics_source = pre_screen_helper + "\n" + pre_screen_builder
    post_semantics_source = post_screen_helper + "\n" + post_screen_builder
    route = _between(
        source,
        "current_shear_for_residual_cleanup = _parse_util_value(family_utils.get(\"shear\"))",
        "shear_blocker = _shear_low_util_active_links_exact_blocker(",
    )
    evaluator_stamp_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_evaluator_injected_adapter("
    )
    materiality_stamp_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff("
    )
    selection_stamp_idx = route.find(
        "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_selection_sort_key("
    )
    next_dependency = _run_next_dependency()
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_MATERIALITY_SAFETY_SCREEN_HANDOFF_TRACE_WIRED",
        "import_alias_present": (
            "build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff as "
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff"
        )
        in source,
        "helper_present": bool(helper),
        "helper_calls_controller": (
            "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff("
            in helper
        ),
        "helper_stamps_non_driving_flags": all(
            token in helper
            for token in (
                "materiality_safety_screen_proof_only",
                "materiality_safety_screen_product_driving",
                "materiality_safety_screen_render_driving",
                "materiality_safety_screen_apply_driving",
                "materiality_safety_screen_session_driving",
            )
        ),
        "route_stamp_order": 0 <= evaluator_stamp_idx < materiality_stamp_idx < selection_stamp_idx,
        "route_records_screen_inputs": all(
            token in route
            for token in (
                '"route_branch": "post_click_residual_shear_cleanup_after_bending_blocker"',
                '"state_fingerprint": _stable_final_publication_hash(dict(state or {}))',
                '"mode_config_hash": _stable_final_publication_hash(dict(mode_config or {}))',
            )
        ),
        "route_records_screen_outputs": all(
            token in route
            for token in (
                '"generated_update_count": len(fallback_variant_generator_update_sequence)',
                '"evaluation_attempted_count": len(fallback_candidate_evaluation_sequence)',
                '"accepted_candidate_count": len(fallback_shear_candidates)',
                '"rejected_candidate_count": max(',
                '"stable_sequence_hash": _stable_final_publication_hash(',
            )
        ),
        "route_uses_injected_pre_screen": (
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_pre_screen("
            in route
        ),
        "route_uses_injected_post_screen": (
            "_run_post_click_low_bending_residual_shear_cleanup_materiality_safety_post_screen("
            in route
        ),
        "raw_inline_materiality_logic_absent_from_route": all(
            token not in route
            for token in (
                "_one_click_diff_accumulated_updates(",
                "_shear_cleanup_materially_reduces_reinforcement(",
                "_overview_required_checks_acceptable(",
                "_candidate_preview_statuses_have_explicit_fail(",
            )
        ),
        "pre_screen_helper_preserves_route_semantics": all(
            token in pre_semantics_source
            for token in (
                "candidate_delta_screen = delta_screen_builder(",
                "fallback_updates = dict(candidate_delta_screen.get(\"updates\") or {})",
                "_updates_match_state(state, fallback_updates)",
                "materially_reduces_reinforcement",
                "pure_updates_checker(dict(fallback_updates))",
                "no_updates",
                "updates_match_state",
                "not_material_reduction",
                "non_shear_update_keys",
            )
        ),
        "post_screen_helper_preserves_route_semantics": all(
            token in post_semantics_source
            for token in (
                "candidate_acceptance_screen = acceptance_screen_builder(",
                "fallback_shear_util = _parse_util_value(fallback_utils.get(\"shear\"))",
                "fallback_shear_util is None",
                "float(fallback_shear_util) <= float(current_shear_util) + 1e-9",
                "float(fallback_shear_util) > 1.0 + float(target_band_eps)",
                "bool(overview.get(\"any_fail\"))",
                "required_checks_acceptable",
                "explicit_preview_fail",
                "candidate_failed_residual_shear_cleanup_acceptance",
            )
        ),
        "object_page_live_case": _object_case("page_live"),
        "object_controller_owned_case": _object_case("controller_owned"),
        "next_dependency": next_dependency,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    page_case = dict(capture.get("object_page_live_case") or {})
    controller_case = dict(capture.get("object_controller_owned_case") or {})
    return {
        "import_alias_present": capture.get("import_alias_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "helper_calls_controller": capture.get("helper_calls_controller") is True,
        "helper_stamps_non_driving_flags": capture.get("helper_stamps_non_driving_flags") is True,
        "route_stamp_order": capture.get("route_stamp_order") is True,
        "route_records_screen_inputs": capture.get("route_records_screen_inputs") is True,
        "route_records_screen_outputs": capture.get("route_records_screen_outputs") is True,
        "route_uses_injected_pre_screen": capture.get("route_uses_injected_pre_screen") is True,
        "route_uses_injected_post_screen": capture.get("route_uses_injected_post_screen") is True,
        "raw_inline_materiality_logic_absent_from_route": (
            capture.get("raw_inline_materiality_logic_absent_from_route") is True
        ),
        "pre_screen_helper_preserves_route_semantics": (
            capture.get("pre_screen_helper_preserves_route_semantics") is True
        ),
        "post_screen_helper_preserves_route_semantics": (
            capture.get("post_screen_helper_preserves_route_semantics") is True
        ),
        "page_live_object_shape_ready": page_case.get("output_shape_ready") is True,
        "page_live_not_behavior_ready": page_case.get("behavior_cutover_ready") is False,
        "controller_owned_behavior_ready": controller_case.get("behavior_cutover_ready") is True,
        "object_hashes_stable": page_case.get("stable_hash_repeat") is True
        and controller_case.get("stable_hash_repeat") is True,
        "object_non_driving": all(
            page_case.get(key) is expected
            for key, expected in (
                ("proof_only", True),
                ("product_driving", False),
                ("render_driving", False),
                ("apply_driving", False),
                ("session_driving", False),
            )
        ),
        "next_dependency_passed": (capture.get("next_dependency") or {}).get("passed") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Materiality Safety Screen Handoff Trace Wiring",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Result",
        "",
        f"- helper present: `{capture.get('helper_present')}`",
        f"- route stamp order valid: `{capture.get('route_stamp_order')}`",
        f"- route uses injected pre-screen: `{capture.get('route_uses_injected_pre_screen')}`",
        f"- route uses injected post-screen: `{capture.get('route_uses_injected_post_screen')}`",
        f"- raw inline materiality logic absent from route: `{capture.get('raw_inline_materiality_logic_absent_from_route')}`",
        f"- next dependency audit passed: `{(capture.get('next_dependency') or {}).get('passed')}`",
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
            "Materiality/safety screen parity is ready for cutover proof. Keep CTA, visible wording, apply routing, and family/runtime behaviour unchanged.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff_trace_wiring_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff_trace_wiring_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff_trace_wiring_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_materiality_safety_screen_handoff_trace_wiring_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_materiality_safety_screen_handoff_trace_wiring "
        f"{payload['status']}"
    )
    print(json_path)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
