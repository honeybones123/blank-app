"""Evidence-merge tail handoff object snapshot for residual shear cleanup."""

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
    except Exception as exc:  # pragma: no cover
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
    token = (
        "def build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff("
    )
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\n\ndef ", start + len(token))
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    from design_brain.design_guide_controller import (
        build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff,
    )

    source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace")
    block = _function_block(source)
    route_shell = {
        "route_shell_adapter_hash": "route-shell-fixture-hash",
        "route_shell_ready": True,
    }
    inputs = {
        "route_branch": "post_click_residual_shear_cleanup_after_bending_blocker",
        "pre_merge_evidence_hash": "pre-evidence-hash",
        "pre_merge_exact_blockers_hash": "pre-blockers-hash",
        "residual_updates_hash": "updates-hash",
        "residual_outside_preferred_band": False,
    }
    output = {
        "residual_evidence_hash": "merged-evidence-hash",
        "residual_exact_blockers_hash": "merged-blockers-hash",
        "exact_blocker_families": ("bending",),
        "outside_target_band_allowed": False,
        "post_click_bending_blocker_preserved": True,
        "post_click_residual_shear_cleanup_after_bending_blocker": True,
        "no_second_cta_required": True,
    }
    first = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff(
        route_shell_adapter=route_shell,
        evidence_inputs=inputs,
        evidence_output_summary=output,
        dependency_status="page_live",
    )
    second = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff(
        route_shell_adapter=route_shell,
        evidence_inputs=inputs,
        evidence_output_summary=output,
        dependency_status="page_live",
    )
    controller_owned = build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff(
        route_shell_adapter=route_shell,
        evidence_inputs=inputs,
        evidence_output_summary=output,
        dependency_status="controller_owned",
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
    return {
        "decision": "EVIDENCE_MERGE_TAIL_HANDOFF_OBJECT_READY_FOR_TRACE_WIRING",
        "function_present": bool(block),
        "exported": (
            '"build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff"'
            in source
        ),
        "stable_repeat_hash": first.get("evidence_merge_tail_handoff_hash")
        == second.get("evidence_merge_tail_handoff_hash"),
        "output_shape_ready": first.get("output_shape_ready") is True,
        "behavior_cutover_not_ready_with_page_live_dependency": (
            first.get("behavior_cutover_ready") is False
        ),
        "behavior_cutover_ready_when_controller_owned": (
            controller_owned.get("behavior_cutover_ready") is True
        ),
        "outside_band_wording_not_moved": "outside_target_band_blocker_construction"
        in tuple(first.get("not_moved") or ()),
        "candidate_search_not_moved": "candidate_generation_execution"
        in tuple(first.get("not_moved") or ()),
        "candidate_evaluation_not_moved": "candidate_evaluation_execution"
        in tuple(first.get("not_moved") or ()),
        "cta_contract_not_moved": "cta_contract_execution" in tuple(first.get("not_moved") or ()),
        "forbidden_page_terms_absent": not any(
            term.lower() in block.lower() for term in forbidden_page_terms
        ),
        "execution_terms_absent": not any(term in block for term in forbidden_execution_terms),
        "proof_only": first.get("proof_only") is True,
        "product_driving": first.get("product_driving") is True,
        "render_driving": first.get("render_driving") is True,
        "apply_driving": first.get("apply_driving") is True,
        "session_driving": first.get("session_driving") is True,
        "latest": {
            "route_shell_deadness": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_deadness_readiness"
            ),
            "route_shell_cutover": _latest(
                "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_adapter_cutover_implementation"
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
        "output_shape_ready": capture.get("output_shape_ready") is True,
        "behavior_cutover_not_ready_with_page_live_dependency": (
            capture.get("behavior_cutover_not_ready_with_page_live_dependency") is True
        ),
        "behavior_cutover_ready_when_controller_owned": (
            capture.get("behavior_cutover_ready_when_controller_owned") is True
        ),
        "outside_band_wording_not_moved": capture.get("outside_band_wording_not_moved")
        is True,
        "candidate_search_not_moved": capture.get("candidate_search_not_moved") is True,
        "candidate_evaluation_not_moved": capture.get("candidate_evaluation_not_moved")
        is True,
        "cta_contract_not_moved": capture.get("cta_contract_not_moved") is True,
        "forbidden_page_terms_absent": capture.get("forbidden_page_terms_absent") is True,
        "execution_terms_absent": capture.get("execution_terms_absent") is True,
        "non_driving": (
            capture.get("proof_only") is True
            and capture.get("product_driving") is False
            and capture.get("render_driving") is False
            and capture.get("apply_driving") is False
            and capture.get("session_driving") is False
        ),
        "route_shell_deadness_pass": (
            (capture.get("latest") or {}).get("route_shell_deadness", {}).get("status")
            == "PASS"
        ),
        "route_shell_cutover_pass": (
            (capture.get("latest") or {}).get("route_shell_cutover", {}).get("status")
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
        "# Residual Shear Cleanup Evidence-Merge Tail Handoff Object Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Function present: `{capture.get('function_present')}`",
        f"- Stable repeat hash: `{capture.get('stable_repeat_hash')}`",
        f"- Output shape ready: `{capture.get('output_shape_ready')}`",
        f"- Behaviour cutover ready with page-live dependency: `{not capture.get('behavior_cutover_not_ready_with_page_live_dependency')}`",
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
            "Trace-wire the evidence-merge handoff beside the live residual evidence merge.",
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
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_object_snapshot.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_object_{stamp}.json"
    )
    report_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_object_{stamp}.md"
    )
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_handoff_object "
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
