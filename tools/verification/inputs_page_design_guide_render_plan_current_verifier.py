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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_render_plan_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_render_plan_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py").read_text(encoding="utf-8", errors="ignore")
    caller_source = (ROOT / "inputs_page_modules" / "design_guide" / "panel_coordinators.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_design_guide_render_plan_current_coordinator",
    )
    caller_segment, caller_size = _function_source(caller_source, "render_design_guide_postprocess_pre_render_plan_coordinator")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("render_plan_current_coordinator_missing")
    if coordinator_size > 260:
        failures.append(f"render_plan_current_coordinator_too_large:{coordinator_size}")
    for required in [
        "_design_guide_guidance_intent_debug_rows(guidance_items)",
        "_design_guide_terminal_state_from_render_artifacts(",
        "_derive_design_guide_terminal_state_from_current_overview(",
        "_sync_pending_recommendation_from_guidance(",
        "_design_guide_render_plan(",
        "\"not_started_fast_render\"",
        "\"early_return\": True",
        "_design_guide_banner_matches_current_render(",
        "\"cleared_terminal_state\"",
        "\"cleared_stale_banner\"",
        "\"kept_matching_banner\"",
        "\"design_guide_post_apply_banner_rendered\"",
        "_design_guide_title_alignment_verification_record(",
        "\"overview_untrusted_after_fresh_recompute\"",
        "\"final_assertion_guard_state\"",
        "DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT",
        "\"render_post_apply_banner\": bool(render_post_apply_banner)",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_design_guide_render_plan_current_coordinator(",
        "guidance_debug=guidance_debug",
        "guidance_items=guidance_items",
        "guidance_disp_state=guidance_disp_state",
        "_recommendation_result=_recommendation_result",
        "collapse_meta=collapse_meta",
        "redundancy_meta=redundancy_meta",
        "fingerprint=fingerprint",
        "fast_focus_section=fast_focus_section",
        "guidance_fresh_compute_used=guidance_fresh_compute_used",
        "sidebar_debug=sidebar_debug",
        "_render_coherence_repairs=_render_coherence_repairs",
        "_render_coherence_needed=_render_coherence_needed",
        "if bool(_render_plan_result.get(\"early_return\")):",
        "terminal_state = _render_plan_result[\"terminal_state\"]",
        "pending_recommendation = _render_plan_result[\"pending_recommendation\"]",
        "render_plan = dict(_render_plan_result[\"render_plan\"] or {})",
        "render_post_apply_banner = bool(_render_plan_result[\"render_post_apply_banner\"])",
    ]:
        if required not in caller_segment:
            failures.append(f"caller_missing_{required}")
    for stale in [
        "guidance_debug[\"guidance_intent_items\"] = _design_guide_guidance_intent_debug_rows(guidance_items)",
        "terminal_state = _design_guide_terminal_state_from_render_artifacts(",
        "render_plan = _design_guide_render_plan(",
        "banner_matches_current_render = _design_guide_banner_matches_current_render(",
        "_title_alignment_record = _design_guide_title_alignment_verification_record(",
        "_final_assertion_guard_state = {",
        "DESIGN_GUIDE_TITLE_ALIGNMENT_LOG_EVENT,",
    ]:
        if stale in caller_segment:
            failures.append(f"caller_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_render_plan_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "caller_size": caller_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Render Plan Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Caller coordinator size: `{caller_size}`",
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
