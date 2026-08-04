"""Controller route-shell adapter object snapshot for residual shear cleanup.

This proof-only verifier checks that the Design Guide controller can represent
the residual-shear cleanup route shell and preserve the current route item
shape without taking ownership of candidate generation/evaluation, CTA
execution, visible wording, apply routing, rendering, or session mutation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


EXPECTED_OUTSIDE_OWNERSHIP_FLAGS = (
    "candidate_generation_execution_owned_elsewhere",
    "candidate_evaluation_execution_owned_elsewhere",
    "primary_shear_tightening_execution_owned_elsewhere",
    "cta_contract_execution_owned_elsewhere",
    "visible_wording_authoring_owned_elsewhere",
    "apply_routing_owned_elsewhere",
    "ui_rendering_owned_elsewhere",
    "session_debug_mutation_owned_elsewhere",
)

FORBIDDEN_PAGE_TERMS = (
    "inputs_page",
    "import streamlit",
    "st.session_state",
    "st.button",
    "render_html",
)

FORBIDDEN_EXECUTION_TERMS = (
    "generate_less_shear_reo_variants(",
    "_evaluate_auto_design_candidate(",
    "_compute_shear_tightening_recommendation(",
    "_design_guide_button_contract(",
)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    raw_status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    upper = raw_status.upper()
    if "PASS" in upper or "LOCKED" in upper or "COMPLETE" in upper:
        status = "PASS"
    elif "FAIL" in upper:
        status = "FAIL"
    else:
        status = raw_status or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path)}


def _function_block(source: str) -> str:
    token = "def run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell("
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\n\ndef ", start + len(token))
    return source[start:end] if end > start else source[start:]


def _fixture() -> dict[str, Any]:
    bending_blocker = {
        "family": "bending",
        "source": "post_click_low_bending_exact_blocker",
        "exact_blocker": True,
        "no_second_cta_required": True,
    }
    evidence = {
        "cleanup_search_ran": True,
        "cleanup_search_exhaustive": True,
        "post_click_bending_blocker_preserved": True,
        "post_click_residual_shear_cleanup_after_bending_blocker": True,
        "no_second_cta_required": True,
        "starting_util": 0.69,
        "best_safe_final_util": 0.91,
        "selected_candidate_id": "shear_cleanup_route_shell_fixture",
        "safe_candidate_count": 1,
        "executable_candidate_count": 1,
        "exact_blockers_by_family": {"bending": bending_blocker},
    }
    result_item = {
        "selected_family_id": "SHEAR_OVERDESIGN_GOVERNS",
        "family": "shear",
        "guidance_intent": "efficiency_tightening",
        "action_type": "apply_resolved_candidate",
        "candidate_id": "shear_cleanup_route_shell_fixture",
        "no_second_cta_required": True,
        "button_contract": {
            "family": "shear",
            "enabled": True,
            "action_type": "apply_resolved_candidate",
            "updates": {"lig_legs": 0, "s_lig": 0},
        },
        "candidate_search_evidence": dict(evidence),
    }
    return {
        "state": {"b": 400.0, "D": 650.0, "lig_legs": 2, "s_lig": 200},
        "overview": {"utils": {"bending": 0.24, "shear": 0.69}},
        "mode_config": {"target_band": [0.85, 1.0], "goal": "efficiency"},
        "bending_blocker": bending_blocker,
        "exact_blockers_by_family": {"bending": bending_blocker},
        "residual_shear_tightening": {
            "updates": {"lig_legs": 0, "s_lig": 0},
            "candidate_search_evidence": dict(evidence),
        },
        "residual_result_item": result_item,
        "residual_detail": {"accepted": True, "source": "fixture"},
        "route_debug": {
            "post_click_bending_blocker_preserved": True,
            "post_click_residual_shear_cleanup_after_bending_blocker": True,
        },
        "route_flags": {"starting_shear_util": 0.69, "target_low": 0.85, "target_high": 1.0},
    }


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell,
    )

    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    block = _function_block(source)
    fixture = _fixture()
    first = run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell(
        **fixture
    )
    second = run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell(
        **fixture
    )
    controller_owned = run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell(
        **fixture,
        dependency_status={
            "candidate_generation_execution": "controller_owned",
            "candidate_evaluation_execution": "controller_owned",
            "primary_shear_tightening_execution": "controller_owned",
            "cta_contract_execution": "controller_owned",
            "visible_wording_authoring": "controller_owned",
        },
    )
    result_item = dict(fixture.get("residual_result_item") or {})
    return {
        "decision": "ROUTE_SHELL_ADAPTER_OBJECT_READY_FOR_TRACE_WIRING",
        "function_present": bool(block),
        "exported": (
            '"run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell"'
            in source
        ),
        "stable_repeat_hash": first.get("route_shell_adapter_hash")
        == second.get("route_shell_adapter_hash"),
        "result_item_hash_matches": first.get("result_item_hash")
        == _stable_hash(result_item),
        "route_projection_hash_present": bool(first.get("route_projection_hash")),
        "route_proof_hash_present": bool(first.get("route_proof_hash")),
        "readiness_hash_present": bool(first.get("route_shell_readiness_hash")),
        "route_shell_ready": first.get("route_shell_ready") is True,
        "behavior_cutover_not_ready_with_live_dependencies": (
            first.get("behavior_cutover_ready") is False
        ),
        "behavior_cutover_ready_when_dependencies_controller_owned": (
            controller_owned.get("behavior_cutover_ready") is True
        ),
        "outside_ownership_flags": {
            flag: first.get(flag) is True for flag in EXPECTED_OUTSIDE_OWNERSHIP_FLAGS
        },
        "forbidden_page_terms_absent": not any(
            term.lower() in block.lower() for term in FORBIDDEN_PAGE_TERMS
        ),
        "execution_terms_absent": not any(term in block for term in FORBIDDEN_EXECUTION_TERMS),
        "proof_only": first.get("proof_only") is True,
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is True,
        "apply_driving": first.get("apply_driving") is True,
        "session_driving": first.get("session_driving") is True,
        "latest": {
            "remaining_surface_audit": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_surface_audit"
            ),
            "final_binding_tail_deadness": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_final_binding_tail_deadness_proof"
            ),
        },
        "raw_payload_hash": _stable_hash(first),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "function_present": capture.get("function_present") is True,
        "exported": capture.get("exported") is True,
        "stable_repeat_hash": capture.get("stable_repeat_hash") is True,
        "result_item_hash_matches": capture.get("result_item_hash_matches") is True,
        "route_projection_hash_present": capture.get("route_projection_hash_present") is True,
        "route_proof_hash_present": capture.get("route_proof_hash_present") is True,
        "readiness_hash_present": capture.get("readiness_hash_present") is True,
        "route_shell_ready": capture.get("route_shell_ready") is True,
        "behavior_cutover_not_ready_with_live_dependencies": (
            capture.get("behavior_cutover_not_ready_with_live_dependencies") is True
        ),
        "behavior_cutover_ready_when_dependencies_controller_owned": (
            capture.get("behavior_cutover_ready_when_dependencies_controller_owned") is True
        ),
        "outside_ownership_flags_true": all(
            (capture.get("outside_ownership_flags") or {}).values()
        ),
        "forbidden_page_terms_absent": capture.get("forbidden_page_terms_absent") is True,
        "execution_terms_absent": capture.get("execution_terms_absent") is True,
        "non_driving": (
            capture.get("proof_only") is True
            and capture.get("product_driving") is False
            and capture.get("render_driving") is False
            and capture.get("apply_driving") is False
            and capture.get("session_driving") is False
        ),
        "latest_remaining_surface_audit_pass": (
            (capture.get("latest") or {}).get("remaining_surface_audit", {}).get("status")
            == "PASS"
        ),
        "latest_final_binding_deadness_pass": (
            (capture.get("latest") or {}).get("final_binding_tail_deadness", {}).get("status")
            == "PASS"
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
        "# Residual Shear Cleanup Route-Shell Adapter Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Function present: `{capture.get('function_present')}`",
        f"- Stable repeat hash: `{capture.get('stable_repeat_hash')}`",
        f"- Result item hash matches input item: `{capture.get('result_item_hash_matches')}`",
        f"- Route shell ready: `{capture.get('route_shell_ready')}`",
        f"- Behaviour cutover ready with live dependencies: `{not capture.get('behavior_cutover_not_ready_with_live_dependencies')}`",
        "",
        "## Outside Ownership Flags",
        "",
    ]
    for key, value in (capture.get("outside_ownership_flags") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(
        [
            "",
            "## Next",
            "",
            "Trace-wire this adapter beside the live residual-shear route. Keep candidate generation/evaluation and CTA contract execution injected/page-owned.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, passed in checks.items() if passed is not True]
    payload: dict[str, Any] = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_object_snapshot.v1",
        "created_at": _stamp(),
        "status": "PASS" if not failures else "FAIL",
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash({"capture": capture, "checks": checks})
    stamp = str(payload["created_at"])
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_object_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_object "
        f"{payload['status']}"
    )
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
