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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_presentation_local_cleanup_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_presentation_local_cleanup_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (
        ROOT
        / "inputs_page_modules"
        / "design_guide"
        / "current_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    panel_source = (
        ROOT
        / "inputs_page_modules"
        / "design_guide"
        / "panel_coordinators.py"
    ).read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_design_guide_presentation_local_cleanup_current_coordinator",
    )
    panel_source_fn, panel_size = _function_source(
        panel_source,
        "render_design_guide_active_guard_presentation_engine_coordinator",
    )

    failures: list[str] = []
    if not coordinator_source:
        failures.append("presentation_local_cleanup_current_coordinator_missing")
    if coordinator_size > 120:
        failures.append(f"presentation_local_cleanup_current_coordinator_too_large:{coordinator_size}")
    for required in [
        "_collect_design_overview(",
        "_build_design_guide_presentation_state(",
        "\"_dg_presentation\": _dg_presentation",
        "\"guidance_items\": list(guidance_items or [])",
        "\"_recommendation_result\": _recommendation_result",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_design_guide_presentation_local_cleanup_current_coordinator(",
        "guidance_debug=guidance_debug",
        "guidance_items=guidance_items",
        "guidance_disp_state=guidance_disp_state",
        "efficiency_state=efficiency_state",
        "terminal_state=terminal_state",
        "terminal_state_source=terminal_state_source",
        "_recommendation_result=_recommendation_result",
        "pending_recommendation=pending_recommendation",
        "_dg_overview = _presentation_local_cleanup[\"_dg_overview\"]",
        "_dg_presentation = dict(_presentation_local_cleanup[\"_dg_presentation\"] or {})",
        "guidance_items = list(_presentation_local_cleanup[\"guidance_items\"] or [])",
    ]:
        if required not in panel_source_fn:
            failures.append(f"panel_missing_{required}")
    for stale in [
        "_dg_engine_decision",
        "legacy_item_from_decision(",
        "_maybe_promote_safe_local_cleanup_primary(",
        "_direct_target_band_guidance_item(",
        "_shear_tightening_as_local_cleanup_item(",
    ]:
        if stale in coordinator_source or stale in panel_source_fn:
            failures.append(f"retired_path_still_present_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_presentation_local_cleanup_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "panel_size": panel_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Presentation/Local-Cleanup Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Panel coordinator size: `{panel_size}`",
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
