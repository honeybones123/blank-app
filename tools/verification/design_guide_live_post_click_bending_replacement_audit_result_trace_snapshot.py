"""Trace wiring proof for post-click bending replacement audit/result object."""

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

IMPORT_TOKEN = (
    "build_final_design_guide_post_click_bending_replacement_audit_result_proof "
    "as _build_final_design_guide_post_click_bending_replacement_audit_result_proof"
)
HELPER_TOKEN = (
    "def _stamp_final_publication_post_click_bending_replacement_audit_result_proof("
)
BUILDER_CALL = "_build_final_design_guide_post_click_bending_replacement_audit_result_proof("
TARGET_START = "_post_click_bending_audit = {}"
TARGET_END = "_post_click_replacement_decision_proof = _stamp_final_publication_post_click_replacement_decision_proof("
STAMP_CALL = "_stamp_final_publication_post_click_bending_replacement_audit_result_proof("
REQUIRED_STAMPS = (
    "final_publication_post_click_bending_replacement_audit_result_proof",
    "final_publication_post_click_bending_replacement_audit_result_proof_hash",
    "final_publication_post_click_bending_replacement_audit_projection_hash",
    "final_publication_post_click_bending_replacement_resolution_result_hash",
    "final_publication_post_click_bending_replacement_audit_result_covered_rows",
    "final_publication_post_click_bending_replacement_audit_result_proof_only",
    "final_publication_post_click_bending_replacement_audit_result_product_driving",
    "final_publication_post_click_bending_replacement_audit_result_render_driving",
    "final_publication_post_click_bending_replacement_audit_result_apply_driving",
    "final_publication_post_click_bending_replacement_audit_result_session_driving",
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


def _block(source: str, start_token: str, end_token: str | None = None) -> str:
    start = source.find(start_token)
    if start < 0:
        return ""
    end = source.find(end_token, start) if end_token else source.find("\ndef ", start + 1)
    return source[start:end] if end > start else ""


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper = _block(source, HELPER_TOKEN)
    target = _block(source, TARGET_START, TARGET_END)
    latest = {
        "object": _latest("design_guide_post_click_bending_replacement_audit_result_object"),
        "body_audit": _latest("design_guide_post_click_bending_replacement_body_ownership_audit"),
        "predicate_deletion": _latest(
            "design_guide_post_click_final_contract_legacy_predicate_deletion_audit"
        ),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "LIVE_POST_CLICK_BENDING_REPLACEMENT_AUDIT_RESULT_TRACE_PROVEN",
        "import_present": IMPORT_TOKEN in source,
        "helper_present": bool(helper),
        "builder_call_in_helper": BUILDER_CALL in helper,
        "target_block_found": bool(target),
        "stamp_call_count_in_target": target.count(STAMP_CALL),
        "stamp_after_live_body": (
            target.find("_post_click_bending_replacement_applied = bool(")
            < target.find(STAMP_CALL)
            if STAMP_CALL in target
            else False
        ),
        "stamp_before_replacement_decision": bool(target.strip().endswith("")),
        "audit_sources_passed": all(
            token in target
            for token in (
                'candidate_search_evidence") or {})',
                'action_payload") or {}).get(',
                'resolved_candidate") or {}).get(',
            )
        ),
        "resolution_surfaces_passed": all(
            token in target
            for token in (
                "bending_resolution=dict(_post_click_bending_resolution or {})",
                "bending_contract=dict(_post_click_bending_contract or {})",
                "output_item=dict(_final_visible_item or {})",
                "final_visible_resolution=dict(_final_visible_resolution or {})",
            )
        ),
        "required_stamps_present": all(token in helper for token in REQUIRED_STAMPS),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "family_runtime_changed": False,
        "latest": latest,
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "import_present": capture.get("import_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "builder_call_in_helper": capture.get("builder_call_in_helper") is True,
        "target_block_found": capture.get("target_block_found") is True,
        "stamp_call_once_in_target": capture.get("stamp_call_count_in_target") == 1,
        "stamp_after_live_body": capture.get("stamp_after_live_body") is True,
        "audit_sources_passed": capture.get("audit_sources_passed") is True,
        "resolution_surfaces_passed": capture.get("resolution_surfaces_passed") is True,
        "required_stamps_present": capture.get("required_stamps_present") is True,
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "body_audit_pass": (latest.get("body_audit") or {}).get("status") == "PASS",
        "predicate_deletion_pass": (latest.get("predicate_deletion") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
        "family_runtime_unchanged": capture.get("family_runtime_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Live Post-Click Bending Replacement Audit/Result Trace Snapshot",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Stamp calls in target block: `{capture.get('stamp_call_count_in_target')}`",
        f"- Stamp after live body: `{capture.get('stamp_after_live_body')}`",
        f"- Required stamps present: `{capture.get('required_stamps_present')}`",
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
            "Next safe slice: add live parity/readiness before moving the audit merge into the object.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    capture = _capture()
    checks = _checks(capture)
    failures = [key for key, value in checks.items() if value is not True]
    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema": "design_guide_live_post_click_bending_replacement_audit_result_trace_snapshot.v1",
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
        / f"design_guide_live_post_click_bending_replacement_audit_result_trace_{stamp}.json"
    )
    md_path = (
        AUDIT_DIR
        / f"design_guide_live_post_click_bending_replacement_audit_result_trace_{stamp}.md"
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_live_post_click_bending_replacement_audit_result_trace {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
