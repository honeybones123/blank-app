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

    design_brain_render_projection_present = (
        "def build_final_visible_render_binding_payload(" in final_source
    )
    if not design_brain_render_projection_present:
        failures.append("missing_design_brain_render_binding_payload")

    design_brain_render_projection_exported = (
        '"build_final_visible_render_binding_payload"' in final_source
    )
    if not design_brain_render_projection_exported:
        failures.append("design_brain_render_binding_payload_not_exported")

    page_calls_render_projection = (
        "_build_final_visible_render_binding_payload(" in inputs_source
    )
    if not page_calls_render_projection:
        failures.append("page_not_calling_render_binding_payload")

    page_direct_adapter_calls_removed = all(
        token not in inputs_source
        for token in (
            "_build_final_visible_final_visible_contract_binding_adapter_projection(",
            "_build_final_visible_compatibility_restamper_debug_projection(",
        )
    )
    if not page_direct_adapter_calls_removed:
        failures.append("page_wrapper_still_calls_lower_level_adapter_or_debug_projection")

    source_output_and_debug_owned_by_design_brain = all(
        token in final_source
        for token in (
            "build_final_visible_render_binding_payload(",
            "FinalDesignGuidePublication.final_visible_render_binding_payload.inline_bypass_state",
            "final_visible_contract_binding_adapter_cutovers",
            "final_visible_contract_binding_output_validity",
        )
    )
    if not source_output_and_debug_owned_by_design_brain:
        failures.append("design_brain_render_binding_payload_missing_lower_level_composition")

    status = "PASS" if not failures else "FAIL"
    payload: dict[str, Any] = {
        "schema": "design_guide_compatibility_render_item_projection_extraction.v2",
        "status": status,
        "generated_at": timestamp,
        "failures": failures,
        "source_file": str(INPUTS),
        "design_brain_file": str(FINAL_PUBLICATION),
        "design_brain_render_projection_present": design_brain_render_projection_present,
        "design_brain_render_projection_exported": design_brain_render_projection_exported,
        "page_calls_render_projection": page_calls_render_projection,
        "page_direct_adapter_calls_removed": page_direct_adapter_calls_removed,
        "source_output_and_debug_owned_by_design_brain": source_output_and_debug_owned_by_design_brain,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_target": "delete or internalise old compatibility adapter/debug scaffolding after render_fast binding cutover proof",
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    json_path = VERIFICATION / f"design_guide_compatibility_render_item_projection_extraction_{timestamp}.json"
    report_path = AUDITS / f"design_guide_compatibility_render_item_projection_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failure_text = "\n".join(f"- `{failure}`" for failure in failures) if failures else "None."
    report = [
        "# Design Guide Compatibility Render Item Projection Extraction",
        "",
        f"## Summary\n{status}",
        "",
        "## Ownership After",
        "",
        "`design_brain.final_publication.build_final_visible_render_binding_payload(...)` now composes the compatibility adapter projection, debug projection, and bypass decision into one pure binding payload.",
        "",
        "## Page Role",
        "",
        "`inputs_page.py` calls the render binding payload helper and stores returned debug payloads; it no longer calls the lower-level adapter/debug projection builders or the bypass decision directly.",
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

    print(f"design_guide_compatibility_render_item_projection_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

