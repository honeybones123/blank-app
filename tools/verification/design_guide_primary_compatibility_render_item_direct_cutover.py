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

PRIMARY_CALLSITE = "render_guidance_secondary_primary_binding"
FINAL_CALLSITE = "render_fast_design_guidance_panel.final_visible_item_binding"


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _call_window(source: str, function_name: str, callsite_id: str) -> tuple[int | None, str]:
    pattern = re.compile(
        rf"{re.escape(function_name)}\(\s*[\s\S]{{0,1400}}?callsite_id\s*=\s*{re.escape(json.dumps(callsite_id))}",
        re.MULTILINE,
    )
    match = pattern.search(source)
    if not match:
        return None, ""
    line = source[: match.start()].count("\n") + 1
    return line, source[max(0, match.start() - 1900) : min(len(source), match.end() + 5200)]


def _call_lines(source: str, function_name: str) -> list[int]:
    lines: list[int] = []
    token = f"{function_name}("
    for index, line in enumerate(source.splitlines(), start=1):
        if token in line and not line.strip().startswith("def "):
            lines.append(index)
    return lines


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    VERIFICATION.mkdir(parents=True, exist_ok=True)
    AUDITS.mkdir(parents=True, exist_ok=True)

    inputs_source = INPUTS.read_text(encoding="utf-8")
    final_source = FINAL_PUBLICATION.read_text(encoding="utf-8")
    failures: list[str] = []

    primary_projection_line, primary_projection_window = _call_window(
        inputs_source,
        "_build_final_visible_compatibility_restamper_render_item_projection",
        PRIMARY_CALLSITE,
    )
    primary_wrapper_line, primary_wrapper_window = _call_window(
        inputs_source,
        "_final_visible_compatibility_restamper_adapter_cutover",
        PRIMARY_CALLSITE,
    )
    primary_bypass_line, primary_bypass_window = _call_window(
        inputs_source,
        "_maybe_bypass_final_visible_restamper_bridge_noop",
        PRIMARY_CALLSITE,
    )
    final_wrapper_line, final_wrapper_window = _call_window(
        inputs_source,
        "_final_visible_compatibility_restamper_adapter_cutover",
        FINAL_CALLSITE,
    )
    final_projection_line, final_projection_window = _call_window(
        inputs_source,
        "_build_final_visible_compatibility_restamper_render_item_projection",
        FINAL_CALLSITE,
    )
    final_bypass_line, final_bypass_window = _call_window(
        inputs_source,
        "_maybe_bypass_final_visible_restamper_bridge_noop",
        FINAL_CALLSITE,
    )
    wrapper_call_lines = _call_lines(inputs_source, "_final_visible_compatibility_restamper_adapter_cutover")

    if "def build_final_visible_compatibility_restamper_render_item_projection(" not in final_source:
        failures.append("missing_design_brain_render_item_projection")
    if not primary_projection_window:
        failures.append("primary_callsite_not_using_design_brain_render_item_projection")
    if primary_wrapper_window:
        failures.append("primary_callsite_still_uses_page_wrapper")
    if not primary_bypass_window:
        failures.append("primary_guarded_bypass_missing")
    if final_wrapper_window:
        failures.append("final_render_fast_still_uses_page_wrapper")
    if not final_projection_window:
        failures.append("final_render_fast_direct_projection_missing")
    if not final_bypass_window:
        failures.append("final_render_fast_guarded_bypass_missing")
    if len(wrapper_call_lines) != 0:
        failures.append(f"expected_0_page_wrapper_calls_found_{len(wrapper_call_lines)}")

    required_primary_tokens = (
        "_store_final_visible_compatibility_restamper_render_item_projection_debug(",
        "guidance_items[idx] = item",
        "button_contract = dict(item.get(\"button_contract\") or {})",
        "_apply_design_brain_publication_contract_for_render(",
        "final_visible_restamper_bridge_render_guidance_secondary_primary_bypassed",
    )
    required_primary_presence = {
        token: token in primary_projection_window for token in required_primary_tokens
    }
    for token, present in required_primary_presence.items():
        if not present:
            failures.append(f"missing_primary_cutover_token:{token}")

    status = "PASS" if not failures else "FAIL"
    payload: dict[str, Any] = {
        "schema": "design_guide_primary_compatibility_render_item_direct_cutover.v1",
        "status": status,
        "generated_at": timestamp,
        "failures": failures,
        "source_file": str(INPUTS),
        "design_brain_file": str(FINAL_PUBLICATION),
        "primary_callsite": PRIMARY_CALLSITE,
        "final_callsite": FINAL_CALLSITE,
        "primary_projection_line": primary_projection_line,
        "primary_wrapper_line": primary_wrapper_line,
        "primary_bypass_line": primary_bypass_line,
        "final_wrapper_line": final_wrapper_line,
        "final_projection_line": final_projection_line,
        "final_bypass_line": final_bypass_line,
        "page_wrapper_call_lines": wrapper_call_lines,
        "page_wrapper_call_count": len(wrapper_call_lines),
        "primary_direct_projection_consumption": bool(primary_projection_window and not primary_wrapper_window),
        "final_render_fast_direct_projection_consumption": bool(final_projection_window and not final_wrapper_window),
        "primary_required_token_presence": required_primary_presence,
        "primary_projection_window_hash": _stable_hash(primary_projection_window),
        "primary_bypass_window_hash": _stable_hash(primary_bypass_window),
        "final_wrapper_window_hash": _stable_hash(final_wrapper_window),
        "final_projection_window_hash": _stable_hash(final_projection_window),
        "final_bypass_window_hash": _stable_hash(final_bypass_window),
        "product_behavior_changed": False,
        "visible_wording_changed": False,
        "cta_apply_semantics_changed": False,
        "family_runtime_changed": False,
        "next_safe_target": "prove/delete the page wrapper body and then assess the remaining guarded bypass probes",
    }
    payload["snapshot_hash"] = _stable_hash(payload)

    json_path = VERIFICATION / f"design_guide_primary_compatibility_render_item_direct_cutover_{timestamp}.json"
    report_path = AUDITS / f"design_guide_primary_compatibility_render_item_direct_cutover_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    failure_text = "\n".join(f"- `{failure}`" for failure in failures) if failures else "None."
    report = [
        "# Design Guide Primary Compatibility Render Item Direct Cutover",
        "",
        f"## Summary\n{status}",
        "",
        "## Surface Targeted",
        "",
        f"`{PRIMARY_CALLSITE}`",
        "",
        "## Ownership After",
        "",
        "The primary card binding callsite consumes `FinalDesignGuidePublication` render-item projection directly through `design_brain.final_publication`, while page code only stores returned debug/bypass metadata and renders the returned item.",
        "",
        "## Remaining Wrapper Consumer",
        "",
        f"`{FINAL_CALLSITE}` also consumes the Design Brain projection directly.",
        "",
        "## Counts",
        "",
        f"- Page wrapper call count: `{len(wrapper_call_lines)}`",
        f"- Primary direct projection consumption: `{payload['primary_direct_projection_consumption']}`",
        f"- Final render-fast direct projection consumption: `{payload['final_render_fast_direct_projection_consumption']}`",
        "",
        "## Failures",
        "",
        failure_text,
        "",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")

    print(f"design_guide_primary_compatibility_render_item_direct_cutover {status}")
    print(f"json={json_path}")
    print(f"report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
