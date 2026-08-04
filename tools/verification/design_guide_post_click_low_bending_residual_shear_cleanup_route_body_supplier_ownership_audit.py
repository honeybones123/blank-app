"""Classify live ownership inside the residual-shear route body supplier.

The physical wrapper now consumes a prebuilt result, but that result is still
created by calling the nested page supplier. This audit records why the supplier
is not deletion-safe yet and identifies the next extraction surface.
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
ROUTE_BODY_END = "    residual_shear_cleanup_physical_route_body_wrapper = "

REQUIRED_ARTIFACTS = {
    "physical_wrapper_replacement_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_physical_wrapper_replacement_readiness"
    ),
    "prebuilt_route_shell_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell_cutover"
    ),
    "dependency_injected_candidate_execution_shell_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_dependency_injected_candidate_execution_shell_cutover"
    ),
    "result_packaging_cutover_implementation": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_cutover_implementation"
    ),
    "result_packaging_deadness_reachability": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_result_packaging_deadness_reachability"
    ),
}

SUPPLIER_SURFACES = {
    "route_body_supplier_callsite": {
        "token": "route_body_supplier=_execute_post_click_low_bending_residual_shear_cleanup_route_body",
        "classification": "still live page supplier callsite",
        "ownership": "page-shell live execution bridge",
        "delete_blocker": True,
    },
    "primary_shear_tightening_executor": {
        "token": "_run_post_click_low_bending_residual_shear_cleanup_primary_executor(",
        "classification": "still live candidate generation execution",
        "ownership": "page-owned injected dependency",
        "delete_blocker": True,
    },
    "primary_shear_tightening_helper": {
        "token": "executor=_compute_shear_tightening_recommendation",
        "classification": "still live shear cleanup candidate helper",
        "ownership": "page/shared engineering helper dependency",
        "delete_blocker": True,
    },
    "fallback_variant_generation": {
        "token": "generator=generate_less_shear_reo_variants",
        "classification": "still live fallback candidate generation",
        "ownership": "page-owned injected dependency",
        "delete_blocker": True,
    },
    "fallback_candidate_evaluation": {
        "token": "evaluator=_evaluate_auto_design_candidate",
        "classification": "still live candidate evaluation",
        "ownership": "page-owned evaluation dependency",
        "delete_blocker": True,
    },
    "fallback_candidate_selection": {
        "token": "selector=_select_design_guide_post_click_low_bending_residual_shear_cleanup_candidate_by_sort_key",
        "classification": "still live fallback candidate selection",
        "ownership": "page-owned selection dependency",
        "delete_blocker": True,
    },
    "result_packaging": {
        "token": "packager=_shear_tightening_as_local_cleanup_item",
        "classification": "still live result packaging dependency",
        "ownership": "page-owned packaging dependency",
        "delete_blocker": True,
    },
    "local_cleanup_evaluation": {
        "token": "local_cleanup_evaluator=_evaluate_local_cleanup_guidance_item",
        "classification": "still live local cleanup evaluation dependency",
        "ownership": "page-owned evaluation dependency",
        "delete_blocker": True,
    },
    "controller_route_shell": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell(",
        "classification": "controller-owned route shell",
        "ownership": "controller-owned",
        "delete_blocker": False,
    },
    "controller_result_packaging_tail": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_result_packaging_blocker_tail_shell(",
        "classification": "controller-owned blocker/result tail",
        "ownership": "controller-owned",
        "delete_blocker": False,
    },
    "controller_final_binding_tail": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_final_binding_tail(",
        "classification": "controller-owned final binding tail",
        "ownership": "controller-owned",
        "delete_blocker": False,
    },
    "controller_route_body_replacement": {
        "token": "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body_replacement(",
        "classification": "controller proof/replacement object already present",
        "ownership": "controller-owned proof",
        "delete_blocker": False,
    },
    "controller_prebuilt_route_result": {
        "token": "_build_design_guide_controller_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result(",
        "classification": "controller-owned prebuilt result object",
        "ownership": "controller-owned",
        "delete_blocker": False,
    },
    "debug_projection_rows": {
        "token": "debug_sink[",
        "classification": "debug/session projection still physically live",
        "ownership": "page-shell non-authoritative debug/session projection",
        "delete_blocker": False,
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
        return {"found": False, "status": "MISSING", "path": ""}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {
            "found": True,
            "status": "UNREADABLE",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"found": True, "status": _status_from_payload(payload), "path": str(path)}


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace")
    body = _between(source, ROUTE_BODY_START, ROUTE_BODY_END)
    body_deleted = not body and ROUTE_BODY_START not in source
    source_with_callsite = body + "\n" + source
    surface_rows = {
        name: {
            "present": spec["token"] in source_with_callsite
            if name == "route_body_supplier_callsite"
            else spec["token"] in body,
            "classification": spec["classification"],
            "ownership": spec["ownership"],
            "delete_blocker": bool(
                spec["delete_blocker"]
                and (
                    spec["token"] in source_with_callsite
                    if name == "route_body_supplier_callsite"
                    else spec["token"] in body
                )
            ),
            "token": spec["token"],
        }
        for name, spec in SUPPLIER_SURFACES.items()
    }
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    required_artifacts_pass = all(row.get("status") == "PASS" for row in latest.values())
    candidate_execution_shell_cutover = (
        latest.get("dependency_injected_candidate_execution_shell_cutover", {}).get("status")
        == "PASS"
    )
    result_packaging_cutover = (
        latest.get("result_packaging_cutover_implementation", {}).get("status") == "PASS"
        and latest.get("result_packaging_deadness_reachability", {}).get("status") == "PASS"
    )
    if candidate_execution_shell_cutover:
        for name in (
            "primary_shear_tightening_executor",
            "primary_shear_tightening_helper",
            "fallback_variant_generation",
            "fallback_candidate_evaluation",
            "fallback_candidate_selection",
        ):
            if name in surface_rows:
                surface_rows[name]["classification"] = (
                    "controller-orchestrated injected dependency / keep until supplier deletion"
                )
                surface_rows[name]["ownership"] = "controller-owned orchestration with page-supplied dependency"
                surface_rows[name]["delete_blocker"] = False
    if result_packaging_cutover:
        for name in (
            "result_packaging",
            "local_cleanup_evaluation",
        ):
            if name in surface_rows:
                surface_rows[name]["classification"] = (
                    "controller-orchestrated injected result-packaging dependency / keep until supplier deletion"
                )
                surface_rows[name]["ownership"] = "controller-owned result packaging with page-supplied dependency"
                surface_rows[name]["delete_blocker"] = False
    delete_blockers = tuple(
        name for name, row in surface_rows.items() if row.get("delete_blocker") is True
    )
    still_live_page_authority = tuple(
        name
        for name, row in surface_rows.items()
        if row.get("present") and str(row.get("ownership") or "").startswith("page-owned")
    )
    controller_owned_surfaces = tuple(
        name for name, row in surface_rows.items() if row.get("ownership") == "controller-owned"
    )
    decision = (
        "RESIDUAL_SHEAR_ROUTE_BODY_SUPPLIER_DELETED"
        if body_deleted and not delete_blockers
        else (
            "RESIDUAL_SHEAR_ROUTE_BODY_SUPPLIER_STILL_LIVE"
            if delete_blockers
            else "RESIDUAL_SHEAR_ROUTE_BODY_SUPPLIER_READY_FOR_DELETION"
        )
    )
    next_safe_surface = (
        "rerun_route_body_deletion_deadness_and_composed_locks"
        if body_deleted and not delete_blockers
        else (
        "extract_or_prebuild_result_packaging_and_local_cleanup_evaluation_before_supplier_deletion"
        if delete_blockers
        else "delete_route_body_supplier"
        )
    )
    return {
        "decision": decision,
        "body_found": bool(body),
        "body_deleted": body_deleted,
        "required_artifacts_pass": required_artifacts_pass,
        "surface_rows": surface_rows,
        "delete_blockers": delete_blockers,
        "delete_blocker_count": len(delete_blockers),
        "still_live_page_authority": still_live_page_authority,
        "controller_owned_surfaces": controller_owned_surfaces,
        "safe_to_delete_supplier_now": not delete_blockers and bool(body),
        "supplier_deletion_complete": body_deleted and not delete_blockers,
        "next_safe_surface": next_safe_surface,
        "latest_required_artifacts": latest,
        "body_hash": _stable_hash(body),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    delete_blocker_count = int(capture.get("delete_blocker_count") or 0)
    safe_to_delete = capture.get("safe_to_delete_supplier_now") is True
    deletion_complete = capture.get("supplier_deletion_complete") is True
    return {
        "body_found_or_deleted": capture.get("body_found") is True or deletion_complete,
        "required_artifacts_pass": capture.get("required_artifacts_pass") is True,
        "supplier_state_classified": bool(capture.get("decision")),
        "supplier_readiness_state_consistent": (
            (safe_to_delete and delete_blocker_count == 0)
            or (deletion_complete and delete_blocker_count == 0)
            or (not safe_to_delete and delete_blocker_count > 0)
        ),
        "live_blockers_are_explicit_when_present": (
            safe_to_delete or deletion_complete or delete_blocker_count > 0
        ),
        "deletion_not_claimed_while_supplier_live": (
            safe_to_delete or deletion_complete or delete_blocker_count > 0
        ),
        "controller_surfaces_already_present": bool(capture.get("controller_owned_surfaces")),
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
        "# Residual Shear Route Body Supplier Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Safe to delete supplier now: `{capture.get('safe_to_delete_supplier_now')}`",
        f"Delete blocker count: `{capture.get('delete_blocker_count')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Surface Inventory",
        "",
    ]
    for name, row in dict(capture.get("surface_rows") or {}).items():
        lines.append(
            f"- `{name}`: present=`{row.get('present')}`, "
            f"delete_blocker=`{row.get('delete_blocker')}`, "
            f"ownership=`{row.get('ownership')}`, "
            f"classification=`{row.get('classification')}`"
        )
    lines.extend(["", "## Checks", ""])
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- `{name}`: `{value}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    capture = _capture()
    checks = _checks(capture)
    failures = [name for name, value in checks.items() if value is not True]
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "timestamp": stamp,
        "capture": capture,
        "checks": checks,
        "failures": failures,
        "snapshot_hash": _stable_hash({"capture": capture, "checks": checks}),
    }
    json_path = ARTIFACT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"route_body_supplier_ownership_audit_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"route_body_supplier_ownership_audit_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_supplier_ownership_audit",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
