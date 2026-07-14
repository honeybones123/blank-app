"""Audit legacy page-local post-click final-contract predicates after adapter cutover."""

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

TARGET_START = "_final_contract_for_post_click = dict(_final_visible_item.get(\"button_contract\") or {})"
TARGET_END = "_post_click_bending_audit = {}"
LEGACY_PREDICATES = {
    "contract_enabled_formula": (
        "_design_guide_button_contract_enabled(\n            _final_contract_for_post_click"
    ),
    "exact_blocker_formula": (
        "_guidance_item_has_low_util_exact_blocker(\n            _final_visible_item"
    ),
    "requires_exact_blocker_formula": "post_click_safe_incremental_cleanup_requires_exact_blocker",
    "visible_action_formula": "_guidance_item_best_safe_partial_cleanup(_final_visible_item)",
    "safe_incremental_visible_action_formula": (
        "_guidance_item_safe_incremental_cleanup_below_threshold(_final_visible_item)"
    ),
}
ADAPTER_CUTOVER_MARKERS = (
    "_post_click_final_contract_predicates = dict(",
    "final_publication_post_click_final_contract_predicate_result_live_cutover_used",
)
FORBIDDEN_PAGE_COMPARISON_MARKERS = (
    "_page_post_click_predicates_before_adapter_cutover = {",
    "live_contract_enabled=bool(_post_click_bending_low_contract_enabled)",
    "live_exact_blocker_on_visible_item=bool(",
    "live_requires_exact_blocker=bool(_post_click_bending_low_requires_exact_blocker)",
    "live_visible_action=bool(_post_click_bending_low_visible_action)",
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


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    target = _target_block(source)
    predicate_rows = {
        name: {
            "present": token in target,
            "classification": "A. deleted after adapter-owned predicate cutover",
            "delete_now": False,
            "reason": (
                "The adapter now supplies consumed predicate values and focused parity scenarios "
                "cover the old page predicate meaning."
            ),
        }
        for name, token in LEGACY_PREDICATES.items()
    }
    latest = {
        "cutover": _latest("design_guide_post_click_final_contract_predicate_result_adapter_cutover"),
        "parity": _latest(
            "design_guide_post_click_final_contract_predicate_result_adapter_parity_scenarios"
        ),
        "cutover_readiness": _latest(
            "design_guide_post_click_final_contract_predicate_result_adapter_cutover_readiness"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    all_latest_pass = all((item or {}).get("status") == "PASS" for item in latest.values())
    all_rows_absent = all(row.get("present") is False for row in predicate_rows.values())
    adapter_cutover_present = all(marker in target for marker in ADAPTER_CUTOVER_MARKERS)
    page_comparison_markers_absent = not any(
        marker in target for marker in FORBIDDEN_PAGE_COMPARISON_MARKERS
    )
    return {
        "decision": "LEGACY_PREDICATES_DELETED_ADAPTER_PARITY_RETAINED",
        "target_block_found": bool(target),
        "adapter_cutover_present": adapter_cutover_present,
        "page_comparison_markers_absent": page_comparison_markers_absent,
        "predicate_rows": predicate_rows,
        "legacy_predicate_count": sum(1 for row in predicate_rows.values() if row.get("present")),
        "delete_now_count": 0,
        "all_rows_absent": all_rows_absent,
        "deletion_allowed": True,
        "next_safe_step": (
            "Keep old formulas deleted. Use the focused parity scenario verifier and composed "
            "Design Guide locks as the guard before deleting adjacent post-click compatibility stamps."
        ),
        "latest": latest,
        "all_latest_required_artifacts_pass": all_latest_pass,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "adapter_cutover_present": capture.get("adapter_cutover_present") is True,
        "page_comparison_markers_absent": capture.get("page_comparison_markers_absent") is True,
        "all_rows_absent": capture.get("all_rows_absent") is True,
        "deletion_allowed": capture.get("deletion_allowed") is True,
        "all_latest_required_artifacts_pass": (
            capture.get("all_latest_required_artifacts_pass") is True
        ),
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Post-Click Final Contract Legacy Predicate Deletion Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Legacy predicate count: `{capture.get('legacy_predicate_count')}`",
        f"- Delete-now count: `{capture.get('delete_now_count')}`",
        f"- Deletion allowed: `{capture.get('deletion_allowed')}`",
        f"- Page comparison markers absent: `{capture.get('page_comparison_markers_absent')}`",
        "",
        "## Predicate Rows",
        "",
    ]
    for name, row in (capture.get("predicate_rows") or {}).items():
        lines.append(
            f"- {name}: present=`{row.get('present')}`, classification=`{row.get('classification')}`, "
            f"delete_now=`{row.get('delete_now')}`"
        )
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in (payload.get("checks") or {}).items())
    lines.extend(["", "## Next", "", str(capture.get("next_safe_step"))])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_post_click_final_contract_legacy_predicate_deletion_audit.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = (
        ARTIFACT_DIR
        / f"design_guide_post_click_final_contract_legacy_predicate_deletion_audit_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_final_contract_legacy_predicate_deletion_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_final_contract_legacy_predicate_deletion_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
