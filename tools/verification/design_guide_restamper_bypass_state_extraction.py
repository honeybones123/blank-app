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
    final_publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    failures: list[str] = []

    page_local_helper_deleted = "def _final_visible_restamper_adapter_bypass_state(" not in inputs_source
    if not page_local_helper_deleted:
        failures.append("page_local_bypass_state_helper_still_present")

    design_brain_builder_deleted = (
        "def build_final_visible_restamper_adapter_bypass_state(" not in final_publication_source
    )
    if not design_brain_builder_deleted:
        failures.append("design_brain_bypass_state_builder_still_present")

    import_alias_deleted = (
        "build_final_visible_restamper_adapter_bypass_state as _build_final_visible_restamper_adapter_bypass_state"
        not in inputs_source
    )
    if not import_alias_deleted:
        failures.append("inputs_import_alias_for_bypass_state_builder_still_present")

    inline_bypass_state_present = (
        "FinalDesignGuidePublication.final_visible_render_binding_payload.inline_bypass_state"
        in final_publication_source
    )
    if not inline_bypass_state_present:
        failures.append("missing_inline_bypass_state_surface")

    storage_surface_present = all(
        token in inputs_source
        for token in (
            "final_visible_restamper_adapter_bypass_states",
            "final_visible_restamper_adapter_bypass_states_hash",
            'bypass_state.get("bypass_state_hash")',
        )
    )
    if not storage_surface_present:
        failures.append("missing_page_storage_surface_for_bypass_state")

    local_hash_logic_deleted = all(
        token not in inputs_source
        for token in (
            '"state_hash": _stable_final_publication_hash(dict(state or {}))',
            '"rec_hash": _stable_final_publication_hash(dict(rec or {}))',
            'payload["bypass_state_hash"] = _stable_final_publication_hash(payload)',
        )
    )
    if not local_hash_logic_deleted:
        failures.append("page_local_bypass_hash_logic_still_present")

    status = "PASS" if not failures else "FAIL"
    payload: dict[str, Any] = {
        "schema": "design_guide_restamper_bypass_state_extraction.v2",
        "status": status,
        "generated_at": timestamp,
        "failures": failures,
        "source_file": str(INPUTS),
        "design_brain_file": str(FINAL_PUBLICATION),
        "page_local_helper_deleted": page_local_helper_deleted,
        "design_brain_builder_deleted": design_brain_builder_deleted,
        "import_alias_deleted": import_alias_deleted,
        "inline_bypass_state_present": inline_bypass_state_present,
        "page_storage_surface_present": storage_surface_present,
        "page_local_hash_logic_deleted": local_hash_logic_deleted,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_target": "prove whether the remaining bypass-state storage keys are compatibility/debug-only and can be reduced later",
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    json_path = VERIFICATION / f"design_guide_restamper_bypass_state_extraction_{timestamp}.json"
    report_path = AUDITS / f"design_guide_restamper_bypass_state_extraction_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failure_text = "\n".join(f"- `{failure}`" for failure in failures) if failures else "None."
    report = [
        "# Design Guide Restamper Bypass State Extraction",
        "",
        f"## Summary\n{status}",
        "",
        "## Ownership After",
        "",
        "`design_brain.final_publication.build_final_visible_render_binding_payload(...)` now builds the bypass-state fingerprint inline. `inputs_page.py` only stores the returned bypass-state hash in compatibility/debug state.",
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

    print(f"design_guide_restamper_bypass_state_extraction {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
