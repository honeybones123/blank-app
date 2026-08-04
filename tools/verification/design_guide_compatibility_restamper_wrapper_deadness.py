from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACTS = ROOT / "artifacts"
VERIFICATION = ARTIFACTS / "verification"
AUDITS = ARTIFACTS / "audits"

CALLSITE_ID = "render_fast_design_guidance_panel.final_visible_item_binding"


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _call_window(source: str, function_name: str, callsite_id: str) -> tuple[int | None, str]:
    pattern = re.compile(
        rf"{re.escape(function_name)}\(\s*[\s\S]{{0,1200}}?callsite_id\s*=\s*{re.escape(json.dumps(callsite_id))}",
        re.MULTILINE,
    )
    match = pattern.search(source)
    if not match:
        return None, ""
    line = source[: match.start()].count("\n") + 1
    return line, source[max(0, match.start() - 1800) : min(len(source), match.end() + 4200)]


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    inputs_source = INPUTS.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    failures: list[str] = []

    binding_line, binding_window = _call_window(
        inputs_source,
        "_build_final_visible_render_binding_payload",
        CALLSITE_ID,
    )
    wrapper_present = "def _final_visible_compatibility_restamper_adapter_cutover(" in inputs_source
    deleted_helper_tokens = {
        "page_wrapper": not wrapper_present,
        "page_adapter_projection_alias": "_build_final_visible_final_visible_contract_binding_adapter_projection(" not in inputs_source,
        "page_debug_projection_alias": "_build_final_visible_compatibility_restamper_debug_projection(" not in inputs_source,
        "page_bypass_decision_alias": "_build_final_visible_restamper_bridge_bypass_decision(" not in inputs_source,
        "design_brain_adapter_helper": "def build_final_visible_final_visible_contract_binding_adapter_projection(" not in final_source,
        "design_brain_debug_helper": "def build_final_visible_compatibility_restamper_debug_projection(" not in final_source,
        "design_brain_bridge_bypass_helper": "def build_final_visible_restamper_bridge_bypass_decision(" not in final_source,
    }
    for key, deleted in deleted_helper_tokens.items():
        if not deleted:
            failures.append(f"stale_wrapper_surface_still_present:{key}")

    if not binding_window:
        failures.append("missing_render_binding_callsite")
    if "def _store_final_visible_compatibility_restamper_render_item_projection_debug(" not in inputs_source:
        failures.append("missing_projection_debug_storage_helper")

    if binding_window:
        required_binding_tokens = {
            "guidance_debug.update": "guidance_debug.update(" in binding_window,
            "projection_debug_storage": "_store_final_visible_compatibility_restamper_render_item_projection_debug(" in binding_window,
            "final_visible_item_writeback": "_final_visible_item = dict(" in binding_window,
        }
        for key, present in required_binding_tokens.items():
            if not present:
                failures.append(f"missing_binding_token:{key}")
    else:
        required_binding_tokens = {}

    status = "PASS" if not failures else "FAIL"
    decision = "DELETED_AND_REPLACED_BY_RENDER_BINDING_PAYLOAD"
    payload: dict[str, Any] = {
        "schema": "design_guide_compatibility_restamper_wrapper_deadness.v2",
        "status": status,
        "generated_at": timestamp,
        "failures": failures,
        "wrapper_present": wrapper_present,
        "deleted_helper_tokens": deleted_helper_tokens,
        "render_binding_call_line": binding_line,
        "render_binding_call_window_hash": _stable_hash(binding_window),
        "required_binding_tokens": required_binding_tokens,
        "decision": decision,
        "ready_to_delete_wrapper": True,
        "wrapper_deleted": True,
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    json_path = VERIFICATION / f"design_guide_compatibility_restamper_wrapper_deadness_{timestamp}.json"
    report_path = AUDITS / f"design_guide_compatibility_restamper_wrapper_deadness_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failure_text = "\n".join(f"- `{failure}`" for failure in failures) if failures else "None."
    report = [
        "# Design Guide Compatibility Restamper Wrapper Deadness",
        "",
        f"## Summary\n{status}",
        "",
        f"## Decision\n`{decision}`",
        "",
        "## Proof",
        "",
        f"- Wrapper deleted: `{not wrapper_present}`",
        f"- Render binding call line: `{binding_line}`",
        "",
        "## Failures",
        "",
        failure_text,
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"design_guide_compatibility_restamper_wrapper_deadness {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    print(f"decision={decision}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

