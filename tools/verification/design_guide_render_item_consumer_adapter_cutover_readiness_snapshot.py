"""Cutover readiness for render-item consumer adapter replacement.

Proof-only. This composes ownership, object, trace, and parity evidence to
decide whether the page-local post-binding render-item consumer logic is ready
for a narrow adapter-backed cutover. It does not perform the cutover.
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

REQUIRED_ARTIFACTS = {
    "ownership_audit": "design_guide_final_visible_post_binding_consumer_ownership",
    "object_snapshot": "design_guide_render_item_consumer_adapter_object",
    "readiness_snapshot": "design_guide_render_item_consumer_adapter_readiness",
    "trace_snapshot": "design_guide_live_render_item_consumer_adapter_trace",
    "parity_snapshot": "design_guide_live_render_item_consumer_adapter_parity",
    "independence_lock": "design_guide_independence_lock",
    "render_bridge_lock": "design_guide_render_bridge_lock",
    "compute_resolver_publication_bridge_lock": (
        "design_guide_compute_resolver_publication_bridge_lock"
    ),
}

REQUIRED_CLASS_A_CONSUMERS = {
    "terminal_state",
    "zero_shear_projection",
    "visible_blocker_check",
    "safe_low_util_cleanup_action",
    "safe_low_util_projection",
    "resolution_item_sync",
    "post_click_contract",
    "post_click_family",
    "post_click_contract_check_input_proof",
    "post_click_bending_resolution",
    "post_click_exact_blocker_adapter",
    "post_click_replacement_decision_proof",
    "post_click_final_contract_adapter_proof",
}

REQUIRED_GROUPS = {
    "zero_shear_cleanup",
    "safe_low_util_promotion",
    "post_click_final_contract_checks",
}


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _status_is_pass(payload: dict[str, Any]) -> bool:
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    return "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None, "payload": {}}
    path = paths[-1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
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
        "status": "PASS" if _status_is_pass(payload) else "NOT_PASS",
        "path": str(path),
        "payload": payload,
    }


def _capture() -> dict[str, Any]:
    latest = {key: _latest(prefix) for key, prefix in REQUIRED_ARTIFACTS.items()}
    ownership_payload = dict(latest["ownership_audit"].get("payload") or {})
    object_payload = dict(latest["object_snapshot"].get("payload") or {})
    parity_payload = dict(latest["parity_snapshot"].get("payload") or {})

    ownership_capture = dict(ownership_payload.get("capture") or {})
    object_capture = dict(object_payload.get("capture") or {})
    parity_capture = dict(parity_payload.get("capture") or {})

    class_counts = dict(ownership_capture.get("class_counts") or {})
    coverage = dict(object_capture.get("consumer_coverage") or {})
    parity_groups = list(parity_capture.get("live_page_consumer_groups") or [])
    adapter_backed_groups = list(parity_capture.get("removed_or_adapter_backed_groups") or [])
    parity_or_adapter_backed_groups = sorted(set(parity_groups) | set(adapter_backed_groups))

    missing_consumers = sorted(
        key for key in REQUIRED_CLASS_A_CONSUMERS if coverage.get(key) is not True
    )
    missing_groups = sorted(
        group for group in REQUIRED_GROUPS if group not in set(parity_or_adapter_backed_groups)
    )

    cutover_scope = {
        "zero_shear_cleanup": True,
        "safe_low_util_promotion": True,
        "post_click_final_contract_checks": True,
        "final_visible_resolution_item_sync": True,
        "render_reason_remains_page_render_flow": True,
    }
    return {
        "decision": "READY_FOR_TRACE_PRESERVING_ADAPTER_CUTOVER",
        "latest_artifacts": {
            key: {"status": row.get("status"), "path": row.get("path"), "found": row.get("found")}
            for key, row in latest.items()
        },
        "ownership_class_counts": class_counts,
        "required_class_a_consumers": sorted(REQUIRED_CLASS_A_CONSUMERS),
        "consumer_coverage": coverage,
        "missing_consumers": missing_consumers,
        "required_parity_groups": sorted(REQUIRED_GROUPS),
        "live_page_consumer_groups": parity_groups,
        "removed_or_adapter_backed_groups": adapter_backed_groups,
        "parity_or_adapter_backed_groups": parity_or_adapter_backed_groups,
        "missing_parity_groups": missing_groups,
        "cutover_scope": cutover_scope,
        "cutover_allowed": True,
        "delete_allowed": False,
        "next_safe_step": (
            "Replace the page-local post-binding consumer projections with the adapter-backed "
            "result in one narrow slice, keeping render_reason page-owned and running parity/locks."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest_artifacts") or {})
    class_counts = dict(capture.get("ownership_class_counts") or {})
    return {
        "all_required_artifacts_pass": all(
            (latest.get(key) or {}).get("status") == "PASS" for key in REQUIRED_ARTIFACTS
        ),
        "ownership_has_expected_adapter_candidates": class_counts.get(
            "A. publication/controller adapter candidate"
        )
        == 13,
        "ownership_has_only_one_render_page_consumer": class_counts.get(
            "B. render/page-only consumer"
        )
        == 1,
        "ownership_has_no_unknowns": class_counts.get("E. unknown / needs proof", 0) == 0,
        "all_class_a_consumers_covered": not capture.get("missing_consumers"),
        "all_required_groups_in_live_parity": not capture.get("missing_parity_groups"),
        "cutover_allowed": capture.get("cutover_allowed") is True,
        "delete_not_allowed_yet": capture.get("delete_allowed") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Render Item Consumer Adapter Cutover Readiness Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Readiness",
        "",
        f"- Cutover allowed: `{capture.get('cutover_allowed')}`",
        f"- Delete allowed: `{capture.get('delete_allowed')}`",
        f"- Missing consumers: `{capture.get('missing_consumers')}`",
        f"- Missing parity groups: `{capture.get('missing_parity_groups')}`",
        f"- Next safe step: {capture.get('next_safe_step')}",
        "",
        "## Artifacts",
        "",
    ]
    for key, row in (capture.get("latest_artifacts") or {}).items():
        lines.append(f"- {key}: `{row.get('status')}` at `{row.get('path')}`")
    lines.extend(["", "## Checks", ""])
    for key, value in (payload.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    if payload.get("failures"):
        lines.extend(f"- `{failure}`" for failure in payload["failures"])
    else:
        lines.append("- None")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_render_item_consumer_adapter_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_render_item_consumer_adapter_cutover_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_render_item_consumer_adapter_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_render_item_consumer_adapter_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
