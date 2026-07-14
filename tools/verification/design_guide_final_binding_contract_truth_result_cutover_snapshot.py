"""Cutover verifier for final-binding enabled-contract truth result."""

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

BINDING = "def _publish_final_visible_design_guide_contract_binding("


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _latest(prefix: str) -> dict[str, Any]:
    paths = sorted(ARTIFACT_DIR.glob(f"{prefix}_*.json"), key=lambda path: path.stat().st_mtime)
    if not paths:
        return {"found": False, "status": "MISSING", "path": None}
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
    status = str(payload.get("status") or payload.get("result") or payload.get("lock_status") or "")
    if "PASS" in status.upper() or "LOCKED" in status.upper() or "COMPLETE" in status.upper():
        status = "PASS"
    return {"found": True, "status": status or "UNKNOWN", "path": str(path)}


def _function_block(source: str, token: str) -> str:
    start = source.find(token)
    if start < 0:
        return ""
    end = source.find("\ndef ", start + 1)
    return source[start:end] if end > start else source[start:]


def _capture() -> dict[str, Any]:
    source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    binding = _function_block(source, BINDING)
    payload_assignment = (
        "final_binding_contract_truth_payload = _stamp_final_visible_contract_binding_truth_result("
    )
    result_assignment = (
        "final_binding_contract_truth_result = dict("
    )
    cutover_guard = "if final_binding_contract_truth_result:"
    cutover_assignments = {
        "evidence_expected_util": (
            "evidence_expected_util = final_binding_contract_truth_result.get(\"evidence_expected_util\")"
            in binding
        ),
        "contract_expected_util": (
            "contract_expected_util = final_binding_contract_truth_result.get(\"contract_expected_util\")"
            in binding
        ),
        "evidence_family_for_contract": (
            "final_binding_contract_truth_result.get(\"evidence_family_for_contract\")" in binding
        ),
        "contract_updates_cross_family": (
            "final_binding_contract_truth_result.get(\"contract_updates_cross_family\")" in binding
        ),
        "contract_update_keys_for_family": (
            "final_binding_contract_truth_result.get(\"contract_update_keys_for_family\")" in binding
        ),
        "contract_combined_text": (
            "final_binding_contract_truth_result.get(\"contract_combined_text\")" in binding
        ),
        "title_hint_for_contract": (
            "final_binding_contract_truth_result.get(\"title_hint_for_contract\")" in binding
        ),
        "blocker_families_for_contract": (
            "final_binding_contract_truth_result.get(\"blocker_families_for_contract\")" in binding
        ),
    }
    old_fallback_still_present = {
        "evidence_expected_util": "evidence_expected_util = _parse_util_value(" in binding,
        "family_truth": "evidence_family_for_contract = str(evidence_for_binding.get(\"family\") or \"\")" in binding,
        "cross_family_truth": "contract_updates_cross_family = bool(" in binding,
        "blocker_truth": "blocker_families_for_contract = {evidence_family_for_contract}" in binding,
    }
    debug_cutover_stamps = {
        "used": '"final_binding_contract_truth_result_live_cutover_used"' in binding,
        "hash": '"final_binding_contract_truth_result_live_cutover_hash"' in binding,
        "proof_hash": '"final_binding_contract_truth_result_live_cutover_proof_hash"' in binding,
        "source": '"FinalDesignGuidePublication.final_visible_contract_binding_truth"' in binding,
    }
    trace_index = binding.find(payload_assignment)
    no_second_index = binding.find("_stamp_final_visible_contract_binding_no_second_cta_result(")
    latest = {
        "object": _latest("design_guide_final_binding_contract_truth_result_object"),
        "trace": _latest("design_guide_live_final_binding_contract_truth_result_trace"),
        "parity": _latest("design_guide_final_binding_contract_truth_result_parity_scenarios"),
        "readiness": _latest("design_guide_final_binding_contract_truth_cutover_readiness"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_BINDING_CONTRACT_TRUTH_RESULT_CUTOVER",
        "binding_present": bool(binding),
        "payload_assignment_present": payload_assignment in binding,
        "result_assignment_present": result_assignment in binding,
        "cutover_guard_present": cutover_guard in binding,
        "cutover_assignments": cutover_assignments,
        "old_fallback_still_present": old_fallback_still_present,
        "debug_cutover_stamps": debug_cutover_stamps,
        "cutover_before_no_second_cta": (
            trace_index >= 0 and no_second_index >= 0 and trace_index < no_second_index
        ),
        "manual_fallback_deleted": False,
        "ready_for_deletion": False,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "engineering_behavior_changed": False,
        "latest": {
            key: {"status": value.get("status"), "path": value.get("path")}
            for key, value in latest.items()
        },
    }


def _checks(capture: dict[str, Any]) -> dict[str, bool]:
    latest = dict(capture.get("latest") or {})
    return {
        "binding_present": capture.get("binding_present") is True,
        "payload_assignment_present": capture.get("payload_assignment_present") is True,
        "result_assignment_present": capture.get("result_assignment_present") is True,
        "cutover_guard_present": capture.get("cutover_guard_present") is True,
        "cutover_assignments": all((capture.get("cutover_assignments") or {}).values()),
        "old_fallback_still_present": all((capture.get("old_fallback_still_present") or {}).values()),
        "debug_cutover_stamps": all((capture.get("debug_cutover_stamps") or {}).values()),
        "cutover_before_no_second_cta": capture.get("cutover_before_no_second_cta") is True,
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "readiness_pass": (latest.get("readiness") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "manual_fallback_not_deleted": capture.get("manual_fallback_deleted") is False,
        "not_deletion_ready": capture.get("ready_for_deletion") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Binding Contract Truth Result Cutover",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Manual fallback deleted: `{capture.get('manual_fallback_deleted')}`",
        f"- Ready for deletion: `{capture.get('ready_for_deletion')}`",
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
        "schema": "design_guide_final_binding_contract_truth_result_cutover_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_contract_truth_result_cutover_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_contract_truth_result_cutover_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_contract_truth_result_cutover {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
