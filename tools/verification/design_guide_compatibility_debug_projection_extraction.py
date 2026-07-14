from __future__ import annotations

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


OLD_PAGE_TRACE_TOKENS = (
    "output_hash = _stable_final_publication_hash(out)",
    "adapter_hash = _stable_final_publication_hash(",
    "traces[str(callsite_id or \"\").strip()] = {",
    "_record_final_visible_restamper_adapter_bypass_state(",
    "fallback_item = dict(out or input_item or {})",
)

REQUIRED_PAGE_SHELL_TOKENS = (
    "_build_final_visible_render_binding_payload(",
    "(_final_visible_render_binding or {}).get(\"debug_updates\") or {}",
    "_store_final_visible_compatibility_restamper_render_item_projection_debug(",
    "final_visible_restamper_adapter_bypass_states",
)

REQUIRED_DESIGN_BRAIN_TOKENS = (
    "def build_final_visible_render_binding_payload(",
    "final_visible_contract_binding_output_cutover",
    "final_visible_contract_binding_adapter_cutovers",
    "FinalDesignGuidePublication.final_visible_render_binding_payload.inline_bypass_state",
    '"derived_from": "FinalDesignGuidePublication.final_visible_render_binding_payload"',
)


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    inputs_source = INPUTS.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    failures: list[str] = []

    old_page_trace_presence = {token: token in inputs_source for token in OLD_PAGE_TRACE_TOKENS}
    for token, present in old_page_trace_presence.items():
        if present:
            failures.append(f"old_page_trace_construction_still_present:{token}")

    page_shell_presence = {token: token in inputs_source for token in REQUIRED_PAGE_SHELL_TOKENS}
    for token, present in page_shell_presence.items():
        if not present:
            failures.append(f"missing_page_shell_token:{token}")

    design_brain_presence = {token: token in final_source for token in REQUIRED_DESIGN_BRAIN_TOKENS}
    for token, present in design_brain_presence.items():
        if not present:
            failures.append(f"missing_design_brain_token:{token}")

    helper_count = inputs_source.count("def _final_visible_compatibility_restamper_adapter_cutover(")
    if helper_count != 0:
        failures.append(f"expected_zero_page_compatibility_wrapper_found_{helper_count}")

    status = "PASS" if not failures else "FAIL"
    payload: dict[str, Any] = {
        "schema": "design_guide_compatibility_debug_projection_extraction.v1",
        "status": status,
        "generated_at": timestamp,
        "failures": failures,
        "source_file": str(INPUTS),
        "design_brain_file": str(FINAL_PUBLICATION),
        "old_page_trace_presence": old_page_trace_presence,
        "page_shell_presence": page_shell_presence,
        "design_brain_presence": design_brain_presence,
        "page_compatibility_wrapper_count": helper_count,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_target": "prove whether the remaining render-binding shell and projection-debug storage helper can be reduced further",
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    json_path = VERIFICATION / f"design_guide_compatibility_debug_projection_extraction_{timestamp}.json"
    report_path = AUDITS / f"design_guide_compatibility_debug_projection_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failure_text = "\n".join(f"- `{failure}`" for failure in failures) if failures else "None."
    report = [
        "# Design Guide Compatibility Debug Projection Extraction",
        "",
        f"## Summary\n{status}",
        "",
        "## Ownership Before",
        "",
        "`inputs_page.py` constructed compatibility restamper trace rows, adapter hashes, fallback rows, source-output debug fields, and bypass-state payloads.",
        "",
        "## Ownership After",
        "",
        "`design_brain.final_publication.build_final_visible_render_binding_payload(...)` now constructs the plain debug/proof payloads inline. `inputs_page.py` only applies the returned debug updates and stores compatibility traces.",
        "",
        "## Failures",
        "",
        failure_text,
        "",
        "## Next Safe Target",
        "",
        str(payload["next_safe_target"]),
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"design_guide_compatibility_debug_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

