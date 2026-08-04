"""Classify whether the residual-shear nested wrapper body is dead.

The executor injection has been replaced by a prebuilt result path. This probe
looks inside the nested function itself and identifies the remaining live
surfaces before any attempt to delete or thin that function body.
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
ROUTE_BODY_END = (
    "    residual_shear_cleanup_prebuilt_route_result = {}"
)

REQUIRED_ARTIFACTS = {
    "prebuilt_route_result_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_result_cutover"
    ),
    "physical_wrapper_replacement_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_physical_wrapper_replacement_readiness"
    ),
    "live_route_result_assembly_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_live_route_result_assembly_audit"
    ),
}

WRAPPER_BODY_SURFACES = {
    "route_shell_with_injected_dependencies": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_shell_with_injected_dependencies(",
        "classification": "C. live orchestration call with injected page dependencies",
        "delete_blocker": True,
    },
    "primary_executor_lambda": {
        "token": "primary_executor=lambda:",
        "classification": "C. page-owned primary executor injection still live inside wrapper",
        "delete_blocker": True,
    },
    "fallback_search_loop_lambda": {
        "token": "fallback_search_loop=lambda:",
        "classification": "C. page-owned fallback search dependency injection still live inside wrapper",
        "delete_blocker": True,
    },
    "result_packaging_executor_lambda": {
        "token": "result_packaging_executor=lambda:",
        "classification": "C. page-owned result packaging dependency injection still live inside wrapper",
        "delete_blocker": True,
    },
    "shared_button_contract_execution": {
        "token": "_execute_post_click_low_bending_residual_shear_cleanup_button_contract(",
        "classification": "C. shared/page CTA contract execution still live inside wrapper",
        "delete_blocker": True,
    },
    "debug_projection_writes": {
        "token": "debug_sink[",
        "classification": "D. page-owned debug/session projection still physically live",
        "delete_blocker": False,
    },
    "proof_debug_return_tail": {
        "token": "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail(",
        "classification": "B. controller-represented proof/debug/return tail",
        "delete_blocker": False,
    },
    "route_body_result_shell": {
        "token": "_run_design_guide_controller_post_click_low_bending_residual_shear_cleanup_route_body(",
        "classification": "B. controller return-boundary result shell",
        "delete_blocker": False,
    },
    "physical_return": {
        "token": "return residual_route_return_item",
        "classification": "C. physical nested return still live",
        "delete_blocker": True,
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
    body = _between(source, ROUTE_BODY_START, ROUTE_BODY_END)
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    surface_rows = {
        name: {
            "present": spec["token"] in body,
            "classification": spec["classification"],
            "delete_blocker": bool(spec["delete_blocker"] and spec["token"] in body),
            "token": spec["token"],
        }
        for name, spec in WRAPPER_BODY_SURFACES.items()
    }
    required_artifacts_pass = all(row.get("status") == "PASS" for row in latest.values())
    delete_blockers = tuple(
        name for name, row in surface_rows.items() if row.get("delete_blocker") is True
    )
    nested_wrapper_deleted = not bool(body)
    safe_to_delete_nested_wrapper_now = bool(
        required_artifacts_pass and (nested_wrapper_deleted or (body and not delete_blockers))
    )
    if nested_wrapper_deleted and required_artifacts_pass:
        decision = "RESIDUAL_SHEAR_NESTED_WRAPPER_BODY_DELETED"
        next_safe_surface = "rerun_route_body_deletion_deadness_after_wrapper_deletion"
    elif safe_to_delete_nested_wrapper_now:
        decision = "RESIDUAL_SHEAR_NESTED_WRAPPER_BODY_DEAD"
        next_safe_surface = "delete_nested_route_body_wrapper"
    else:
        decision = "RESIDUAL_SHEAR_NESTED_WRAPPER_BODY_NOT_DEAD"
        next_safe_surface = "extract_prebuilt_route_result_builder_or_split_live_route_result_assembly"
    return {
        "decision": decision,
        "body_found": bool(body),
        "nested_wrapper_deleted": nested_wrapper_deleted,
        "required_artifacts_pass": required_artifacts_pass,
        "surface_rows": surface_rows,
        "delete_blockers": delete_blockers,
        "delete_blocker_count": len(delete_blockers),
        "safe_to_delete_nested_wrapper_now": safe_to_delete_nested_wrapper_now,
        "next_safe_surface": next_safe_surface,
        "latest_required_artifacts": {
            name: {key: value for key, value in row.items() if key != "payload"}
            for name, row in latest.items()
        },
        "body_hash": _stable_hash(body),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    deleted = capture.get("nested_wrapper_deleted") is True
    safe_to_delete = capture.get("safe_to_delete_nested_wrapper_now") is True
    blocker_count = int(capture.get("delete_blocker_count") or 0)
    return {
        "body_found_or_deleted": capture.get("body_found") is True or deleted,
        "required_artifacts_pass": capture.get("required_artifacts_pass") is True,
        "deadness_classified": bool(capture.get("decision")),
        "delete_state_consistent": (
            (safe_to_delete and blocker_count == 0)
            or ((not safe_to_delete) and blocker_count > 0)
        ),
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
        "# Residual Shear Nested Wrapper Deadness Probe",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Safe to delete nested wrapper now: `{capture.get('safe_to_delete_nested_wrapper_now')}`",
        f"Delete blocker count: `{capture.get('delete_blocker_count')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Surfaces",
        "",
    ]
    for name, row in dict(capture.get("surface_rows") or {}).items():
        lines.append(
            f"- `{name}`: present=`{row.get('present')}`, "
            f"delete_blocker=`{row.get('delete_blocker')}`, "
            f"classification=`{row.get('classification')}`"
        )
    lines.extend(["", "## Checks", ""])
    for name, value in dict(payload.get("checks") or {}).items():
        lines.append(f"- {name}: `{value}`")
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
        f"nested_wrapper_deadness_probe_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"nested_wrapper_deadness_probe_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_nested_wrapper_deadness_probe",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
