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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_final_render_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_final_render_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_design_guide_final_render_current_coordinator",
    )
    legacy_source, legacy_size = _function_source(source, "_render_fast_design_guidance_panel")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("final_render_current_coordinator_missing")
    if coordinator_size > 190:
        failures.append(f"final_render_current_coordinator_too_large:{coordinator_size}")
    for required in [
        'guidance_debug["design_guide_presentation"]',
        "_set_cached_design_guide_guidance(",
        "_post_click_accepted_green_audit(",
        "render_guidance_secondary_items(",
        "render_card_model_fn=render_guidance_secondary_card_model_current_coordinator",
        "render_primary_cta_state_fn=render_guidance_secondary_primary_cta_state_current_coordinator",
        "render_button_contract_fn=render_guidance_secondary_button_contract_current_coordinator",
        "render_apply_action_fn=render_guidance_secondary_apply_action_current_coordinator",
        "st.success(_terminal_title)",
        "render_design_guide_post_apply_banner(",
        "st_module=st",
        "apply_banner_key=DESIGN_GUIDE_APPLY_BANNER_KEY",
        "st.session_state[DESIGN_GUIDE_PANEL_BASELINE_FP_KEY] = fingerprint",
        "st.session_state.pop(DESIGN_GUIDE_NEEDS_REFRESH_KEY, None)",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    orchestration_source, _ = _function_source(
        source,
        "render_design_guide_final_render_branch_dispatch_coordinator",
    )
    for required in [
        "render_design_guide_final_render_current_coordinator(",
        "guidance_debug=guidance_debug",
        "_dg_presentation=dg_presentation",
        "guidance_items_raw=guidance_items_raw",
        "render_post_apply_banner=render_post_apply_banner",
        "fast_focus_section=fast_focus_section",
    ]:
        if required not in orchestration_source:
            failures.append(f"orchestration_missing_{required}")
    if legacy_source:
        for stale in [
            "_post_cleanup_terminal_render = bool(",
            "_accepted_render_item = _guidance_item(",
            "_terminal_truth_source = str(_dg_presentation.get",
            "_visible_render_items = list(render_plan.get",
            "st.session_state[DESIGN_GUIDE_PANEL_BASELINE_FP_KEY] = fingerprint",
        ]:
            if stale in legacy_source:
                failures.append(f"legacy_still_owns_{stale}")
    if "_render_design_guide_post_apply_banner(" in source:
        failures.append("page_local_post_apply_banner_wrapper_still_present")
    if "def _render_guidance_secondary_items(" in source:
        failures.append("page_local_guidance_secondary_items_still_present")

    payload = {
        "verifier": "inputs_page_design_guide_final_render_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "legacy_size": legacy_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Final Render Current Verifier",
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
