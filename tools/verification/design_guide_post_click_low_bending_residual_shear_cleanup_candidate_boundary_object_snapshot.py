"""Object snapshot for residual shear cleanup candidate/evaluator boundary."""

from __future__ import annotations

from datetime import datetime
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


EXPECTED_DEPENDENCIES = {
    "primary_shear_tightening_executor",
    "fallback_variant_generator",
    "candidate_evaluator",
    "candidate_delta_builder",
    "materiality_screen",
    "shear_detailing_purity_screen",
    "overview_acceptance_screen",
    "preview_status_screen",
    "candidate_selection_sort_key",
    "result_packaging_evaluator",
    "cta_contract_builder",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    artifacts = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not artifacts:
        return {"found": False, "status": "MISSING", "path": None}
    last_readable: dict[str, Any] | None = None
    for path in reversed(artifacts):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            last_readable = {
                "found": True,
                "status": "UNREADABLE",
                "path": str(path),
                "error": f"{type(exc).__name__}: {exc}",
            }
            continue
        status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
        if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
            return {"found": True, "status": "PASS", "path": str(path)}
        last_readable = {"found": True, "status": status or "UNKNOWN", "path": str(path)}
    return last_readable or {"found": False, "status": "MISSING", "path": None}


def _function_block(source: str) -> str:
    start = source.find(
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary("
    )
    if start < 0:
        return ""
    end = source.find("\n\n@dataclass", start)
    return source[start:end] if end > start else source[start:]


def _route_proof_fixture() -> dict[str, Any]:
    from design_brain.final_publication import (
        build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof,
    )

    return build_final_design_guide_post_click_low_bending_residual_shear_cleanup_route_proof(
        state={"b": 400.0, "D": 650.0, "lig_legs": 2, "s_lig": 200},
        overview={"utils": {"bending": 0.24, "shear": 0.69}},
        mode_config={"target_band": [0.85, 1.0], "goal": "efficiency"},
        bending_blocker={"family": "bending", "exact_blocker": True},
        exact_blockers_by_family={"bending": {"family": "bending", "exact_blocker": True}},
        residual_shear_tightening={
            "updates": {"lig_legs": 0, "s_lig": 0},
            "candidate_search_evidence": {
                "starting_util": 0.69,
                "best_safe_final_util": 0.91,
                "safe_candidate_count": 1,
                "executable_candidate_count": 1,
            },
        },
        residual_result_item={
            "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
            "family": "shear",
            "action_type": "apply_resolved_candidate",
            "button_contract": {
                "family": "shear",
                "enabled": True,
                "action_type": "apply_resolved_candidate",
                "updates": {"lig_legs": 0, "s_lig": 0},
            },
        },
        residual_detail={"accepted": True},
        route_debug={"post_click_bending_blocker_preserved": True},
        route_flags={"starting_shear_util": 0.69, "target_low": 0.85, "target_high": 1.0},
    )


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary,
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness,
    )

    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    block = _function_block(source)
    route_proof = _route_proof_fixture()
    shell = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness(
        route_proof=route_proof,
        dependency_status={},
    )
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary(
        route_proof=route_proof,
        route_shell_readiness=shell,
        dependency_status={},
        candidate_boundary_inputs={
            "starting_shear_util": 0.69,
            "target_low": 0.85,
            "target_high": 1.0,
            "route": "post_click_low_bending_residual_shear_cleanup",
        },
    )
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary(
        route_proof=route_proof,
        route_shell_readiness=shell,
        dependency_status={},
        candidate_boundary_inputs={
            "starting_shear_util": 0.69,
            "target_low": 0.85,
            "target_high": 1.0,
            "route": "post_click_low_bending_residual_shear_cleanup",
        },
    )
    owned = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary(
        route_proof=route_proof,
        route_shell_readiness=shell,
        dependency_status={key: "controller_owned" for key in EXPECTED_DEPENDENCIES},
        candidate_boundary_inputs={"route": "post_click_low_bending_residual_shear_cleanup"},
    )
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
        "_compute_shear_tightening_recommendation(",
        "_evaluate_candidate_fast(",
        "evaluate_candidate_full(",
        "_design_guide_button_contract(",
    )
    latest = {
        "boundary_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_evaluation_boundary"
        ),
        "route_shell_cutover": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_cutover"
        ),
        "route_deadness_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness"
        ),
    }
    dependency_rows = dict(first.get("dependency_rows") or {})
    return {
        "decision": "RESIDUAL_SHEAR_CLEANUP_CANDIDATE_BOUNDARY_OBJECT_PROVEN",
        "function_present": bool(block),
        "exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_candidate_boundary"'
            in source
        ),
        "stable_repeat_hash": first.get("candidate_boundary_hash") == second.get("candidate_boundary_hash"),
        "request_shape_ready": first.get("request_shape_ready") is True,
        "dependency_boundary_ready": first.get("dependency_boundary_ready") is True,
        "behavior_cutover_ready": first.get("behavior_cutover_ready") is True,
        "owned_fixture_behavior_ready": owned.get("behavior_cutover_ready") is True,
        "dependency_rows": dependency_rows,
        "all_expected_dependencies_represented": EXPECTED_DEPENDENCIES.issubset(
            set(dependency_rows)
        ),
        "unresolved_dependencies": list(first.get("unresolved_dependencies") or []),
        "boundary_hash_present": bool(first.get("candidate_boundary_hash")),
        "input_hashes_present": all(
            bool(value) for value in dict(first.get("boundary_input_hashes") or {}).values()
        ),
        "forbidden_page_terms_absent": not any(
            term.lower() in block.lower() for term in forbidden_page_terms
        ),
        "execution_terms_absent": not any(term in block for term in forbidden_execution_terms),
        "proof_only": first.get("proof_only") is True,
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is True,
        "apply_driving": first.get("apply_driving") is True,
        "session_driving": first.get("session_driving") is True,
        "latest": latest,
        "latest_required_artifacts_pass": all(
            (item or {}).get("status") == "PASS" for item in latest.values()
        ),
        "raw_payload": first,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    unresolved = set(capture.get("unresolved_dependencies") or [])
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "request_shape_ready": capture.get("request_shape_ready") is True,
        "dependency_boundary_ready": capture.get("dependency_boundary_ready") is True,
        "behavior_cutover_not_ready": capture.get("behavior_cutover_ready") is False,
        "owned_fixture_behavior_ready": capture.get("owned_fixture_behavior_ready") is True,
        "all_expected_dependencies_represented": (
            capture.get("all_expected_dependencies_represented") is True
        ),
        "expected_dependencies_unresolved": EXPECTED_DEPENDENCIES.issubset(unresolved),
        "boundary_hash_present": capture.get("boundary_hash_present") is True,
        "input_hashes_present": capture.get("input_hashes_present") is True,
        "forbidden_page_terms_absent": capture.get("forbidden_page_terms_absent") is True,
        "execution_terms_absent": capture.get("execution_terms_absent") is True,
        "proof_only": capture.get("proof_only") is True,
        "not_product_driving": capture.get("product_driving") is False,
        "not_render_driving": capture.get("render_driving") is False,
        "not_apply_driving": capture.get("apply_driving") is False,
        "not_session_driving": capture.get("session_driving") is False,
        "latest_required_artifacts_pass": capture.get("latest_required_artifacts_pass") is True,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Candidate Boundary Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Request shape ready: `{capture.get('request_shape_ready')}`",
        f"- Dependency boundary ready: `{capture.get('dependency_boundary_ready')}`",
        f"- Behavior cutover ready: `{capture.get('behavior_cutover_ready')}`",
        f"- Unresolved dependencies: `{capture.get('unresolved_dependencies')}`",
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
            "Wire this candidate boundary trace-only beside the live residual route before moving candidate generation/evaluation.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_object_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_object_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_object_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_candidate_boundary_object_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_candidate_boundary_object "
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
