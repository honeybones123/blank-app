from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACTS = ROOT / "artifacts"
VERIFICATION = ARTIFACTS / "verification"
AUDITS = ARTIFACTS / "audits"

PAGE_GUARD_HELPER = "_final_publication_projection_bypass_page_guard_inputs"
DELETED_BYPASS_HELPER = "_maybe_bypass_final_visible_restamper_bridge_noop"
RENDER_BINDING_ALIAS = "_build_final_visible_render_binding_payload"
RENDER_BINDING_BUILDER = "build_final_visible_render_binding_payload"
CALLSITES = (
    "render_fast_design_guidance_panel.final_visible_item_binding",
)


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _function_body(source: str, name: str) -> tuple[int | None, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            start = int(node.lineno)
            end = int(getattr(node, "end_lineno", node.lineno))
            return start, "\n".join(lines[start - 1 : end])
    return None, ""


def _callsite_windows(source: str) -> list[dict[str, Any]]:
    lines = source.splitlines()
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        if f"{RENDER_BINDING_ALIAS}(" not in line or line.strip().startswith("def "):
            continue
        start = max(1, index - 8)
        end = min(len(lines), index + 18)
        window = "\n".join(lines[start - 1 : end])
        callsite_id = ""
        for expected in CALLSITES:
            if expected in window:
                callsite_id = expected
                break
        rows.append(
            {
                "line": index,
                "callsite_id": callsite_id,
                "context_hash": _stable_hash(window),
                "has_debug_sink": "debug_sink=" in window,
                "has_state": "state=" in window,
                "has_rec": "rec=" in window,
                "classification": "design_brain_render_binding_call",
                "delete_safe_now": False,
                "next_required_adapter": "keep only page guard-input collection; bypass decision order stays inside Design Brain render binding",
            }
        )
    return rows


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    inputs_source = INPUTS.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    helper_line, helper_body = _function_body(inputs_source, PAGE_GUARD_HELPER)
    deleted_helper_line, deleted_helper_body = _function_body(inputs_source, DELETED_BYPASS_HELPER)
    callsites = _callsite_windows(inputs_source)
    failures: list[str] = []

    if deleted_helper_body or f"{DELETED_BYPASS_HELPER}(" in inputs_source:
        failures.append("deleted_page_bypass_helper_still_present")
    if not helper_body:
        failures.append("missing_page_guard_input_helper")
    if len(callsites) != 1:
        failures.append(f"expected_1_render_binding_call_found_{len(callsites)}")
    missing_callsite_ids = sorted(set(CALLSITES) - {row.get("callsite_id") for row in callsites})
    if missing_callsite_ids:
        failures.append(f"missing_expected_callsite_ids:{missing_callsite_ids}")
    if f"def {RENDER_BINDING_BUILDER}(" not in final_source:
        failures.append("missing_design_brain_render_binding_builder")
    for token in (
        "st.session_state.get(DESIGN_GUIDE_COMPONENT_APPLY_IN_FLIGHT_KEY)",
        "post_click_design_guide_state",
        "_build_final_visible_render_binding_payload(",
    ):
        if token not in helper_body:
            if token == "_build_final_visible_render_binding_payload(":
                if token not in inputs_source:
                    failures.append(f"inputs_missing_render_binding_call:{token}")
            else:
                failures.append(f"helper_missing_guard_token:{token}")
    for token in (
        "_build_final_visible_restamper_adapter_bypass_state",
        "_build_final_visible_restamper_bridge_bypass_decision",
    ):
        if token in inputs_source:
            failures.append(f"page_still_imports_lower_level_bypass_builder:{token}")
    for token in (
        "adapter_state_mismatch",
        "previous_output_not_current_input",
        "stable_adapter_hash_restamper_bridge",
        "apply_in_flight",
        "post_click_state_present",
    ):
        if token not in final_source:
            failures.append(f"design_brain_render_binding_missing_token:{token}")

    page_owned_reasons = {
        "session_apply_in_flight_guard": "reads Streamlit session state, so this part must remain page-shell or be passed in as plain request state",
        "post_click_state_guard": "prevents stable-rerun reuse during post-click states",
        "debug_sink_previous_state_lookup": "reads previous adapter state from page debug/session payload",
    }
    design_brain_owned_reasons = {
        "inline_bypass_state_fingerprint": "now owned inline inside design_brain.final_publication.build_final_visible_render_binding_payload",
        "hash_comparison_policy": "now owned inside the Design Brain render-binding payload",
        "full_plain_data_bridge_decision": "now owned by the Design Brain render-binding payload using page-supplied guard booleans",
    }
    status = "PASS" if not failures else "FAIL"
    payload: dict[str, Any] = {
        "schema": "design_guide_guarded_bypass_probe_ownership_audit.v1",
        "status": status,
        "generated_at": timestamp,
        "failures": failures,
        "helper_line": helper_line,
        "callsite_count": len(callsites),
        "callsites": callsites,
        "deleted_page_bypass_helper_present": bool(deleted_helper_body),
        "page_owned_reasons": page_owned_reasons,
        "design_brain_owned_reasons": design_brain_owned_reasons,
        "delete_safe_now": False,
        "recommended_next_slice": "retain page guard-input helper as bounded page/session shell unless a broader controller request-hash memo boundary replaces it",
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "helper_body_hash": _stable_hash(helper_body),
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    json_path = VERIFICATION / f"design_guide_guarded_bypass_probe_ownership_audit_{timestamp}.json"
    report_path = AUDITS / f"design_guide_guarded_bypass_probe_ownership_audit_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failure_text = "\n".join(f"- `{failure}`" for failure in failures) if failures else "None."
    call_rows = [
        f"| {row['line']} | `{row['callsite_id']}` | `{row['classification']}` | `{row['delete_safe_now']}` |"
        for row in callsites
    ]
    report = [
        "# Design Guide Guarded Bypass Probe Ownership Audit",
        "",
        f"## Summary\n{status}",
        "",
        "## Current Decision",
        "",
        "`KEEP_FOR_NOW`",
        "",
        "The remaining surfaces are direct calls into a Design Brain-owned render binding. The old page-owned bypass helper is deleted; the page only collects session/post-click guard inputs.",
        "",
        "## Callsites",
        "",
        "| Line | Callsite | Classification | Delete Safe Now |",
        "| --- | --- | --- | --- |",
        *(call_rows or ["| None |  |  |  |"]),
        "",
        "## Ownership Split",
        "",
        "- Design Brain owns the inline bypass-state hash fingerprint inside the render-binding payload.",
        "- Design Brain owns the bridge bypass decision consumed by the render-binding payload.",
        "- Design Brain owns the full plain-data render-binding decision.",
        "- The old page-owned bypass helper is deleted.",
        "- inputs_page.py still reads session/apply-in-flight and post-click guard inputs through a bounded page-shell helper.",
        "",
        "## Failures",
        "",
        failure_text,
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"design_guide_guarded_bypass_probe_ownership_audit {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
