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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_debug_bundle_payload_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_debug_bundle_payload_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    payload_source, payload_size = _function_source(
        source,
        "render_design_guide_debug_bundle_payload_current_coordinator",
    )
    debug_source, debug_size = _function_source(
        source,
        "render_design_guide_debug_bundle_current_coordinator",
    )

    failures: list[str] = []
    if not payload_source:
        failures.append("debug_bundle_payload_current_coordinator_missing")
    if payload_size > 360:
        failures.append(f"debug_bundle_payload_current_coordinator_too_large:{payload_size}")
    if debug_size > 70:
        failures.append(f"debug_bundle_current_coordinator_not_wrapper:{debug_size}")
    for required in [
        "render_design_guide_debug_bundle_context_current_coordinator(",
        "return {",
        "\"guidance_compute_ms\": guidance_compute_ms",
        "\"manual_resolver_lock_check\"",
        "\"displayed_primary_display_truth\"",
        "\"design_guide_engine_decision\"",
        "\"optimisation_normalized_link_state\"",
        "\"post_apply_display_truth\": dict(post_apply_display_truth)",
        "\"recommendation_result_winner_id\"",
        "**_design_guide_step_history_debug_summary()",
        "**guidance_dedupe_meta",
    ]:
        if required not in payload_source:
            failures.append(f"payload_missing_{required}")
    for required in [
        "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = render_design_guide_debug_bundle_payload_current_coordinator(",
        "resolved_guidance_actions=resolved_guidance_actions",
        "mode_mt=mode_mt",
        "bottom_bt=bottom_bt",
    ]:
        if required not in debug_source:
            failures.append(f"debug_bundle_missing_{required}")
    for stale in [
        "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = {",
        "\"manual_resolver_lock_check\": {",
        "\"recommendation_result_winner_id\": (",
        "render_design_guide_debug_bundle_context_current_coordinator(",
    ]:
        if stale in debug_source:
            failures.append(f"debug_bundle_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_debug_bundle_payload_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "payload_size": payload_size,
        "debug_bundle_size": debug_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Debug Bundle Payload Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Payload coordinator size: `{payload_size}`",
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
