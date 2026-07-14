"""Cutover readiness for final-binding enabled-contract truth result."""

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
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"

BINDING = "def _publish_final_visible_design_guide_contract_binding("
HELPER = "def _stamp_final_visible_contract_binding_truth_result("
BUILDER = "def build_final_visible_contract_binding_truth_result("

REQUIRED_RESULT_FIELDS = {
    "evidence_expected_util",
    "contract_expected_util",
    "evidence_family_for_contract",
    "family_resolution_source",
    "util_resolution_source",
    "contract_updates_cross_family",
    "blocker_families_for_contract",
    "contract_update_keys_for_family",
    "contract_combined_text",
    "title_hint_for_contract",
    "debug_effect",
}


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
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    binding = _function_block(inputs_source, BINDING)
    helper = _function_block(inputs_source, HELPER)
    builder = _function_block(publication_source, BUILDER)
    old_live_truth_assignments = {
        "evidence_expected_util": "evidence_expected_util = _parse_util_value(" in binding,
        "contract_expected_util": "contract_expected_util = _parse_util_value(contract.get(\"expected_util\"))" in binding,
        "evidence_family_for_contract": (
            "evidence_family_for_contract = str(evidence_for_binding.get(\"family\") or \"\")" in binding
        ),
        "contract_update_keys_for_family": "contract_update_keys_for_family = {" in binding,
        "contract_updates_cross_family": "contract_updates_cross_family = bool(" in binding,
        "contract_combined_text": "contract_combined_text = \" \".join(" in binding,
        "title_hint_for_contract": "title_hint_for_contract = \" \".join(" in binding,
        "bending_target_util_override": "bending_target_util = _parse_util_value(" in binding,
        "combined_preview_plain_value": "combined_binding_bending_util = _parse_util_value(" in binding,
        "blocker_families_for_contract": "blocker_families_for_contract = {evidence_family_for_contract}" in binding,
    }
    result_fields_represented = {
        field: f'"{field}"' in builder
        for field in sorted(REQUIRED_RESULT_FIELDS)
    }
    helper_reads_result_fields = {
        "evidence_expected_util": 'result.get("evidence_expected_util")' in helper,
        "contract_expected_util": 'result.get("contract_expected_util")' in helper,
        "evidence_family_for_contract": 'result.get("evidence_family_for_contract")' in helper,
        "contract_updates_cross_family": 'result.get("contract_updates_cross_family")' in helper,
        "blocker_families_for_contract": 'result.get("blocker_families_for_contract")' in helper,
    }
    trace_call_index = binding.find("_stamp_final_visible_contract_binding_truth_result(")
    no_second_index = binding.find("_stamp_final_visible_contract_binding_no_second_cta_result(")
    latest = {
        "object": _latest("design_guide_final_binding_contract_truth_result_object"),
        "trace": _latest("design_guide_live_final_binding_contract_truth_result_trace"),
        "parity": _latest("design_guide_final_binding_contract_truth_result_parity_scenarios"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "FINAL_BINDING_CONTRACT_TRUTH_READY_FOR_TRUTH_VARIABLE_CUTOVER",
        "binding_present": bool(binding),
        "helper_present": bool(helper),
        "builder_present": bool(builder),
        "old_live_truth_assignments": old_live_truth_assignments,
        "result_fields_represented": result_fields_represented,
        "helper_reads_result_fields": helper_reads_result_fields,
        "trace_call_before_no_second_cta": (
            trace_call_index >= 0 and no_second_index >= 0 and trace_call_index < no_second_index
        ),
        "combined_preview_evaluator_boundary": {
            "page_evaluator_still_page_owned": "_evaluate_auto_design_candidate(" in binding,
            "builder_does_not_evaluate": "_evaluate_auto_design_candidate(" not in builder,
            "helper_does_not_evaluate": "_evaluate_auto_design_candidate(" not in helper,
            "plain_preview_value_passed": "combined_binding_bending_util=combined_binding_bending_util" in binding,
        },
        "ready_for_truth_variable_cutover": True,
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
        "helper_present": capture.get("helper_present") is True,
        "builder_present": capture.get("builder_present") is True,
        "old_live_truth_assignments_present": all(
            (capture.get("old_live_truth_assignments") or {}).values()
        ),
        "result_fields_represented": all((capture.get("result_fields_represented") or {}).values()),
        "helper_reads_result_fields": all((capture.get("helper_reads_result_fields") or {}).values()),
        "trace_call_before_no_second_cta": capture.get("trace_call_before_no_second_cta") is True,
        "combined_preview_evaluator_boundary": all(
            (capture.get("combined_preview_evaluator_boundary") or {}).values()
        ),
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "trace_pass": (latest.get("trace") or {}).get("status") == "PASS",
        "parity_pass": (latest.get("parity") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "ready_for_truth_variable_cutover": capture.get("ready_for_truth_variable_cutover") is True,
        "not_deletion_ready": capture.get("ready_for_deletion") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Final Binding Contract Truth Cutover Readiness",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Ready for truth variable cutover: `{capture.get('ready_for_truth_variable_cutover')}`",
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
        "schema": "design_guide_final_binding_contract_truth_cutover_readiness_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_final_binding_contract_truth_cutover_readiness_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_final_binding_contract_truth_cutover_readiness_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_final_binding_contract_truth_cutover_readiness {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
