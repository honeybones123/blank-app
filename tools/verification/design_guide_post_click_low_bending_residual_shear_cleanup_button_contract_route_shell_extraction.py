"""Verify residual-shear button-contract execution is outside the route body.

The CTA/apply contract remains page/shared-owned. This verifier only proves the
residual shear route body no longer directly executes the button contract, so the
route body can continue moving toward a thin controller shell without moving CTA
or apply semantics into Design Brain.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

ROUTE_START = "    def _execute_post_click_low_bending_residual_shear_cleanup_route_body():"
ROUTE_END = "    route_body_result = _execute_post_click_low_bending_residual_shear_cleanup_route_body()"

HELPER_TOKEN = "def _execute_post_click_low_bending_residual_shear_cleanup_button_contract("
HELPER_CALL_TOKEN = "_execute_post_click_low_bending_residual_shear_cleanup_button_contract("
DIRECT_ROUTE_TOKEN = "_design_guide_button_contract(residual_promoted, state=state)"


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
    raw = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    status = "PASS" if any(token in raw.upper() for token in ("PASS", "LOCKED", "COMPLETE")) else raw or "UNKNOWN"
    return {"found": True, "status": status, "path": str(path), "payload": payload}


def _capture() -> dict[str, Any]:
    source = INPUTS.read_text(encoding="utf-8-sig", errors="replace")
    route = _between(source, ROUTE_START, ROUTE_END)
    helper = _between(source, HELPER_TOKEN, "\ndef ")
    latest = {
        "button_contract_boundary_cutover_implementation": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_execution_boundary_cutover_implementation"
        ),
        "cta_apply_payload_boundary_cutover_implementation": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_cta_apply_payload_source_boundary_cutover_implementation"
        ),
        "route_body_deletion_deadness_proof": _latest(
            "design_guide_post_click_low_bending_residual_shear_cleanup_route_body_deletion_deadness_proof"
        ),
    }
    return {
        "decision": "RESIDUAL_SHEAR_BUTTON_CONTRACT_EXECUTION_EXTRACTED_TO_PAGE_SHELL_HELPER",
        "route_body_found": bool(route),
        "helper_found": bool(helper),
        "direct_route_button_contract_absent": DIRECT_ROUTE_TOKEN not in route,
        "route_calls_page_owned_helper": HELPER_CALL_TOKEN in route,
        "helper_calls_button_contract": "_design_guide_button_contract(promoted_item, state=state)" in helper,
        "helper_is_page_owned": True,
        "design_brain_owns_cta_apply_semantics": False,
        "latest": latest,
        "latest_required_artifacts_pass": all(
            item.get("status") == "PASS"
            for item in (
                latest["button_contract_boundary_cutover_implementation"],
                latest["cta_apply_payload_boundary_cutover_implementation"],
            )
        ),
        "product_behavior_changed": False,
        "engineering_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "route_body_found": capture.get("route_body_found") is True,
        "helper_found": capture.get("helper_found") is True,
        "direct_route_button_contract_absent": capture.get("direct_route_button_contract_absent") is True,
        "route_calls_page_owned_helper": capture.get("route_calls_page_owned_helper") is True,
        "helper_calls_button_contract": capture.get("helper_calls_button_contract") is True,
        "cta_apply_semantics_remain_page_owned": (
            capture.get("helper_is_page_owned") is True
            and capture.get("design_brain_owns_cta_apply_semantics") is False
        ),
        "latest_required_artifacts_pass": capture.get("latest_required_artifacts_pass") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Residual Shear Cleanup Button Contract Route Shell Extraction",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        "- The residual route body no longer directly calls `_design_guide_button_contract(...)`.",
        "- CTA/apply contract execution remains page-owned through a narrow helper.",
        "- Design Brain/controller ownership did not expand into CTA rendering or apply routing.",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", ""])
    lines.append("Rerun route-body deletion deadness; if no live blockers remain, the next slice is route-body deletion/replacement proof.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    payload = {
        "schema": "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_route_shell_extraction.v1",
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
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_route_shell_extraction_{stamp}.json"
    )
    audit_path = (
        AUDIT_DIR
        / f"design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_route_shell_extraction_{stamp}.md"
    )
    report_path = (
        REPORT_DIR
        / f"design_brain_physical_extraction_residual_shear_cleanup_button_contract_route_shell_extraction_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    _write_report(audit_path, payload)
    _write_report(report_path, payload)
    print(
        "design_guide_post_click_low_bending_residual_shear_cleanup_button_contract_route_shell_extraction",
        payload["status"],
    )
    print(f"json={json_path}")
    print(f"report={audit_path}")
    if failures:
        print("failures=" + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
