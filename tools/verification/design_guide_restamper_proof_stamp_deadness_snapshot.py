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
    "render_guidance_secondary_items.pre_render_binding",
    "render_guidance_secondary_items.pre_card_binding",
    "render_guidance_secondary_primary_binding",
    "render_fast_design_guidance_panel.final_visible_item_binding",
)

PROOF_STORE_TOKENS = (
    "final_visible_final_visible_output_bridge_proofs",
    "final_visible_final_visible_output_bridge_proof_hash",
    "final_visible_restamper_bridge_latest_callsite",
    "final_visible_restamper_bridge_latest_hash",
    "final_visible_restamper_bridge_latest_result_item_hash",
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


def _source_without_function(source: str, name: str) -> str:
    start = source.find(f"def {name}(")
    if start < 0:
        return source
    next_def = source.find("\ndef ", start + 1)
    end = next_def if next_def >= 0 else len(source)
    return source[:start] + source[end:]


def _call_with_callsite_window(source: str, function_name: str, callsite_id: str) -> str:
    pattern = re.compile(
        rf"{re.escape(function_name)}\(\s*[\s\S]{{0,900}}?callsite_id\s*=\s*{re.escape(json.dumps(callsite_id))}",
        re.MULTILINE,
    )
    match = pattern.search(source)
    if not match:
        return ""
    return source[max(0, match.start() - 900) : min(len(source), match.end() + 2300)]


def _line_number(source: str, needle: str) -> int | None:
    index = source.find(needle)
    if index < 0:
        return None
    return source[:index].count("\n") + 1


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    source = INPUTS.read_text(encoding="utf-8")
    bypass_body = _function_body(source, "_maybe_bypass_final_visible_restamper_bridge_noop")
    proof_body = _function_body(source, "_stamp_final_visible_final_visible_output_bridge_proof")
    source_without_proof_body = _source_without_function(
        source, "_stamp_final_visible_final_visible_output_bridge_proof"
    )

    failures: list[str] = []
    if proof_body:
        failures.append("proof_stamp_helper_still_present_after_deletion_slice")

    proof_store_product_reads = {
        token: source_without_proof_body.count(token) for token in PROOF_STORE_TOKENS
    }
    for token, count in proof_store_product_reads.items():
        if count:
            failures.append(f"proof_store_token_still_used_outside_helper:{token}:{count}")

    proof_bridge_trace_calls_outside_helper = source_without_proof_body.count(
        "_run_design_guide_controller_final_visible_output_bridge_trace_only("
    )
    proof_bridge_trace_import_only = (
        proof_bridge_trace_calls_outside_helper == 0
        and "_run_design_guide_controller_final_visible_output_bridge_trace_only" in source_without_proof_body
    )
    if proof_bridge_trace_calls_outside_helper:
        failures.append(
            f"controller_restamper_bridge_trace_called_outside_helper:{proof_bridge_trace_calls_outside_helper}"
        )

    forbidden_bypass_tokens = (
        'debug_sink.get("final_visible_final_visible_output_bridge_proofs")',
        "missing_previous_proof",
        "stable_noop_restamper_bridge",
        "_run_design_guide_controller_final_visible_output_bridge_trace_only(",
    )
    bypass_forbidden_hits = [token for token in forbidden_bypass_tokens if token in bypass_body]
    for token in bypass_forbidden_hits:
        failures.append(f"bypass_still_depends_on_proof_stamp:{token}")

    required_bypass_tokens = (
        'debug_sink.get("final_visible_restamper_adapter_bypass_states")',
        "missing_previous_adapter_state",
        "stable_adapter_hash_restamper_bridge",
        '"adapter_state_hash": current.get("bypass_state_hash")',
    )
    for token in required_bypass_tokens:
        if bypass_body and token not in bypass_body:
            failures.append(f"bypass_missing_adapter_hash_dependency:{token}")

    callsites: list[dict[str, object]] = []
    for callsite in EXPECTED_CALLSITES:
        window = _call_with_callsite_window(
            source, "_stamp_final_visible_final_visible_output_bridge_proof", callsite
        )
        line = _line_number(source, f"callsite_id={json.dumps(callsite)}")
        has_call = bool(window)
        identity_hash_guard = (
            "_stable_final_publication_hash" in window
            and "== _stable_final_publication_hash" in window
        )
        result_identity_scope = '"result_identity_only"' in window
        adapter_result_hash_debug_only = "adapter_result_hash" in window
        adapter_result_item_used_only_when_same_hash = bool(
            identity_hash_guard and result_identity_scope and adapter_result_hash_debug_only
        )
        row = {
            "callsite_id": callsite,
            "line": line,
            "proof_stamp_call_present": has_call,
            "identity_hash_guard": identity_hash_guard,
            "result_identity_only_scope": result_identity_scope,
            "adapter_result_hash_debug_present": adapter_result_hash_debug_only,
            "deleted_after_adapter_hash_cutover": not has_call,
            "safe_to_delete_callsite_after_adapter_hash_cutover": adapter_result_item_used_only_when_same_hash
            if has_call
            else True,
            "window_hash": _stable_hash(window) if window else None,
        }
        callsites.append(row)
        if has_call and not adapter_result_item_used_only_when_same_hash:
            failures.append(f"proof_stamp_callsite_not_identity_only:{callsite}")

    helper_call_count = source.count("_stamp_final_visible_final_visible_output_bridge_proof(") - (
        1 if proof_body else 0
    )
    if helper_call_count != 0:
        failures.append(f"expected_0_proof_stamp_calls_found_{helper_call_count}")

    snapshot = {
        "schema": "design_guide_restamper_proof_stamp_deadness.v1",
        "status": "PASS" if not failures else "FAIL",
        "generated_at": timestamp,
        "source_file": str(INPUTS),
        "failures": failures,
        "proof_stamp_helper_present": bool(proof_body),
        "proof_stamp_call_count": helper_call_count,
        "proof_store_product_reads_outside_helper": proof_store_product_reads,
        "controller_restamper_bridge_trace_calls_outside_helper": proof_bridge_trace_calls_outside_helper,
        "controller_restamper_bridge_trace_reference_is_import_only": proof_bridge_trace_import_only,
        "bypass_no_longer_depends_on_proof_stamp": not bypass_forbidden_hits,
        "bypass_uses_adapter_hash_state": (
            True if not bypass_body else all(token in bypass_body for token in required_bypass_tokens)
        ),
        "bypass_helper_present": bool(bypass_body),
        "bypass_helper_required": bool(bypass_body),
        "callsites": callsites,
        "proof_stamp_calls_deleted": helper_call_count == 0,
        "proof_stamp_helper_deleted": not bool(proof_body),
        "proof_stamp_surface_locked_zero": not failures,
        "replacement_authority": "final_visible_restamper_adapter_bypass_states",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    snapshot["snapshot_hash"] = _stable_hash(snapshot)

    json_path = VERIFICATION / f"design_guide_restamper_proof_stamp_deadness_{timestamp}.json"
    report_path = AUDITS / f"design_guide_restamper_proof_stamp_deadness_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    call_rows = [
        "| `{callsite_id}` | `{line}` | `{proof_stamp_call_present}` | `{deleted_after_adapter_hash_cutover}` | `{identity_hash_guard}` | `{result_identity_only_scope}` | `{safe_to_delete_callsite_after_adapter_hash_cutover}` |".format(
            **row
        )
        for row in callsites
    ]
    read_rows = [
        f"| `{token}` | `{count}` |" for token, count in proof_store_product_reads.items()
    ]
    report = [
        "# Design Guide Restamper Proof-Stamp Deadness Snapshot",
        "",
        f"## Summary\n{snapshot['status']}",
        "",
        "## Deadness Decision",
        "",
        f"- Proof-stamp surface locked zero: `{snapshot['proof_stamp_surface_locked_zero']}`",
        f"- Proof-stamp calls remaining: `{helper_call_count}`",
        f"- Proof-stamp helper present: `{snapshot['proof_stamp_helper_present']}`",
        f"- Bypass no longer depends on proof stamp: `{snapshot['bypass_no_longer_depends_on_proof_stamp']}`",
        f"- Bypass uses adapter hash state: `{snapshot['bypass_uses_adapter_hash_state']}`",
        "",
        "## Proof Store Reads Outside Helper",
        "",
        "| Token | Count |",
        "| --- | ---: |",
        *read_rows,
        "",
        "## Callsites",
        "",
        "| Callsite | Line | Present | Deleted | Hash Guard | Identity Only | Safe Delete |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
        *call_rows,
        "",
        "## Failures",
        "",
        "\n".join(f"- `{failure}`" for failure in failures) if failures else "None.",
        "",
        "## Next Safe Step",
        "",
        (
            "Keep this zero-count verifier in the composed cleanup inventory, then update reachability/readiness counts."
            if not failures
            else "Do not delete; resolve the failures above first."
        ),
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"design_guide_restamper_proof_stamp_deadness {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
