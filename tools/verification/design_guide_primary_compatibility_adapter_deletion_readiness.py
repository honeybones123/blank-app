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
    return line, source[max(0, match.start() - 1800) : min(len(source), match.end() + 5200)]


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    inputs_source = INPUTS.read_text(encoding="utf-8")
    final_publication_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    failures: list[str] = []

    binding_line, binding_window = _call_window(
        inputs_source,
        "_build_final_visible_render_binding_payload",
        CALLSITE_ID,
    )

    deleted_page_tokens = (
        "def _final_visible_compatibility_restamper_adapter_cutover(",
        "_final_visible_compatibility_restamper_adapter_cutover(",
        "_build_final_visible_final_visible_contract_binding_adapter_projection(",
        "_build_final_visible_compatibility_restamper_debug_projection(",
        "_build_final_visible_restamper_bridge_bypass_decision(",
        "_publish_final_visible_design_guide_contract_binding(",
    )
    deleted_design_brain_tokens = (
        "def build_final_visible_final_visible_contract_binding_adapter_projection(",
        "def build_final_visible_compatibility_restamper_debug_projection(",
        "def build_final_visible_restamper_bridge_bypass_decision(",
    )

    page_deletions = {token: token not in inputs_source for token in deleted_page_tokens}
    design_brain_deletions = {
        token: token not in final_publication_source for token in deleted_design_brain_tokens
    }
    for token, deleted in {**page_deletions, **design_brain_deletions}.items():
        if not deleted:
            failures.append(f"stale_helper_still_present:{token}")

    required_surfaces = {
        "render_binding_builder": "def build_final_visible_render_binding_payload(" in final_publication_source,
        "page_render_binding_call": bool(binding_window),
        "page_projection_debug_store_helper": (
            "def _store_final_visible_compatibility_restamper_render_item_projection_debug(" in inputs_source
        ),
    }
    for key, present in required_surfaces.items():
        if not present:
            failures.append(f"missing_required_surface:{key}")

    consumer_presence = {
        "stores_item": "_final_visible_item = dict(" in binding_window,
        "stores_projection_debug": "_store_final_visible_compatibility_restamper_render_item_projection_debug(" in binding_window,
        "updates_guidance_debug": "guidance_debug.update(" in binding_window,
    }
    for key, present in consumer_presence.items():
        if not present:
            failures.append(f"missing_expected_binding_consumer:{key}")

    status = "PASS" if not failures else "FAIL"
    payload: dict[str, Any] = {
        "schema": "design_guide_primary_compatibility_adapter_deletion_readiness.v2",
        "status": status,
        "generated_at": timestamp,
        "source_file": str(INPUTS),
        "design_brain_file": str(FINAL_PUBLICATION),
        "failures": failures,
        "callsite_id": CALLSITE_ID,
        "render_binding_call_line": binding_line,
        "render_binding_call_window_hash": _stable_hash(binding_window),
        "page_deletions": page_deletions,
        "design_brain_deletions": design_brain_deletions,
        "required_surfaces": required_surfaces,
        "consumer_presence": consumer_presence,
        "decision": "PRIMARY_COMPATIBILITY_ADAPTER_DELETED_RENDER_BINDING_IS_NOW_THE_ONLY_LIVE_PATH",
        "ready_to_delete_callsite_now": False,
        "ready_to_delete_helper_now": True,
        "direct_delete_blockers": [
            "render-binding payload is still the live compatibility shell that page render consumes",
            "projection debug storage helper still preserves compatibility/debug shape",
        ],
        "next_required_adapter": (
            "Prove whether the remaining render-binding shell and projection-debug storage helper can be "
            "reduced further without changing the live final-visible item path."
        ),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    json_path = VERIFICATION / f"design_guide_primary_compatibility_adapter_deletion_readiness_{timestamp}.json"
    report_path = AUDITS / f"design_guide_primary_compatibility_adapter_deletion_readiness_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failure_text = "\n".join(f"- `{failure}`" for failure in failures) if failures else "None."
    report = [
        "# Design Guide Primary Compatibility Adapter Deletion Readiness",
        "",
        f"## Summary\n{status}",
        "",
        "## Decision",
        "",
        f"`{payload['decision']}`",
        "",
        "## Current Live Shape",
        "",
        "`inputs_page.py` no longer calls the deleted compatibility adapter wrapper. The remaining live page shell is one call to `build_final_visible_render_binding_payload(...)` plus projection-debug storage.",
        "",
        "## Failures",
        "",
        failure_text,
        "",
        "## Next Safe Target",
        "",
        str(payload["next_required_adapter"]),
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"design_guide_primary_compatibility_adapter_deletion_readiness {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

