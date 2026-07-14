"""Controller route cutover readiness object snapshot for residual shear cleanup."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXPECTED_ROUTE_SHELL_SURFACES = {
    "route_entry_guard",
    "primary_shear_tightening_search",
    "fallback_variant_search",
    "materiality_and_safety_screen",
    "promoted_item_packaging",
    "blocker_evidence_merge",
    "target_band_reason_text",
    "cta_contract_bridge",
    "debug_session_projection",
}

EXPECTED_UNRESOLVED_DEPENDENCIES = {
    "candidate_generation_execution",
    "candidate_evaluation_execution",
    "primary_shear_tightening_execution",
    "cta_contract_execution",
    "visible_wording_authoring",
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
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness("
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
        bending_blocker={
            "family": "bending",
            "exact_blocker": True,
            "no_second_cta_required": True,
        },
        exact_blockers_by_family={
            "bending": {
                "family": "bending",
                "exact_blocker": True,
                "no_second_cta_required": True,
            }
        },
        residual_shear_tightening={
            "updates": {"lig_legs": 0, "s_lig": 0},
            "candidate_search_evidence": {
                "starting_util": 0.69,
                "best_safe_final_util": 0.91,
                "selected_candidate_id": "shear_cleanup_fixture",
                "safe_candidate_count": 1,
                "executable_candidate_count": 1,
            },
        },
        residual_result_item={
            "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
            "family": "shear",
            "guidance_intent": "efficiency_tightening",
            "action_type": "apply_resolved_candidate",
            "candidate_id": "shear_cleanup_fixture",
            "no_second_cta_required": True,
            "button_contract": {
                "family": "shear",
                "enabled": True,
                "action_type": "apply_resolved_candidate",
                "updates": {"lig_legs": 0, "s_lig": 0},
            },
            "candidate_search_evidence": {
                "post_click_bending_blocker_preserved": True,
                "post_click_residual_shear_cleanup_after_bending_blocker": True,
                "no_second_cta_required": True,
                "starting_util": 0.69,
                "best_safe_final_util": 0.91,
                "selected_candidate_id": "shear_cleanup_fixture",
                "exact_blockers_by_family": {
                    "bending": {
                        "family": "bending",
                        "exact_blocker": True,
                        "no_second_cta_required": True,
                    }
                },
            },
        },
        residual_detail={"source": "fixture"},
        route_debug={
            "post_click_bending_blocker_preserved": True,
            "post_click_residual_shear_cleanup_after_bending_blocker": True,
        },
        route_flags={"starting_shear_util": 0.69},
    )


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness,
    )

    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    block = _function_block(source)
    route_proof = _route_proof_fixture()
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness(
        route_proof=route_proof,
        dependency_status={},
    )
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness(
        route_proof=route_proof,
        dependency_status={},
    )
    with_controller_owned_dependencies = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness(
        route_proof=route_proof,
        dependency_status={key: "controller_owned" for key in EXPECTED_UNRESOLVED_DEPENDENCIES},
    )
    forbidden_page_terms = (
        "inputs_page",
        "import streamlit",
        "st.session_state",
        "st.button",
        "render_html",
    )
    forbidden_execution_terms = (
        "generate_less_shear_reo_variants(",
        "_evaluate_auto_design_candidate(",
        "_compute_shear_tightening_recommendation(",
        "_design_guide_button_contract(",
    )
    latest = {
        "route_audit": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_audit"
        ),
        "route_object": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_object"
        ),
        "route_trace": _latest(
            "design_guide_live_post_click_low_bending_residual_shear_cleanup_route_trace"
        ),
        "route_parity": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_parity_scenarios"
        ),
        "route_cutover_readiness": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness"
        ),
        "debug_projection_narrowing": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_debug_projection_narrowing"
        ),
    }
    return {
        "decision": (
            "CONTROLLER_ROUTE_SHELL_READY_BEHAVIOR_CUTOVER_NOT_READY"
        ),
        "function_present": bool(block),
        "exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_cutover_readiness"'
            in source
        ),
        "stable_repeat_hash": first.get("readiness_hash") == second.get("readiness_hash"),
        "route_shell_ready": first.get("route_shell_ready") is True,
        "behavior_cutover_ready": first.get("behavior_cutover_ready") is True,
        "controller_owned_fixture_behavior_ready": (
            with_controller_owned_dependencies.get("behavior_cutover_ready") is True
        ),
        "safe_next_cutover_surface": first.get("safe_next_cutover_surface"),
        "represented_route_surfaces": list(first.get("represented_route_surfaces") or []),
        "missing_route_shell_surfaces": list(first.get("missing_route_shell_surfaces") or []),
        "missing_projection_sections": list(first.get("missing_projection_sections") or []),
        "unresolved_behavior_dependencies": list(
            first.get("unresolved_behavior_dependencies") or []
        ),
        "live_dependency_evidence": first.get("live_dependency_evidence") or {},
        "route_projection_hash_matches": first.get("route_projection_hash")
        == route_proof.get("route_projection_hash"),
        "route_proof_hash_matches": first.get("route_proof_hash") == route_proof.get("proof_hash"),
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
    represented = set(capture.get("represented_route_surfaces") or [])
    unresolved = set(capture.get("unresolved_behavior_dependencies") or [])
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "route_shell_ready": capture.get("route_shell_ready") is True,
        "behavior_cutover_not_ready": capture.get("behavior_cutover_ready") is False,
        "controller_owned_fixture_behavior_ready": (
            capture.get("controller_owned_fixture_behavior_ready") is True
        ),
        "route_shell_surface": capture.get("safe_next_cutover_surface") == "route_shell_only",
        "all_route_surfaces_represented": EXPECTED_ROUTE_SHELL_SURFACES.issubset(represented),
        "no_missing_route_shell_surfaces": not capture.get("missing_route_shell_surfaces"),
        "no_missing_projection_sections": not capture.get("missing_projection_sections"),
        "expected_behavior_dependencies_unresolved": EXPECTED_UNRESOLVED_DEPENDENCIES.issubset(
            unresolved
        ),
        "route_projection_hash_matches": capture.get("route_projection_hash_matches") is True,
        "route_proof_hash_matches": capture.get("route_proof_hash_matches") is True,
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
        "# Residual Shear Cleanup Controller Route Cutover Readiness Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Route shell ready: `{capture.get('route_shell_ready')}`",
        f"- Behavior cutover ready: `{capture.get('behavior_cutover_ready')}`",
        f"- Safe next cutover surface: `{capture.get('safe_next_cutover_surface')}`",
        f"- Unresolved behavior dependencies: `{capture.get('unresolved_behavior_dependencies')}`",
        "",
        "## Boundary",
        "",
        "- Candidate generation, candidate evaluation, primary shear tightening, CTA execution, and visible wording remain live dependencies.",
        "- The controller object is proof-only and non-driving.",
        "- The next possible cutover is route shell only, not behavior.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Latest Artifacts", ""])
    for key, item in (capture.get("latest") or {}).items():
        lines.append(f"- {key}: `{(item or {}).get('status')}` {(item or {}).get('path')}")
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Cut over only the residual shear cleanup route shell to the controller readiness object, then prove live parity before any behavior move or deletion.",
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
        "schema": (
            "design_guide_post_click_low_bending_residual_shear_cleanup_controller_route_cutover_readiness_object_snapshot.v1"
        ),
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_controller_route_cutover_readiness_object_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_controller_route_cutover_readiness_object_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_route_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_controller_route_cutover_readiness_object "
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
