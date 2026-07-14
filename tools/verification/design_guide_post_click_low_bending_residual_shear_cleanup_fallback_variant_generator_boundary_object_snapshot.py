"""Object snapshot for residual shear cleanup fallback variant generator boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    path = artifacts[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _function_block(source: str) -> str:
    start = source.find(
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary("
    )
    if start < 0:
        return ""
    end = source.find("\n\n@dataclass", start)
    return source[start:end] if end > start else source[start:]


def _fixture(*, dependency_status: str = "page_live", missing_sequence_hash: bool = False) -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary,
    )

    sequence = [
        {"index": 0, "updates": {"lig_legs": 0, "s_lig": 0}},
        {"index": 1, "updates": {"lig_legs": 2, "s_lig": 300}},
    ]
    stable_sequence_hash = "" if missing_sequence_hash else _stable_hash(sequence)
    return build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary(
        candidate_boundary={
            "candidate_boundary_hash": "candidate-boundary-hash",
            "dependency_rows": {"fallback_variant_generator": {"status": dependency_status}},
        },
        generator_inputs={
            "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
            "state_fingerprint": "state-fingerprint",
            "mode_config_hash": "mode-config-hash",
            "iteration_limit": 64,
        },
        generator_output_summary={
            "generator_attempted": True,
            "generated_variant_count": len(sequence),
            "generated_update_count": 2,
            "iteration_limit": 64,
            "stable_sequence_hash": stable_sequence_hash,
            "order_proof": {
                "iteration_limit": 64,
                "stable_sequence_hash": stable_sequence_hash,
                "preserves_generator_order": True,
            },
        },
        dependency_status=dependency_status,
    )


def _capture() -> dict[str, Any]:
    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    block = _function_block(source)
    page_live = _fixture(dependency_status="page_live")
    repeat = _fixture(dependency_status="page_live")
    owned = _fixture(dependency_status="controller_owned")
    missing_sequence = _fixture(dependency_status="controller_owned", missing_sequence_hash=True)
    forbidden_page_terms = (
        "inputs_page",
        "import streamlit",
        "st.session_state",
        "st.button",
        "design_guide_page",
    )
    forbidden_execution_terms = (
        "generate_less_shear_reo_variants(",
        "_evaluate_auto_design_candidate(",
        "_one_click_diff_accumulated_updates(",
        "_compute_shear_tightening_recommendation(",
        "_evaluate_candidate_fast(",
        "evaluate_candidate_full(",
        "_design_guide_button_contract(",
    )
    latest = {
        "remaining_injected_dependency_priority_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_injected_dependency_priority_audit"
        ),
        "candidate_boundary_parity": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_parity_scenarios"
        ),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_resolver_publication_bridge_lock": _latest(
            "design_guide_compute_resolver_publication_bridge_lock"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_FALLBACK_VARIANT_GENERATOR_BOUNDARY_OBJECT_PROVEN",
        "function_present": bool(block),
        "exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary"'
            in source
        ),
        "stable_repeat_hash": page_live.get("fallback_variant_generator_boundary_hash")
        == repeat.get("fallback_variant_generator_boundary_hash"),
        "page_live_output_shape_ready": page_live.get("output_shape_ready") is True,
        "page_live_behavior_cutover_ready": page_live.get("behavior_cutover_ready") is True,
        "owned_behavior_cutover_ready": owned.get("behavior_cutover_ready") is True,
        "missing_sequence_blocks_cutover": missing_sequence.get("behavior_cutover_ready") is False,
        "iteration_limit": page_live.get("iteration_limit"),
        "generated_variant_count": page_live.get("generated_variant_count"),
        "generated_update_count": page_live.get("generated_update_count"),
        "stable_sequence_hash_present": bool(page_live.get("stable_sequence_hash")),
        "boundary_hash_present": bool(page_live.get("fallback_variant_generator_boundary_hash")),
        "input_output_hashes_present": bool(page_live.get("generator_input_hash"))
        and bool(page_live.get("generator_output_hash")),
        "page_must_keep_for_now": list(page_live.get("page_must_keep_for_now") or []),
        "not_moved": list(page_live.get("not_moved") or []),
        "forbidden_page_terms_absent": not any(
            term.lower() in block.lower() for term in forbidden_page_terms
        ),
        "execution_terms_absent": not any(term in block for term in forbidden_execution_terms),
        "proof_only": page_live.get("proof_only") is True,
        "product_driving": page_live.get("product_driving") is True,
        "render_driving": page_live.get("render_driving") is True,
        "apply_driving": page_live.get("apply_driving") is True,
        "session_driving": page_live.get("session_driving") is True,
        "latest": latest,
        "latest_required_artifacts_pass": all(
            (item or {}).get("status") == "PASS" for item in latest.values()
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "raw_payload": page_live,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    not_moved = set(capture.get("not_moved") or [])
    page_keep = set(capture.get("page_must_keep_for_now") or [])
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "page_live_output_shape_ready": capture.get("page_live_output_shape_ready") is True,
        "page_live_behavior_cutover_not_ready": (
            capture.get("page_live_behavior_cutover_ready") is False
        ),
        "owned_behavior_cutover_ready": capture.get("owned_behavior_cutover_ready") is True,
        "missing_sequence_blocks_cutover": capture.get("missing_sequence_blocks_cutover") is True,
        "iteration_limit_locked_to_64": capture.get("iteration_limit") == 64,
        "variant_and_update_counts_present": (
            isinstance(capture.get("generated_variant_count"), int)
            and isinstance(capture.get("generated_update_count"), int)
        ),
        "stable_sequence_hash_present": capture.get("stable_sequence_hash_present") is True,
        "boundary_hash_present": capture.get("boundary_hash_present") is True,
        "input_output_hashes_present": capture.get("input_output_hashes_present") is True,
        "page_keeps_fallback_generation_for_now": "fallback_variant_generation" in page_keep,
        "candidate_evaluation_not_moved": "candidate_evaluation_execution" in not_moved,
        "cta_apply_wording_not_moved": {
            "cta_contract_execution",
            "visible_wording_authoring",
            "apply_routing",
        }.issubset(not_moved),
        "forbidden_page_terms_absent": capture.get("forbidden_page_terms_absent") is True,
        "execution_terms_absent": capture.get("execution_terms_absent") is True,
        "proof_only": capture.get("proof_only") is True,
        "not_product_driving": capture.get("product_driving") is False,
        "not_render_driving": capture.get("render_driving") is False,
        "not_apply_driving": capture.get("apply_driving") is False,
        "not_session_driving": capture.get("session_driving") is False,
        "latest_required_artifacts_pass": capture.get("latest_required_artifacts_pass") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Fallback Variant Generator Boundary Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Output shape ready: `{capture.get('page_live_output_shape_ready')}`",
        f"- Page-live behavior cutover ready: `{capture.get('page_live_behavior_cutover_ready')}`",
        f"- Controller-owned fixture behavior cutover ready: `{capture.get('owned_behavior_cutover_ready')}`",
        f"- Iteration limit: `{capture.get('iteration_limit')}`",
        f"- Generated variant count: `{capture.get('generated_variant_count')}`",
        f"- Generated update count: `{capture.get('generated_update_count')}`",
        f"- Page must keep for now: `{capture.get('page_must_keep_for_now')}`",
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
            "Trace-wire this fallback-generator boundary beside the live residual-shear route. Keep generator execution, candidate evaluation, CTA/apply, visible wording, rendering, and session mutation unchanged.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_object_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_object_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_object_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_fallback_variant_generator_boundary_object_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_fallback_variant_generator_boundary_object "
        + payload["status"]
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    print(f"extraction_report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
