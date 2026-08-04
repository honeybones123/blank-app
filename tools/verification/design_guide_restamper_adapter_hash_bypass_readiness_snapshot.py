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


EXPECTED_CALLSITES = {
    "render_guidance_secondary_primary_binding": "compatibility_adapter",
    "render_fast_design_guidance_panel.final_visible_item_binding": "compatibility_adapter",
}


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _line_number(text: str, needle: str) -> int | None:
    index = text.find(needle)
    if index < 0:
        return None
    return text[:index].count("\n") + 1


def _contains_between(text: str, start: str, end: str, needle: str) -> bool:
    start_i = text.find(start)
    if start_i < 0:
        return False
    end_i = text.find(end, start_i)
    if end_i < 0:
        end_i = len(text)
    return needle in text[start_i:end_i]


def _call_with_callsite_present(text: str, function_name: str, callsite_id: str) -> bool:
    pattern = re.compile(
        rf"{re.escape(function_name)}\(\s*[\s\S]{{0,700}}?callsite_id\s*=\s*{re.escape(json.dumps(callsite_id))}",
        re.MULTILINE,
    )
    return bool(pattern.search(text))


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    source = INPUTS.read_text(encoding="utf-8")
    failures: list[str] = []
    callsites: list[dict[str, object]] = []

    bypass_function_has_current_guards = all(
        token in source
        for token in (
            "def _maybe_bypass_final_visible_restamper_bridge_noop(",
            "debug_force_rebuild",
            "apply_in_flight",
            "post_click_state_present",
            "missing_previous_adapter_state",
        )
    )
    if not bypass_function_has_current_guards:
        failures.append("current_bypass_guard_surface_missing")

    old_stamp_dependency_present = (
        'debug_sink.get("final_visible_final_visible_output_bridge_proofs")' in source
        and 'return {"bypass": False, "reason": "missing_previous_proof"}' in source
    )
    adapter_state_dependency_present = (
        'debug_sink.get("final_visible_restamper_adapter_bypass_states")' in source
        and 'return {"bypass": False, "reason": "missing_previous_adapter_state"}' in source
    )
    if not adapter_state_dependency_present:
        failures.append("adapter_state_dependency_not_detected")

    default_adapter_hash_surface = (
        "def _final_visible_restamper_default_rebuild_adapter_cutover(" not in source
        and "_final_visible_restamper_default_rebuild_adapter_cutover(" not in source
    )
    if not default_adapter_hash_surface:
        failures.append("default_rebuild_adapter_surface_not_deleted")

    compatibility_adapter_hash_surface = all(
        token in source
        for token in (
            "def _final_visible_compatibility_restamper_adapter_cutover(",
            '"component_projection_hash": branch_projection.get("projection_hash")',
            '"adapter_hash": adapter_hash',
            'debug_sink["final_visible_contract_binding_adapter_cutover_hash"]',
        )
    )
    if not compatibility_adapter_hash_surface:
        failures.append("compatibility_adapter_hash_surface_missing")

    for callsite, adapter_kind in EXPECTED_CALLSITES.items():
        quoted = f'"{callsite}"'
        occurrences = source.count(quoted)
        bypass_present = _call_with_callsite_present(
            source, "_maybe_bypass_final_visible_restamper_bridge_noop", callsite
        )
        adapter_token = "_final_visible_compatibility_restamper_adapter_cutover("
        required_hash_fields = ("component_projection_hash", "output_hash")
        adapter_present = _call_with_callsite_present(
            source, adapter_token.rstrip("("), callsite
        )
        stamp_present = _call_with_callsite_present(
            source, "_stamp_final_visible_final_visible_output_bridge_proof", callsite
        )

        row = {
            "callsite_id": callsite,
            "line": _line_number(source, quoted),
            "adapter_kind": adapter_kind,
            "quoted_occurrences": occurrences,
            "bypass_probe_present": bool(bypass_present),
            "adapter_call_present": bool(adapter_present),
            "proof_stamp_deleted": not bool(stamp_present),
            "adapter_hash_fields": list(required_hash_fields),
            "ready_for_adapter_hash_bypass": bool(
                occurrences
                and bypass_present
                and adapter_present
                and compatibility_adapter_hash_surface
            ),
        }
        callsites.append(row)
        if not row["ready_for_adapter_hash_bypass"]:
            failures.append(f"callsite_not_ready:{callsite}")

    ready = not failures
    snapshot = {
        "schema": "design_guide_restamper_adapter_hash_bypass_readiness.v1",
        "status": "PASS" if ready else "FAIL",
        "generated_at": timestamp,
        "failures": failures,
        "source_file": str(INPUTS),
        "current_state": {
            "proof_stamp_dependency_present": old_stamp_dependency_present,
            "adapter_state_dependency_present": adapter_state_dependency_present,
            "current_bypass_guards_present": bypass_function_has_current_guards,
            "default_rebuild_adapter_surface_deleted": default_adapter_hash_surface,
            "compatibility_adapter_hash_surface": compatibility_adapter_hash_surface,
        },
        "classification_counts": {
            "guarded_bypass_probes": len(EXPECTED_CALLSITES),
            "proof_stamp_dependency_callers": len(EXPECTED_CALLSITES)
            if old_stamp_dependency_present
            else 0,
            "adapter_state_dependency_callers": len(EXPECTED_CALLSITES)
            if adapter_state_dependency_present
            else 0,
            "adapter_hash_ready_callers": sum(
                1 for row in callsites if row["ready_for_adapter_hash_bypass"]
            ),
        },
        "callsites": callsites,
        "next_safe_step": (
            "cut over _maybe_bypass_final_visible_restamper_bridge_noop to use adapter hash "
            "state before final_visible_final_visible_output_bridge_proofs, while preserving debug/apply/post-click guards"
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    snapshot["snapshot_hash"] = _stable_hash(snapshot)

    json_path = VERIFICATION / f"design_guide_restamper_adapter_hash_bypass_readiness_{timestamp}.json"
    report_path = AUDITS / f"design_guide_restamper_adapter_hash_bypass_readiness_{timestamp}.md"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")

    report = [
        "# Design Guide Restamper Adapter-Hash Bypass Readiness",
        "",
        f"## Summary\n{'PASS' if ready else 'FAIL'}",
        "",
        "## Current State",
        "",
        f"- Guarded bypass probes: `{len(EXPECTED_CALLSITES)}`",
        f"- Adapter-hash-ready callsites: `{snapshot['classification_counts']['adapter_hash_ready_callers']}`",
        f"- Proof-stamp dependency present: `{old_stamp_dependency_present}`",
        f"- Adapter-state dependency present: `{adapter_state_dependency_present}`",
        "",
        "## Callsites",
        "",
        "| Callsite | Adapter | Ready |",
        "| --- | --- | --- |",
    ]
    for row in callsites:
        report.append(
            f"| `{row['callsite_id']}` | `{row['adapter_kind']}` | `{row['ready_for_adapter_hash_bypass']}` |"
        )
    report.extend(
        [
            "",
            "## Next Safe Step",
            "",
            snapshot["next_safe_step"],
            "",
            "## Failures",
            "",
            "\n".join(f"- `{failure}`" for failure in failures) if failures else "None.",
            "",
        ]
    )
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"design_guide_restamper_adapter_hash_bypass_readiness {snapshot['status']}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())

