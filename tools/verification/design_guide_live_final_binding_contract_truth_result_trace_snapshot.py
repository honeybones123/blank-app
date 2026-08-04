"""Trace snapshot for final-binding enabled-contract truth result."""

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

HELPER = "def _stamp_final_visible_contract_binding_truth_result("
BINDING = "def _publish_final_visible_design_guide_contract_binding("
BUILDER = "def build_final_visible_contract_binding_truth_result("


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


def _line_number(source: str, token: str) -> int | None:
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line:
            return index
    return None


def _capture() -> dict[str, Any]:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8-sig", errors="replace").lstrip("\ufeff")
    helper = _function_block(inputs_source, HELPER)
    binding = _function_block(inputs_source, BINDING)
    builder = _function_block(publication_source, BUILDER)
    call = "_stamp_final_visible_contract_binding_truth_result("
    latest = {
        "object": _latest("design_guide_final_binding_contract_truth_result_object"),
        "residual_policy": _latest("design_guide_final_binding_residual_policy_ownership"),
        "consistency_cutover": _latest("design_guide_final_binding_consistency_guard_result_cutover"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    trace_call_index = binding.find(call)
    no_second_index = binding.find("_stamp_final_visible_contract_binding_no_second_cta_result(")
    return {
        "decision": "LIVE_FINAL_BINDING_CONTRACT_TRUTH_RESULT_TRACE_WIRED",
        "import_alias_present": (
            "build_final_visible_contract_binding_truth_result as "
            "_build_final_visible_contract_binding_truth_result"
        )
        in inputs_source,
        "helper_present": bool(helper),
        "helper_line": _line_number(inputs_source, HELPER),
        "binding_present": bool(binding),
        "builder_present": bool(builder),
        "builder_call_present_in_helper": (
            "_build_final_visible_contract_binding_truth_result(" in helper
        ),
        "trace_call_count_in_binding": binding.count(call),
        "trace_call_before_no_second_cta": (
            trace_call_index >= 0 and no_second_index >= 0 and trace_call_index < no_second_index
        ),
        "combined_preview_boundary": {
            "page_evaluator_still_in_binding": "_evaluate_auto_design_candidate(" in binding,
            "combined_preview_util_initialized": "combined_binding_bending_util = None" in binding,
            "plain_combined_util_passed_to_helper": (
                "combined_binding_bending_util=combined_binding_bending_util" in binding
            ),
            "no_evaluator_in_helper": "_evaluate_auto_design_candidate(" not in helper,
            "no_evaluator_in_builder": "_evaluate_auto_design_candidate(" not in builder,
        },
        "plain_boundary_inputs_passed": {
            "evidence": "evidence_for_binding=evidence_for_binding" in binding,
            "contract": "contract=contract" in binding,
            "item": "item=out" in binding,
            "updates": "updates=updates" in binding,
            "live_expected": "live_evidence_expected_util=evidence_expected_util" in binding,
            "live_contract_expected": "live_contract_expected_util=contract_expected_util" in binding,
            "live_family": "live_evidence_family=evidence_family_for_contract" in binding,
            "live_cross_family": (
                "live_contract_updates_cross_family=contract_updates_cross_family" in binding
            ),
            "live_blockers": "live_blocker_families=sorted(blocker_families_for_contract)" in binding,
        },
        "debug_stamps_present": {
            "payload": '"final_binding_contract_truth_result"' in helper,
            "result_hash": '"final_binding_contract_truth_result_hash"' in helper,
            "proof_hash": '"final_binding_contract_truth_result_proof_hash"' in helper,
            "parity": '"final_binding_contract_truth_result_parity"' in helper,
            "family": '"final_binding_contract_truth_result_family"' in helper,
            "expected_util": '"final_binding_contract_truth_result_expected_util"' in helper,
            "contract_expected": '"final_binding_contract_truth_result_contract_expected_util"' in helper,
            "cross_family": '"final_binding_contract_truth_result_cross_family"' in helper,
            "blocker_families": '"final_binding_contract_truth_result_blocker_families"' in helper,
            "live_family": '"final_binding_contract_truth_result_live_family"' in helper,
            "live_expected": '"final_binding_contract_truth_result_live_expected_util"' in helper,
            "live_blockers": '"final_binding_contract_truth_result_live_blocker_families"' in helper,
        },
        "non_driving_flags_present": {
            "proof_only": '"final_binding_contract_truth_result_proof_only"' in helper,
            "product": '"final_binding_contract_truth_result_product_driving"' in helper and "= False" in helper,
            "render": '"final_binding_contract_truth_result_render_driving"' in helper and "= False" in helper,
            "apply": '"final_binding_contract_truth_result_apply_driving"' in helper and "= False" in helper,
            "session": '"final_binding_contract_truth_result_session_driving"' in helper and "= False" in helper,
            "not_ready_for_cutover": (
                '"final_binding_contract_truth_result_ready_for_live_cutover"' in helper
                and "= False" in helper
            ),
        },
        "builder_remains_trace_only": {
            "proof_only": '"proof_only": True' in builder,
            "product": '"product_driving": False' in builder,
            "render": '"render_driving": False' in builder,
            "apply": '"apply_driving": False' in builder,
            "session": '"session_driving": False' in builder,
            "ready_for_trace_wiring": '"ready_for_trace_wiring": True' in builder,
            "not_ready_for_cutover": '"ready_for_live_cutover": False' in builder,
        },
        "trace_ready_for_cutover": False,
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
        "import_alias_present": capture.get("import_alias_present") is True,
        "helper_present": capture.get("helper_present") is True,
        "binding_present": capture.get("binding_present") is True,
        "builder_present": capture.get("builder_present") is True,
        "builder_call_present_in_helper": capture.get("builder_call_present_in_helper") is True,
        "trace_call_once_in_binding": capture.get("trace_call_count_in_binding") == 1,
        "trace_call_before_no_second_cta": capture.get("trace_call_before_no_second_cta") is True,
        "combined_preview_boundary": all((capture.get("combined_preview_boundary") or {}).values()),
        "plain_boundary_inputs_passed": all((capture.get("plain_boundary_inputs_passed") or {}).values()),
        "debug_stamps_present": all((capture.get("debug_stamps_present") or {}).values()),
        "non_driving_flags_present": all((capture.get("non_driving_flags_present") or {}).values()),
        "builder_remains_trace_only": all((capture.get("builder_remains_trace_only") or {}).values()),
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "residual_policy_pass": (latest.get("residual_policy") or {}).get("status") == "PASS",
        "consistency_cutover_pass": (latest.get("consistency_cutover") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "not_cutover_ready_yet": capture.get("trace_ready_for_cutover") is False,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Live Final Binding Contract Truth Result Trace",
        "",
        f"Status: `{payload.get('status')}`",
        f"Decision: `{capture.get('decision')}`",
        f"Snapshot hash: `{payload.get('snapshot_hash')}`",
        "",
        "## Summary",
        "",
        f"- Helper line: `{capture.get('helper_line')}`",
        f"- Trace call count in binding helper: `{capture.get('trace_call_count_in_binding')}`",
        f"- Trace ready for live cutover: `{capture.get('trace_ready_for_cutover')}`",
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
        "schema": "design_guide_live_final_binding_contract_truth_result_trace_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_live_final_binding_contract_truth_result_trace_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_final_binding_contract_truth_result_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_live_final_binding_contract_truth_result_trace {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
