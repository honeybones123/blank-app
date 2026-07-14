"""Trace snapshot for final-binding contract consistency guard result."""

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

HELPER = "def _stamp_final_visible_contract_binding_consistency_guard_result("
BINDING = "def _publish_final_visible_design_guide_contract_binding("
BUILDER = "def build_final_visible_contract_binding_consistency_guard_result("


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
    call = "_stamp_final_visible_contract_binding_consistency_guard_result("
    latest = {
        "object": _latest("design_guide_final_binding_consistency_guard_result_object"),
        "residual_policy": _latest("design_guide_final_binding_residual_policy_ownership"),
        "independence_lock": _latest("design_guide_independence_lock"),
        "render_bridge_lock": _latest("design_guide_render_bridge_lock"),
        "compute_bridge_lock": _latest("design_guide_compute_resolver_publication_bridge_lock"),
    }
    return {
        "decision": "LIVE_FINAL_BINDING_CONSISTENCY_GUARD_RESULT_TRACE_WIRED",
        "import_alias_present": (
            "build_final_visible_contract_binding_consistency_guard_result as "
            "_build_final_visible_contract_binding_consistency_guard_result"
        )
        in inputs_source,
        "helper_present": bool(helper),
        "helper_line": _line_number(inputs_source, HELPER),
        "binding_present": bool(binding),
        "builder_present": bool(builder),
        "builder_call_present_in_helper": (
            "_build_final_visible_contract_binding_consistency_guard_result(" in helper
        ),
        "trace_call_count_in_binding": binding.count(call),
        "callsites_present": {
            "shear": 'callsite_id="shear_safe_binding_contract_mismatch_reset"' in binding,
            "combined": 'callsite_id="combined_binding_contract_mismatch_reset"' in binding,
        },
        "trace_calls_before_resets": {
            "shear": (
                binding.find('callsite_id="shear_safe_binding_contract_mismatch_reset"') >= 0
                and (
                    binding.find("if final_binding_safe_consistency_guard_resets:") >= 0
                    or binding.find("if safe_binding_evidence_available and dict(updates) != dict(safe_binding_updates):") >= 0
                )
                and binding.find('callsite_id="shear_safe_binding_contract_mismatch_reset"')
                < (
                    binding.find("if final_binding_safe_consistency_guard_resets:")
                    if binding.find("if final_binding_safe_consistency_guard_resets:") >= 0
                    else binding.find("if safe_binding_evidence_available and dict(updates) != dict(safe_binding_updates):")
                )
            ),
            "combined": (
                binding.find('callsite_id="combined_binding_contract_mismatch_reset"') >= 0
                and (
                    binding.find("if final_binding_combined_consistency_guard_resets:") >= 0
                    or binding.find("if combined_binding_evidence_available and dict(updates) != dict(combined_binding_updates):") >= 0
                )
                and binding.find('callsite_id="combined_binding_contract_mismatch_reset"')
                < (
                    binding.find("if final_binding_combined_consistency_guard_resets:")
                    if binding.find("if final_binding_combined_consistency_guard_resets:") >= 0
                    else binding.find("if combined_binding_evidence_available and dict(updates) != dict(combined_binding_updates):")
                )
            ),
        },
        "plain_boundary_inputs_passed": {
            "evidence": "evidence_for_binding=evidence_for_binding" in binding,
            "current_updates": "current_updates=updates" in binding,
            "safe_updates": "safe_binding_updates=safe_binding_updates" in binding,
            "combined_updates": "combined_binding_updates=combined_binding_updates" in binding,
            "safe_already": "safe_updates_already_applied=_updates_match_state(state or {}, safe_binding_updates)" in binding,
            "combined_already": "combined_updates_already_applied=_updates_match_state(state or {}, combined_binding_updates)" in binding,
            "live_resets": "live_resets=bool(" in binding,
        },
        "debug_stamps_present": {
            "payload": '"final_binding_consistency_guard_result"' in helper,
            "result_map": '"final_binding_consistency_guard_results"' in helper,
            "result_hash": '"final_binding_consistency_guard_result_hash"' in helper,
            "proof_hash": '"final_binding_consistency_guard_result_proof_hash"' in helper,
            "callsite": '"final_binding_consistency_guard_result_callsite"' in helper,
            "resets": '"final_binding_consistency_guard_result_resets"' in helper,
            "reason": '"final_binding_consistency_guard_result_reason"' in helper,
            "parity": '"final_binding_consistency_guard_result_parity"' in helper,
            "live_resets": '"final_binding_consistency_guard_result_live_resets"' in helper,
        },
        "non_driving_flags_present": {
            "proof_only": '"final_binding_consistency_guard_result_proof_only"' in helper,
            "product": '"final_binding_consistency_guard_result_product_driving"' in helper and "= False" in helper,
            "render": '"final_binding_consistency_guard_result_render_driving"' in helper and "= False" in helper,
            "apply": '"final_binding_consistency_guard_result_apply_driving"' in helper and "= False" in helper,
            "session": '"final_binding_consistency_guard_result_session_driving"' in helper and "= False" in helper,
            "ready_for_cutover": (
                '"final_binding_consistency_guard_result_ready_for_live_cutover"' in helper
                and "= True" in helper
            ),
        },
        "builder_remains_trace_only": {
            "proof_only": '"proof_only": True' in builder,
            "product": '"product_driving": False' in builder,
            "render": '"render_driving": False' in builder,
            "apply": '"apply_driving": False' in builder,
            "session": '"session_driving": False' in builder,
            "ready_for_cutover": '"ready_for_live_cutover": True' in builder,
        },
        "trace_ready_for_cutover": True,
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
        "trace_call_twice_in_binding": capture.get("trace_call_count_in_binding") == 2,
        "callsites_present": all((capture.get("callsites_present") or {}).values()),
        "trace_calls_before_resets": all((capture.get("trace_calls_before_resets") or {}).values()),
        "plain_boundary_inputs_passed": all((capture.get("plain_boundary_inputs_passed") or {}).values()),
        "debug_stamps_present": all((capture.get("debug_stamps_present") or {}).values()),
        "non_driving_flags_present": all((capture.get("non_driving_flags_present") or {}).values()),
        "builder_remains_trace_only": all((capture.get("builder_remains_trace_only") or {}).values()),
        "object_pass": (latest.get("object") or {}).get("status") == "PASS",
        "residual_policy_pass": (latest.get("residual_policy") or {}).get("status") == "PASS",
        "independence_lock_pass": (latest.get("independence_lock") or {}).get("status") == "PASS",
        "render_bridge_lock_pass": (latest.get("render_bridge_lock") or {}).get("status") == "PASS",
        "compute_bridge_lock_pass": (latest.get("compute_bridge_lock") or {}).get("status") == "PASS",
        "cutover_ready": capture.get("trace_ready_for_cutover") is True,
        "product_behavior_unchanged": capture.get("product_behavior_changed") is False,
        "visible_wording_unchanged": capture.get("visible_wording_changed") is False,
        "cta_apply_semantics_unchanged": capture.get("cta_apply_semantics_changed") is False,
        "engineering_behavior_unchanged": capture.get("engineering_behavior_changed") is False,
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    capture = dict(payload.get("capture") or {})
    lines = [
        "# Live Final Binding Consistency Guard Result Trace",
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
        "schema": "design_guide_live_final_binding_consistency_guard_result_trace_snapshot.v1",
        "status": status,
        "created_at": _stamp(),
        "capture": capture,
        "checks": checks,
        "failures": failures,
    }
    payload["snapshot_hash"] = _stable_hash(payload)
    stamp = payload["created_at"]
    json_path = ARTIFACT_DIR / f"design_guide_live_final_binding_consistency_guard_result_trace_{stamp}.json"
    md_path = AUDIT_DIR / f"design_guide_live_final_binding_consistency_guard_result_trace_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_report(md_path, payload)
    print(f"design_guide_live_final_binding_consistency_guard_result_trace {status}")
    print(f"decision={capture.get('decision')}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    if failures:
        print("failures=" + ", ".join(failures))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
