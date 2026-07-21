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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_debug_bundle_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_debug_bundle_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_design_guide_debug_bundle_current_coordinator",
    )
    legacy_source, legacy_size = _function_source(source, "_render_fast_design_guidance_panel")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("debug_bundle_current_coordinator_missing")
    if coordinator_size > 70:
        failures.append(f"debug_bundle_current_coordinator_too_large:{coordinator_size}")
    for required in [
        "resolved_guidance_actions = _debug_resolved_guidance_actions(current_state)",
        "efficiency_state = guidance_debug.get(\"efficiency_tightening_state\") or {}",
        "if sidebar_debug:",
        "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = render_design_guide_debug_bundle_payload_current_coordinator(",
        "resolved_guidance_actions=resolved_guidance_actions",
        "mode_mt=mode_mt",
        "bottom_bt=bottom_bt",
        "\"efficiency_state\": dict(efficiency_state or {})",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    payload_source, payload_size = _function_source(
        source,
        "render_design_guide_debug_bundle_payload_current_coordinator",
    )
    if not payload_source:
        failures.append("debug_bundle_payload_current_coordinator_missing")
    if payload_size > 360:
        failures.append(f"debug_bundle_payload_current_coordinator_too_large:{payload_size}")
    for required in [
        "render_design_guide_debug_bundle_context_current_coordinator(",
        "return {",
        "\"manual_resolver_lock_check\"",
        "\"optimisation_normalized_link_state\"",
        "\"design_guide_engine_decision\"",
        "\"post_apply_display_truth\"",
    ]:
        if required not in payload_source:
            failures.append(f"payload_missing_{required}")
    for required in [
        "render_design_guide_debug_bundle_current_coordinator(",
        "current_state=current_state",
        "guidance_debug=guidance_debug",
        "guidance_items=guidance_items",
        "guidance_disp_state=guidance_disp_state",
        "terminal_state=terminal_state",
        "render_plan=render_plan",
        "sidebar_debug=sidebar_debug",
        "guidance_compute_ms=guidance_compute_ms",
        "guidance_cache_hit=guidance_cache_hit",
        "guidance_dedupe_meta=guidance_dedupe_meta",
        "_recommendation_result=_recommendation_result",
        "efficiency_state = dict(_debug_bundle_result.get(\"efficiency_state\") or {})",
    ]:
        if required not in legacy_source:
            failures.append(f"legacy_missing_{required}")
    for stale in [
        "resolved_guidance_actions = _debug_resolved_guidance_actions(current_state)",
        "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = {",
        "optimisation_normalized_link_state = {",
        "post_apply_display_truth = _design_guide_display_truth_for_item(",
        "last_apply_route = dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})",
        "\"manual_resolver_lock_check\": {",
    ]:
        if stale in legacy_source:
            failures.append(f"legacy_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_debug_bundle_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "legacy_size": legacy_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Debug Bundle Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Legacy coordinator size: `{legacy_size}`",
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
