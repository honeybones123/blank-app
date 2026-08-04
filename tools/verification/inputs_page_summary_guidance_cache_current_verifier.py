from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_source(source: str, name: str) -> tuple[str, int]:
    tree = ast.parse(source)
    matches: list[tuple[int, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            matches.append((node.end_lineno - node.lineno + 1, node.lineno, node.end_lineno))
    if not matches:
        return "", 0
    size, start, end = max(matches, key=lambda item: item[0])
    lines = source.splitlines()
    return "\n".join(lines[start - 1 : end]), size


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_summary_guidance_cache_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_summary_guidance_cache_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_summary_guidance_cache_current_coordinator",
    )
    render_inputs_source, render_inputs_size = _function_source(source, "render_inputs")
    summary_pipeline_source, _ = _function_source(
        source,
        "render_inputs_summary_pipeline_current_coordinator",
    )
    summary_owner_source = summary_pipeline_source or render_inputs_source

    failures: list[str] = []
    if not coordinator_source:
        failures.append("summary_guidance_cache_coordinator_missing")
    if coordinator_size > 45:
        failures.append(f"summary_guidance_cache_coordinator_too_large:{coordinator_size}")

    for required in [
        "DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY",
        "DESIGN_GUIDE_SIMPLE_CACHE_FP_KEY",
        "_get_design_guide_fp(summary_state)",
        "_get_cached_design_guide_guidance(_summary_fp)",
        "if not _summary_guidance_cache_hit:",
        "_compute_design_guidance_items(",
        "guidance_debug_verbose=False",
        "debug_enabled=False",
        'summary_guidance_items = list(_summary_guidance_payload.get("guidance_items") or [])',
        '_sum_dbg["design_guide_render_state_source"] = "lightweight_overlay_state"',
        "_set_cached_design_guide_guidance(",
        'summary_state_debug["design_guide_render_state_source"] = "lightweight_overlay_state"',
        'governing_check = summary_guidance_items[0].get("check_key") if summary_guidance_items else None',
        "return summary_guidance_items, governing_check",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")

    call_text = "render_inputs_summary_guidance_cache_current_coordinator("
    if call_text not in summary_owner_source:
        failures.append("render_inputs_missing_summary_guidance_cache_call")

    for stale in [
        "DESIGN_GUIDE_SIMPLE_CACHE_ITEMS_KEY not in st.session_state",
        "_summary_fp = _get_design_guide_fp(summary_state)",
        "_summary_guidance_cache_hit",
        "_summary_guidance_payload = _compute_design_guidance_items",
        "_set_cached_design_guide_guidance(",
        "governing_check = summary_guidance_items[0].get(\"check_key\")",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    display_index = summary_owner_source.find("render_inputs_summary_display_state_current_coordinator(")
    guidance_index = summary_owner_source.find(call_text)
    status_helper_index = summary_owner_source.find("render_inputs_summary_row_finalization_current_coordinator(")
    row_finalization_index = summary_owner_source.find("render_inputs_summary_row_finalization_current_coordinator(")
    summary_render_index = summary_owner_source.find("render_inputs_summary_container_current_coordinator(")
    if not (0 <= display_index < guidance_index < row_finalization_index < summary_render_index):
        failures.append(
            "summary_guidance_cache_call_order_changed:"
            f"display={display_index}:guidance={guidance_index}:"
            f"row_finalization_boundary={status_helper_index}:row_finalization={row_finalization_index}:"
            f"summary_render={summary_render_index}"
        )

    payload = {
        "verifier": "inputs_page_summary_guidance_cache_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "render_inputs_size": render_inputs_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Summary Guidance Cache Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Render inputs size: `{render_inputs_size}`",
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
