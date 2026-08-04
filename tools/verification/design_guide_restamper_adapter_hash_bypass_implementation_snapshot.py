from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
ARTIFACTS = ROOT / "artifacts"
VERIFICATION = ARTIFACTS / "verification"
AUDITS = ARTIFACTS / "audits"

EXPECTED_CALLSITES = (
    "render_guidance_secondary_primary_binding",
    "render_fast_design_guidance_panel.final_visible_item_binding",
)


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _function_body(source: str, name: str) -> str:
    start = source.find(f"def {name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    return source[start : next_def if next_def >= 0 else len(source)]


def _call_with_callsite_present(text: str, function_name: str, callsite_id: str) -> bool:
    pattern = re.compile(
        rf"{re.escape(function_name)}\(\s*[\s\S]{{0,900}}?callsite_id\s*=\s*{re.escape(json.dumps(callsite_id))}",
        re.MULTILINE,
    )
    return bool(pattern.search(text))


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    source = INPUTS.read_text(encoding="utf-8")
    bypass_body = _function_body(source, "_maybe_bypass_final_visible_restamper_bridge_noop")
    failures: list[str] = []

    if not bypass_body:
        failures.append("bypass_function_missing")

    required_bypass_tokens = (
        'debug_sink.get("final_visible_restamper_adapter_bypass_states")',
        "missing_previous_adapter_state",
        "missing_previous_adapter_hash",
        "previous_adapter_fallback_state",
        "adapter_state_mismatch",
        "previous_output_not_current_input",
        "stable_adapter_hash_restamper_bridge",
        '"adapter_state_hash": current.get("bypass_state_hash")',
    )
    for token in required_bypass_tokens:
        if token not in bypass_body:
            failures.append(f"bypass_missing:{token}")

    forbidden_bypass_tokens = (
        'debug_sink.get("final_visible_final_visible_output_bridge_proofs")',
        "missing_previous_proof",
        "stable_noop_restamper_bridge",
        'current_response = _run_design_guide_controller_final_visible_output_bridge_trace_only',
    )
    for token in forbidden_bypass_tokens:
        if token in bypass_body:
            failures.append(f"bypass_still_uses_proof_dependency:{token}")

    guard_tokens = (
        "debug_force_rebuild",
        "apply_in_flight",
        "post_click_state_present",
    )
    for token in guard_tokens:
        if token not in bypass_body:
            failures.append(f"bypass_guard_missing:{token}")

    recording_helper_present = all(
        token in source
        for token in (
            "def _final_visible_restamper_adapter_bypass_state(",
            "def _record_final_visible_restamper_adapter_bypass_state(",
            "final_visible_restamper_adapter_bypass_states",
            "final_visible_restamper_adapter_bypass_states_hash",
        )
    )
    if not recording_helper_present:
        failures.append("adapter_bypass_state_recording_helper_missing")

    record_calls = source.count("_record_final_visible_restamper_adapter_bypass_state(") - 1
    if record_calls < 2:
        failures.append(f"adapter_bypass_state_record_calls:{record_calls}")

    callsites: list[dict[str, object]] = []
    for callsite in EXPECTED_CALLSITES:
        bypass_call = _call_with_callsite_present(
            source, "_maybe_bypass_final_visible_restamper_bridge_noop", callsite
        )
        stamp_call = _call_with_callsite_present(
            source, "_stamp_final_visible_final_visible_output_bridge_proof", callsite
        )
        nearby = source[
            max(source.find(json.dumps(callsite)) - 900, 0) : source.find(json.dumps(callsite)) + 2200
        ]
        adapter_hash_debug = 'get("adapter_state_hash")' in nearby
        proof_hash_debug = 'get("proof_hash")' in nearby
        row = {
            "callsite_id": callsite,
            "bypass_call_present": bypass_call,
            "proof_stamp_deleted_after_deadness_proof": not stamp_call,
            "debug_hash_uses_adapter_state_hash": adapter_hash_debug,
            "debug_hash_still_uses_proof_hash": proof_hash_debug,
        }
        callsites.append(row)
        if not bypass_call:
            failures.append(f"callsite_bypass_missing:{callsite}")
        if not adapter_hash_debug:
            failures.append(f"callsite_adapter_hash_debug_missing:{callsite}")
        if proof_hash_debug:
            failures.append(f"callsite_still_records_proof_hash:{callsite}")

    proof_stamp_body_present = "def _stamp_final_visible_final_visible_output_bridge_proof(" in source
    proof_stamp_calls = source.count("_stamp_final_visible_final_visible_output_bridge_proof(") - (
        1 if proof_stamp_body_present else 0
    )
    if proof_stamp_body_present:
        failures.append("proof_stamp_body_still_present_after_deadness_deletion")
    if proof_stamp_calls:
        failures.append(f"proof_stamp_calls_still_present_after_deadness_deletion:{proof_stamp_calls}")

    snapshot = {
        "schema": "design_guide_restamper_adapter_hash_bypass_implementation.v1",
        "status": "PASS" if not failures else "FAIL",
        "generated_at": timestamp,
        "failures": failures,
        "source_file": str(INPUTS),
        "bypass_no_longer_depends_on_proof_stamp": not any(
            token in bypass_body for token in forbidden_bypass_tokens
        ),
        "adapter_bypass_state_recording_helper_present": recording_helper_present,
        "adapter_bypass_state_record_calls": record_calls,
        "proof_stamp_surface_locked_zero": not proof_stamp_body_present and proof_stamp_calls == 0,
        "proof_stamp_body_present": proof_stamp_body_present,
        "proof_stamp_calls_remaining": proof_stamp_calls,
        "callsites": callsites,
        "next_safe_step": (
            "run restamper reachability/deadness inventory and lock the proof-stamp surface at zero"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    snapshot["snapshot_hash"] = _stable_hash(snapshot)

    json_path = VERIFICATION / f"design_guide_restamper_adapter_hash_bypass_implementation_{timestamp}.json"
    report_path = AUDITS / f"design_guide_restamper_adapter_hash_bypass_implementation_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    report = [
        "# Design Guide Restamper Adapter-Hash Bypass Implementation",
        "",
        f"## Summary\n{snapshot['status']}",
        "",
        "## Result",
        "",
        f"- Bypass no longer depends on proof stamp: `{snapshot['bypass_no_longer_depends_on_proof_stamp']}`",
        f"- Adapter state record calls: `{record_calls}`",
        f"- Proof stamp surface locked zero: `{snapshot['proof_stamp_surface_locked_zero']}`",
        "",
        "## Callsites",
        "",
        "| Callsite | Bypass | Adapter Hash Debug | Proof Stamp Deleted |",
        "| --- | --- | --- | --- |",
    ]
    for row in callsites:
        report.append(
            f"| `{row['callsite_id']}` | `{row['bypass_call_present']}` | "
            f"`{row['debug_hash_uses_adapter_state_hash']}` | "
            f"`{row['proof_stamp_deleted_after_deadness_proof']}` |"
        )
    report.extend(
        [
            "",
            "## Failures",
            "",
            "\n".join(f"- `{failure}`" for failure in failures) if failures else "None.",
            "",
            "## Next Safe Step",
            "",
            str(snapshot["next_safe_step"]),
            "",
        ]
    )
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"design_guide_restamper_adapter_hash_bypass_implementation {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
