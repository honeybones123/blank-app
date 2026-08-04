"""Audit readiness to replace the residual-shear physical nested route wrapper.

The proof/debug/return tail is represented by the controller, but the nested
route function can only be deleted after the outer execution shell no longer
needs any callable reference to
`_execute_post_click_low_bending_residual_shear_cleanup_route_body`.
This verifier classifies that exact wrapper boundary without changing product
behaviour.
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

ROUTE_START = "current_shear_for_residual_cleanup = _parse_util_value("
ROUTE_END = "    shear_blocker = _shear_low_util_active_links_exact_blocker("

REQUIRED_ARTIFACTS = {
    "proof_debug_return_tail_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail_cutover"
    ),
    "remaining_route_body_tail_audit": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_remaining_route_body_tail_audit"
    ),
    "route_body_deletion_readiness": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_readiness"
    ),
    "route_body_deletion_deadness_proof": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_deadness_proof"
    ),
    "prebuilt_route_shell_cutover": (
        "design_guide_post_click_low_bending_residual_shear_cleanup_prebuilt_route_shell_cutover"
    ),
}

WRAPPER_SURFACES = {
    "nested_route_body_definition": {
        "token": "def _execute_post_click_low_bending_residual_shear_cleanup_route_body():",
        "classification": "C. physical nested wrapper still present",
        "delete_blocker": True,
    },
    "route_body_executor_injection": {
        "token": "route_body_executor=_execute_post_click_low_bending_residual_shear_cleanup_route_body",
        "classification": "C. controller execution shell still calls page nested wrapper",
        "delete_blocker": True,
    },
    "route_body_supplier_injection": {
        "token": "route_body_supplier=_execute_post_click_low_bending_residual_shear_cleanup_route_body",
        "classification": "C. physical wrapper still invokes page nested wrapper as supplier",
        "delete_blocker": True,
    },
    "execution_shell_result_unwrap": {
        "token": 'residual_shear_cleanup_route_execution_shell.get("result_item")',
        "classification": "B. outer unwrap can remain as page-shell wiring",
        "delete_blocker": False,
    },
    "outer_result_return": {
        "token": "return residual_shear_cleanup_route_result",
        "classification": "B. outer route result return can remain as page-shell wiring",
        "delete_blocker": False,
    },
    "proof_debug_tail_represented": {
        "token": "_stamp_design_guide_controller_post_click_low_bending_residual_shear_cleanup_proof_debug_return_tail(",
        "classification": "B. proof/debug/return tail represented by controller",
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
    route = _between(source, ROUTE_START, ROUTE_END)
    latest = {name: _latest(prefix) for name, prefix in REQUIRED_ARTIFACTS.items()}
    surface_rows = {
        name: {
            "present": spec["token"] in route,
            "classification": spec["classification"],
            "delete_blocker": bool(spec["delete_blocker"] and spec["token"] in route),
            "token": spec["token"],
        }
        for name, spec in WRAPPER_SURFACES.items()
    }
    required_artifacts_pass = all(row.get("status") == "PASS" for row in latest.values())
    delete_blockers = tuple(
        name for name, row in surface_rows.items() if row.get("delete_blocker") is True
    )
    executor_replaced = not surface_rows["route_body_executor_injection"]["present"]
    supplier_replaced = not surface_rows["route_body_supplier_injection"]["present"]
    wrapper_replaced = executor_replaced and supplier_replaced
    safe_to_delete_nested_wrapper_now = bool(
        route and required_artifacts_pass and wrapper_replaced and not delete_blockers
    )
    if safe_to_delete_nested_wrapper_now:
        decision = "RESIDUAL_SHEAR_PHYSICAL_WRAPPER_READY_FOR_DELETION"
        next_safe_surface = "delete_nested_route_body_wrapper"
    elif executor_replaced and not supplier_replaced:
        decision = "RESIDUAL_SHEAR_PHYSICAL_WRAPPER_SUPPLIER_STILL_LIVE"
        next_safe_surface = "prove_or_replace_route_body_supplier_before_deletion"
    elif wrapper_replaced:
        decision = "RESIDUAL_SHEAR_PHYSICAL_WRAPPER_REFERENCES_REPLACED_NOT_READY_TO_DELETE"
        next_safe_surface = "prove_nested_route_body_wrapper_dead_then_delete"
    else:
        decision = "RESIDUAL_SHEAR_PHYSICAL_WRAPPER_NOT_READY_TO_DELETE"
        next_safe_surface = "replace_route_body_executor_injection_with_controller_prebuilt_route_result"
    return {
        "decision": decision,
        "route_found": bool(route),
        "required_artifacts_pass": required_artifacts_pass,
        "surface_rows": surface_rows,
        "delete_blockers": delete_blockers,
        "safe_to_delete_nested_wrapper_now": safe_to_delete_nested_wrapper_now,
        "next_safe_surface": next_safe_surface,
        "latest_required_artifacts": {
            name: {key: value for key, value in row.items() if key != "payload"}
            for name, row in latest.items()
        },
        "route_hash": _stable_hash(route),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    blockers = tuple(capture.get("delete_blockers") or ())
    executor_injection_present = bool(
        ((capture.get("surface_rows") or {}).get("route_body_executor_injection") or {}).get("present")
    )
    supplier_injection_present = bool(
        ((capture.get("surface_rows") or {}).get("route_body_supplier_injection") or {}).get("present")
    )
    nested_wrapper_present = bool(
        ((capture.get("surface_rows") or {}).get("nested_route_body_definition") or {}).get("present")
    )
    return {
        "route_found": capture.get("route_found") is True,
        "required_artifacts_pass": capture.get("required_artifacts_pass") is True,
        "wrapper_state_classified": bool(capture.get("decision")),
        "deletion_not_claimed_while_live_wrapper_remains": (
            capture.get("safe_to_delete_nested_wrapper_now") is False
            and (
                (executor_injection_present and "route_body_executor_injection" in blockers)
                or (supplier_injection_present and "route_body_supplier_injection" in blockers)
                or (
                    (not executor_injection_present)
                    and (not supplier_injection_present)
                    and nested_wrapper_present
                    and "nested_route_body_definition" in blockers
                )
            )
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
        "# Residual Shear Physical Wrapper Replacement Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Safe to delete nested wrapper now: `{capture.get('safe_to_delete_nested_wrapper_now')}`",
        f"Next safe surface: `{capture.get('next_safe_surface')}`",
        "",
        "## Wrapper Surfaces",
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
        f"physical_wrapper_replacement_readiness_{stamp}.json"
    )
    report_path = AUDIT_DIR / (
        "design_guide_post_click_low_bending_residual_shear_cleanup_"
        f"physical_wrapper_replacement_readiness_{stamp}.md"
    )
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_physical_wrapper_replacement_readiness",
        payload["status"],
    )
    print(f"decision={capture.get('decision')}")
    print(f"next_safe_surface={capture.get('next_safe_surface')}")
    print(json_path)
    print(report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
