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
    json_path = ARTIFACT_DIR / f"inputs_page_fresh_design_guide_panel_coordinator_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_fresh_design_guide_panel_coordinator_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_inputs_fresh_design_guide_panel_coordinator",
    )
    render_inputs_source, _ = _function_source(source, "render_inputs")
    wrapper_source, wrapper_size = _function_source(source, "_render_fresh_design_guide_panel")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("fresh_design_guide_panel_coordinator_missing")
    if coordinator_size > 280:
        failures.append(f"fresh_design_guide_panel_coordinator_too_large:{coordinator_size}")
    if not wrapper_source:
        failures.append("fresh_design_guide_panel_wrapper_missing")
    if wrapper_size > 25:
        failures.append(f"fresh_design_guide_panel_wrapper_too_large:{wrapper_size}")
    for required in [
        "render_inputs_fresh_design_guide_start_coordinator(",
        "st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)",
        "CODEX_BROWSER_TEST_MODE",
        "_design_guide_button_contract_enabled(pre_render_contract)",
        "render_inputs_pre_render_safe_combined_contract_promotion_coordinator(",
        "render_inputs_pre_render_bending_exact_blocker_coordinator(",
        '"pre_render_safe_combined_cleanup_proof_promoted"',
        "render_inputs_pre_render_canonical_family_coordinator(",
        "render_inputs_pre_render_design_guide_item_coordinator(",
        "render_inputs_pre_render_publication_boundary_coordinator(",
        "render_inputs_pre_render_direct_action_publication_probe_coordinator(",
        "render_inputs_design_guide_final_panel_coordinator(",
        "render_inputs_design_guide_post_render_probe_coordinator(",
        "render_design_guide_slot_from_final_publication_payload_fn",
        "render_inputs_design_guide_missing_card_fallback_identity_coordinator(",
        "render_inputs_design_guide_missing_card_publication_boundary_coordinator(",
        "render_inputs_design_guide_missing_card_publication_authority_coordinator(",
        "render_inputs_design_guide_missing_card_recovery_render_coordinator(",
        "render_inputs_design_guide_post_recovery_tail_coordinator(",
        "render_inputs_design_guide_post_render_trace_coordinator(",
        "inputs_elapsed_ms_fn=inputs_elapsed_ms_fn",
        "update_user_latency_metrics_fn=update_user_latency_metrics_fn",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_inputs_fresh_design_guide_panel_coordinator(",
        "show_design_guide_for_current_inputs=show_design_guide_for_current_inputs",
        "design_guide_slot=design_guide_slot",
        "render_trace_started=_render_trace_started",
        "mark_fn=_mark",
        "phase5c_render_trace_fn=_phase5c_render_trace",
        "sync_callbacks=sync_callbacks",
        "inputs_render_audit=inputs_render_audit",
        "inputs_detailed_mode=inputs_detailed_mode",
        "fast_focus_section=fast_focus_section",
        "trace_fn=_inputs_pre_widget_trace",
        "render_design_guide_slot_from_final_publication_payload_fn=(",
        "_render_design_guide_slot_from_final_publication_payload",
        "inputs_elapsed_ms_fn=_inputs_elapsed_ms",
        "update_user_latency_metrics_fn=_update_user_latency_metrics",
    ]:
        if required not in wrapper_source:
            failures.append(f"wrapper_missing_{required}")
    for stale in [
        "render_inputs_pre_render_safe_combined_contract_promotion_coordinator(",
        "render_inputs_pre_render_bending_exact_blocker_coordinator(",
        "render_inputs_design_guide_final_panel_coordinator(",
        "render_inputs_design_guide_post_render_probe_coordinator(",
        "render_inputs_design_guide_missing_card_recovery_render_coordinator(",
        "render_inputs_design_guide_post_recovery_tail_coordinator(",
        "render_inputs_design_guide_post_render_trace_coordinator(",
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_fresh_design_guide_panel_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "wrapper_size": wrapper_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Fresh Design Guide Panel Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Wrapper size: `{wrapper_size}`",
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
