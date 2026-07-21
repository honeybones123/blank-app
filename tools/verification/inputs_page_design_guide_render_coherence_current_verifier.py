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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_render_coherence_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_render_coherence_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_design_guide_render_coherence_current_coordinator",
    )
    legacy_source, legacy_size = _function_source(source, "_render_fast_design_guidance_panel")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("render_coherence_current_coordinator_missing")
    if coordinator_size > 110:
        failures.append(f"render_coherence_current_coordinator_too_large:{coordinator_size}")
    for required in [
        "_design_guide_debug_has_coherent_overview(guidance_debug)",
        "_design_guide_debug_has_efficiency_state(guidance_debug)",
        "_ensure_design_guide_debug_trace_coherent(",
        "render_debug_trace_fallback_repaired",
        "overview_rebuilt_in_render",
        "efficiency_state_rebuilt_in_render",
        "guidance_debug.clear()",
        "guidance_debug.update(_merged_dbg)",
        "_design_guide_apply_copy_model_to_items(",
        "_design_guide_apply_button_contracts_to_items(",
        "_design_guide_apply_display_truth_to_items(",
        "_recommendation_result_for_primary_guidance_card(",
        "\"_render_coherence_repairs\": list(_render_coherence_repairs)",
        "\"_render_coherence_needed\": bool(_render_coherence_needed)",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_design_guide_render_coherence_current_coordinator(",
        "current_state=current_state",
        "guidance_debug=guidance_debug",
        "guidance_items=guidance_items",
        "guidance_disp_state=guidance_disp_state",
        "_recommendation_result=_recommendation_result",
        "_branch_for_rr=_branch_for_rr",
        "_stage=_stage",
        "guidance_items = list(_render_coherence_result[\"guidance_items\"] or [])",
        "guidance_disp_state = dict(_render_coherence_result[\"guidance_disp_state\"] or {})",
        "_recommendation_result = _render_coherence_result[\"_recommendation_result\"]",
        "_render_coherence_repairs = list(_render_coherence_result[\"_render_coherence_repairs\"] or [])",
        "_render_coherence_needed = bool(_render_coherence_result[\"_render_coherence_needed\"])",
    ]:
        if required not in legacy_source:
            failures.append(f"legacy_missing_{required}")
    for stale in [
        "_render_coherence_needed = (",
        "_merged_dbg, _render_coherence_repairs = _ensure_design_guide_debug_trace_coherent(",
        "guidance_debug.clear()",
        "_stage(\"after_coherence_recommendation_result\")",
    ]:
        if stale in legacy_source:
            failures.append(f"legacy_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_render_coherence_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "legacy_size": legacy_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Render Coherence Current Verifier",
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
