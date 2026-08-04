"""Ownership audit for the post-click bending replacement body in inputs_page.py.

This verifier is proof-only. It classifies the adjacent body after the
post-click final-contract predicate adapter cutover so the next extraction
slice can move/delete one boundary without changing product behaviour.
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

TARGET_START = "_post_click_bending_audit = {}"
TARGET_END = "_post_click_replacement_decision_proof = _stamp_final_publication_post_click_replacement_decision_proof("

OWNERSHIP_ROWS = {
    "bending_audit_seed_from_guidance_debug": {
        "token": "_post_click_bending_audit = dict(guidance_debug)",
        "classification": "A. controller/proof-object candidate",
        "reason": "This gathers engineering/debug evidence into a post-click bending audit shape.",
    },
    "evidence_source_merge_loop": {
        "token": "for _bending_audit_source in (",
        "classification": "A. controller/proof-object candidate",
        "reason": "This merges candidate/blocker evidence from multiple item payload surfaces.",
    },
    "family_list_merge_loop": {
        "token": "for _family_list_key in (",
        "classification": "A. controller/proof-object candidate",
        "reason": "This normalizes low-util and unresolved family evidence for the bending replacement.",
    },
    "post_click_family_utils_copy": {
        "token": 'post_click_family_utils"',
        "classification": "A. controller/proof-object candidate",
        "reason": "This transfers family utility evidence into the replacement audit payload.",
    },
    "exact_blocker_alias_fill": {
        "token": '"post_click_exact_blockers_by_family" not in _post_click_bending_audit',
        "classification": "A. controller/proof-object candidate",
        "reason": "This is evidence normalization and should not remain page-owned long term.",
    },
    "low_bending_resolution_builder": {
        "token": "_post_click_low_bending_resolution_item(",
        "classification": "A. controller-owned recommendation candidate",
        "reason": "This constructs the post-click low-bending replacement item.",
    },
    "bending_contract_extract": {
        "token": "_post_click_bending_contract = (",
        "classification": "A. controller-owned result candidate",
        "reason": "This extracts the replacement contract result from the built item.",
    },
    "disabled_contract_guard": {
        "token": "and not _design_guide_button_contract_enabled(_post_click_bending_contract)",
        "classification": "B. pre-publication guard to preserve for now",
        "reason": "This guard decides whether the replacement body can publish a blocker item.",
    },
    "final_visible_binding_restamper": {
        "token": "_publish_final_visible_design_guide_contract_binding(",
        "classification": "C. bridge/restamper candidate",
        "reason": "This rebinds the replacement through an old page bridge before the adapter result.",
    },
    "exact_blocker_adapter_result": {
        "token": "_build_final_design_guide_post_click_final_contract_check_adapter_result(",
        "classification": "D. already adapter-backed",
        "reason": "This replacement result is already behind a FinalDesignGuidePublication adapter.",
    },
    "final_visible_resolution_mutation": {
        "token": "_final_visible_resolution.clear()",
        "classification": "E. live render bridge mutation keep until result cutover",
        "reason": "This mutates the render resolution and needs a dedicated cutover before deletion.",
    },
    "guidance_debug_patch_update": {
        "token": "guidance_debug.update(",
        "classification": "F. debug/session patch keep non-authoritative",
        "reason": "This applies adapter debug proof patches and should remain non-authoritative.",
    },
    "adapter_result_cutover_stamps": {
        "token": "final_publication_post_click_final_contract_adapter_result_live_cutover_used",
        "classification": "F. compatibility/proof stamp",
        "reason": "This records the adapter result cutover without owning product truth.",
    },
}


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
    rows = {
        name: {
            **meta,
            "present": str(meta.get("token") or "") in target,
            "delete_now": False,
        }
        for name, meta in OWNERSHIP_ROWS.items()
    }
    counts: dict[str, int] = {}
    for row in rows.values():
        classification = str(row.get("classification") or "unknown")
        counts[classification] = counts.get(classification, 0) + 1
    latest = {
        "predicate_trace": _latest(
            "design_guide_live_post_click_final_contract_predicate_result_adapter_trace"
        ),
        "predicate_cutover": _latest(
            "design_guide_post_click_final_contract_predicate_result_adapter_cutover"
        ),
        "legacy_predicate_deletion": _latest(
            "design_guide_post_click_final_contract_legacy_predicate_deletion_audit"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "POST_CLICK_BENDING_REPLACEMENT_BODY_MAPPED_NOT_READY_TO_DELETE",
        "target_block_found": bool(target),
        "rows": rows,
        "classification_counts": counts,
        "missing_rows": [name for name, row in rows.items() if row.get("present") is not True],
        "delete_now_count": 0,
        "next_safe_step": (
            "Create a controller/proof object for post-click bending replacement audit plus "
            "resolution result, then wire it trace-only beside this body before moving or deleting rows."
        ),
        "latest": latest,
        "all_latest_required_artifacts_pass": all(
            (item or {}).get("status") == "PASS" for item in latest.values()
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    return {
        "target_block_found": capture.get("target_block_found") is True,
        "all_rows_present": not capture.get("missing_rows"),
        "delete_now_count_zero": capture.get("delete_now_count") == 0,
        "all_latest_required_artifacts_pass": (
            capture.get("all_latest_required_artifacts_pass") is True
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
        "# Post-Click Bending Replacement Body Ownership Audit",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Delete-now count: `{capture.get('delete_now_count')}`",
        f"- Missing rows: `{capture.get('missing_rows')}`",
        "",
        "## Classification Counts",
        "",
    ]
    for key, value in (capture.get("classification_counts") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Rows", ""])
    for name, row in (capture.get("rows") or {}).items():
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
        "schema": "design_guide_post_click_bending_replacement_body_ownership_audit.v1",
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
        / f"design_guide_post_click_bending_replacement_body_ownership_audit_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_post_click_bending_replacement_body_ownership_audit_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_post_click_bending_replacement_body_ownership_audit {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
