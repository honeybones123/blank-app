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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_debug_bundle_context_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_debug_bundle_context_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    context_source, context_size = _function_source(
        source,
        "render_design_guide_debug_bundle_context_current_coordinator",
    )
    debug_source, debug_size = _function_source(
        source,
        "render_design_guide_debug_bundle_current_coordinator",
    )
    payload_source, payload_size = _function_source(
        source,
        "render_design_guide_debug_bundle_payload_current_coordinator",
    )

    failures: list[str] = []
    if not context_source:
        failures.append("debug_bundle_context_current_coordinator_missing")
    if context_size > 210:
        failures.append(f"debug_bundle_context_current_coordinator_too_large:{context_size}")
    if debug_size > 70:
        failures.append(f"debug_bundle_current_coordinator_not_reduced:{debug_size}")
    if not payload_source:
        failures.append("debug_bundle_payload_current_coordinator_missing")
    if payload_size > 360:
        failures.append(f"debug_bundle_payload_current_coordinator_too_large:{payload_size}")
    for required in [
        "last_apply_route = dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})",
        "gsum = []",
        "post_apply_display_truth = _design_guide_display_truth_for_item(",
        "displayed_primary_item: dict | None = None",
        "_resolve_recommendation_updates(displayed_primary_item, guidance_disp_state)",
        "_normalise_invalid_shear_state_updates(",
        "\"optimisation_normalized_link_state\"",
        "engine_decision_debug = dict(",
        "\"engine_candidate_search_evidence\": dict(engine_candidate_search_evidence or {})",
    ]:
        if required not in context_source:
            failures.append(f"context_missing_{required}")
    for required in [
        "render_design_guide_debug_bundle_context_current_coordinator(",
        "current_state=current_state",
        "guidance_debug=guidance_debug",
        "guidance_items=guidance_items",
        "guidance_disp_state=guidance_disp_state",
        "terminal_state=terminal_state",
        "render_plan=render_plan",
        "last_apply_route = dict(_debug_bundle_context[\"last_apply_route\"] or {})",
        "optimisation_normalized_link_state = dict(_debug_bundle_context[\"optimisation_normalized_link_state\"] or {})",
        "engine_candidate_search_evidence = dict(_debug_bundle_context[\"engine_candidate_search_evidence\"] or {})",
    ]:
        if required not in payload_source:
            failures.append(f"payload_missing_{required}")
    for stale in [
        "last_apply_route = dict(st.session_state.get(DESIGN_GUIDE_LAST_APPLY_ROUTE_KEY) or {})",
        "post_apply_display_truth = _design_guide_display_truth_for_item(",
        "optimisation_normalized_link_state = {",
        "engine_candidate_search_evidence = dict(\n            engine_card_debug.get(\"candidate_search_evidence\")",
    ]:
        if stale in debug_source:
            failures.append(f"debug_bundle_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_debug_bundle_context_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "context_size": context_size,
        "debug_bundle_size": debug_size,
        "payload_size": payload_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Debug Bundle Context Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Context coordinator size: `{context_size}`",
                f"Debug bundle coordinator size: `{debug_size}`",
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
