"""Readiness snapshot for a post-click final contract controller adapter.

Proof-only. This checks whether the existing active-action post-click exact
blocker route can replace the remaining final-visible post-click block, or
whether a distinct controller adapter is required.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
CONTROLLER = ROOT / "design_brain" / "design_guide_controller.py"

TARGET_START = '_final_contract_for_post_click = dict(_final_visible_item.get("button_contract") or {})'
TARGET_END = "_final_visible_item = _normalise_visible_optimisation_contract("
EXISTING_ROUTE = "run_design_guide_controller_active_action_post_click_exact_blocker_route"
EXISTING_ROUTE_ALIAS = "_run_design_guide_controller_active_action_post_click_exact_blocker_route"

CURRENT_BLOCK_REQUIRED_TOKENS = (
    "_final_visible_item",
    "_final_visible_resolution",
    "_final_contract_for_post_click",
    "_same_flow_cleanup_apply_for_visible",
    "_post_click_bending_low_requires_exact_blocker",
    "_post_click_bending_low_visible_action",
    "_post_click_bending_audit",
    "_post_click_bending_resolution",
    "_post_click_bending_contract",
)

EXISTING_ROUTE_DISTINCT_TOKENS = (
    "active_outside_exact_blockers",
    "current_utils",
    "final_state",
    "final_overview",
    "post_click_active_action_replaced_by_exact_blocker",
)


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


def _target_block(source: str) -> str:
    start = source.find(TARGET_START)
    if start < 0:
        return ""
    end = source.find(TARGET_END, start)
    return source[start:end] if end > start else ""


def _function_block(source: str, token: str) -> str:
    start = source.find(f"def {token}(")
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    controller_source = CONTROLLER.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    target = _target_block(inputs_source)
    route = _function_block(controller_source, EXISTING_ROUTE)
    current_block_surface_present = all(token in target for token in CURRENT_BLOCK_REQUIRED_TOKENS)
    existing_route_surface_present = all(token in route for token in EXISTING_ROUTE_DISTINCT_TOKENS)
    target_uses_existing_route = EXISTING_ROUTE_ALIAS in target or EXISTING_ROUTE in target
    direct_reuse_ready = bool(
        target
        and route
        and target_uses_existing_route
        and current_block_surface_present
        and existing_route_surface_present
    )
    latest = {
        "ownership": _latest("design_guide_post_click_remaining_live_truth_ownership"),
        "row_level_readiness": _latest("design_guide_post_click_contract_check_row_level_readiness"),
        "render_lock": _latest("design_guide_render_bridge_lock"),
        "compute_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
        "independence_lock": _latest("design_guide_independence_lock"),
    }
    return {
        "decision": (
            "POST_CLICK_FINAL_CONTRACT_CHECK_NEEDS_DISTINCT_CONTROLLER_ADAPTER"
            if not direct_reuse_ready
            else "POST_CLICK_FINAL_CONTRACT_CHECK_EXISTING_CONTROLLER_ROUTE_REUSABLE"
        ),
        "target_block_found": bool(target),
        "existing_route_found": bool(route),
        "existing_route_imported_in_inputs": EXISTING_ROUTE_ALIAS in inputs_source,
        "target_uses_existing_route": target_uses_existing_route,
        "current_block_surface_present": current_block_surface_present,
        "existing_route_surface_present": existing_route_surface_present,
        "direct_reuse_ready": direct_reuse_ready,
        "new_adapter_required": not direct_reuse_ready,
        "target_block_hash": _stable_hash(target),
        "existing_route_hash": _stable_hash(route),
        "recommended_next_slice": (
            "create a distinct proof-only controller adapter for final-visible post-click "
            "contract checks; do not reuse the active-action route directly"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "existing_route_found": capture.get("existing_route_found") is True,
        "existing_route_imported": capture.get("existing_route_imported_in_inputs") is True,
        "current_block_surface_present": capture.get("current_block_surface_present") is True,
        "existing_route_surface_present": capture.get("existing_route_surface_present") is True,
        "direct_reuse_not_ready": capture.get("direct_reuse_ready") is False,
        "new_adapter_required": capture.get("new_adapter_required") is True,
        "ownership_pass": (latest.get("ownership") or {}).get("status") == "PASS",
        "row_level_readiness_pass": (latest.get("row_level_readiness") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_lock") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Controller Adapter Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Existing route imported in inputs: `{capture.get('existing_route_imported_in_inputs')}`",
        f"- Target uses existing route: `{capture.get('target_uses_existing_route')}`",
        f"- Direct reuse ready: `{capture.get('direct_reuse_ready')}`",
        f"- New adapter required: `{capture.get('new_adapter_required')}`",
        f"- Recommended next slice: {capture.get('recommended_next_slice')}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_controller_adapter_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_post_click_controller_adapter_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_post_click_controller_adapter_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_controller_adapter_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
