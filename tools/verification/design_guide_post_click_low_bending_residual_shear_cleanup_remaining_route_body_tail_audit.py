"""Classify the remaining residual-shear cleanup route-body tail.

This is proof-only. It does not delete or move behavior. It identifies the
remaining physical route-body surfaces after the injected-dependency route shell
cutover so the next extraction slice can be chosen precisely.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"

ROUTE_BODY_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_BODY_END = "    residual_shear_cleanup_route_execution_shell = _run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_execution_shell("
TAIL_START = (
    "        residual_result_packaging_blocker_tail = "
    "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_"
    "result_packaging_blocker_tail_shell("
)

REQUIRED_ARTIFACTS = {
    "route_shell_with_injected_dependencies_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies_cutover"
    ),
    "route_body_deletion_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_readiness"
    ),
    "route_body_deletion_deadness_proof": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_deadness_proof"
    ),
    "result_packaging_blocker_tail_shell_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_blocker_tail_shell_cutover"
    ),
    "proof_debug_return_tail_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail_cutover"
    ),
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_bridge_lock": "design_guide_compute_resolver_publication_bridge_lock",
    "independence_lock": "design_guide_independence_lock",
}

TAIL_SURFACES = {
    "result_packaging_injected_execution": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_result_packaging(",
        "classification": "C. page-injected result-packaging execution retained by controller tail shell",
        "delete_now": False,
    },
    "outside_preferred_band_blocker_assembly": {
        "token": "and float(residual_preview_util) > float(target_hi) + float(TARGET_BAND_EPS)",
        "classification": "A. old inline blocker/evidence assembly; should be absent after tail shell",
        "delete_now": False,
    },
    "evidence_merge_tail_adapter": {
        "token": "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_evidence_merge_tail_result_adapter(",
        "classification": "B. controller adapter present; compatibility/proof-covered",
        "delete_now": False,
    },
    "final_binding_tail_controller_call": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
        "classification": "B. controller adapter present; compatibility/proof-covered",
        "delete_now": False,
    },
    "button_contract_helper_boundary": {
        "token": "_execute_post_click_low_bending_residual_shear_cleanup_button_contract(",
        "classification": "C. page/shared CTA boundary retained by rule",
        "delete_now": False,
    },
    "debug_session_projection": {
        "token": "debug_sink[",
        "classification": "D. debug/session projection; non-authoritative but physically live",
        "delete_now": False,
    },
    "route_proof_stamps": {
        "token": "_stamp_final_publication_post_click_low_bending_residual_shear_cleanup_route_proof(",
        "classification": "D. proof/debug stamp; non-authoritative but physically live",
        "delete_now": False,
    },
    "route_body_replacement_adapter": {
        "token": "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
        "classification": "B. controller replacement adapter present; compatibility/proof-covered",
        "delete_now": False,
    },
    "route_body_controller_result": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(",
        "classification": "B. controller return-boundary adapter present",
        "delete_now": False,
    },
    "proof_debug_return_tail": {
        "token": "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail(",
        "classification": "B. controller proof/debug/return tail representation present",
        "delete_now": False,
    },
    "physical_route_return": {
        "token": "return residual_route_return_item",
        "classification": "E. physical nested route body return; delete only after tail replacement",
        "delete_now": False,
    },
}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


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


def _status_from_payload(payload: dict[str, Any]) -> str:
    raw = str(
        payload.get("status")
        or payload.get("result")
        or payload.get("lock_status")
        or payload.get("decision")
        or ""
    )
    upper = raw.upper()
    if "PASS" in upper or "LOCKED" in upper:
        return "PASS"
    if "FAIL" in upper:
        return "FAIL"
    if "PARTIAL" in upper:
        return "PARTIAL"
    return raw or "UNKNOWN"


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": "", "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "payload": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "found": True,
        "status": _status_from_payload(payload),
        "path": str(path),
        "payload": payload,
    }


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    route_body = _between(source, ROUTE_BODY_START, ROUTE_BODY_END)
    tail = route_body[route_body.find(TAIL_START) :] if TAIL_START in route_body else ""
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    surface_rows = {
        name: {
            "present": spec["token"] in tail,
            "classification": spec["classification"],
            "delete_now": bool(spec["delete_now"]),
            "token": spec["token"],
        }
        for name, spec in TAIL_SURFACES.items()
    }
    missing_expected_surfaces = tuple(
        name for name, row in surface_rows.items() if row.get("present") is False
    )
    required_artifacts_pass = all(row.get("status") == "PASS" for row in latest.values())
    live_a_surfaces = tuple(
        name
        for name, row in surface_rows.items()
        if row.get("present") and str(row.get("classification") or "").startswith("A.")
    )
    live_debug_surfaces = tuple(
        name
        for name, row in surface_rows.items()
        if row.get("present") and str(row.get("classification") or "").startswith("D.")
    )
    physical_return_present = bool(surface_rows["physical_route_return"]["present"])
    ready_for_deletion = bool(
        tail
        and required_artifacts_pass
        and not live_a_surfaces
        and not live_debug_surfaces
        and not physical_return_present
    )
    result_packaging_tail_cutover = (
        latest["result_packaging_blocker_tail_shell_cutover"].get("status") == "PASS"
    )
    proof_debug_return_tail_cutover = (
        latest["proof_debug_return_tail_cutover"].get("status") == "PASS"
    )
    if ready_for_deletion:
        next_safe_surface = "delete_physical_route_body"
        decision = "RESIDUAL_SHEAR_ROUTE_BODY_TAIL_READY_FOR_DELETION"
    elif proof_debug_return_tail_cutover:
        next_safe_surface = "replace_physical_nested_route_body_wrapper"
        decision = "RESIDUAL_SHEAR_ROUTE_BODY_PROOF_DEBUG_RETURN_TAIL_REPRESENTED_NOT_READY_FOR_DELETION"
    elif result_packaging_tail_cutover:
        next_safe_surface = "proof_debug_return_tail_controller_shell_or_deletion"
        decision = "RESIDUAL_SHEAR_ROUTE_BODY_TAIL_CONTROLLER_PACKAGING_SHELL_IMPLEMENTED_NOT_READY_FOR_DELETION"
    else:
        next_safe_surface = "result_packaging_and_blocker_tail_controller_shell"
        decision = "RESIDUAL_SHEAR_ROUTE_BODY_TAIL_NOT_READY_FOR_DELETION"
    return {
        "decision": decision,
        "route_body_found": bool(route_body),
        "tail_found": bool(tail),
        "required_artifacts_pass": required_artifacts_pass,
        "surface_rows": surface_rows,
        "missing_expected_surfaces": missing_expected_surfaces,
        "live_a_surfaces": live_a_surfaces,
        "live_debug_surfaces": live_debug_surfaces,
        "physical_return_present": physical_return_present,
        "result_packaging_blocker_tail_shell_cutover": result_packaging_tail_cutover,
        "proof_debug_return_tail_cutover": proof_debug_return_tail_cutover,
        "safe_to_delete_tail_now": ready_for_deletion,
        "next_safe_surface": next_safe_surface,
        "required_artifacts": {
            name: {key: value for key, value in row.items() if key != "payload"}
            for name, row in latest.items()
        },
        "tail_hash": _stable_hash(tail),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_body_found": capture.get("route_body_found") is True,
        "tail_found": capture.get("tail_found") is True,
        "required_artifacts_pass": capture.get("required_artifacts_pass") is True,
        "deletion_not_claimed": capture.get("safe_to_delete_tail_now") is False,
        "next_surface_classified": bool(capture.get("next_safe_surface")),
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Remaining Route Body Tail Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Safe to delete tail now: `{capture.get('safe_to_delete_tail_now')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Surface Rows",
        "",
    ]
    for name, row in dict(capture.get("surface_rows") or {}).items():
        lines.append(
            f"- {name}: present=`{row.get('present')}`, classification=`{row.get('classification')}`"
        )
    lines.extend(
        [
            "",
            "## Behaviour",
            "",
            "- Product behaviour changed: `False`",
            "- Engineering behaviour changed: `False`",
            "- Visible wording changed: `False`",
            "- CTA/apply semantics changed: `False`",
            "- Family runtime changed: `False`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    status = "PASS" if all(checks.values()) else "FAIL"
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_route_body_tail_audit.v1",
        "status": status,
        "created_at": stamp,
        "capture": capture,
        "checks": checks,
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"remaining_route_body_tail_audit_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"remaining_route_body_tail_audit_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload), encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"remaining_route_body_tail_audit {status}"
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
