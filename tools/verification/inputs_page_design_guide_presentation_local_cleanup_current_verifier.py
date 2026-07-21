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

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_design_guide_presentation_local_cleanup_current_coordinator",
    )
    legacy_source, legacy_size = _function_source(source, "_render_fast_design_guidance_panel")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("presentation_local_cleanup_current_coordinator_missing")
    if coordinator_size > 190:
        failures.append(f"presentation_local_cleanup_current_coordinator_too_large:{coordinator_size}")
    for required in [
        "_dg_overview = guidance_debug.get(\"overview\")",
        "_collect_design_overview(",
        "_maybe_promote_safe_local_cleanup_primary(",
        "_direct_target_band_guidance_item(",
        "_build_design_guide_presentation_state(",
        "_dg_engine_decision = dict(st.session_state.get(\"_design_guide_engine_decision\") or {})",
        "legacy_item_from_decision(",
        "_shear_tightening_as_local_cleanup_item(",
        "\"_dg_presentation\": _dg_presentation",
        "\"_dg_engine_decision\": dict(_dg_engine_decision or {})",
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
        "_dg_engine_decision = dict(_presentation_local_cleanup[\"_dg_engine_decision\"] or {})",
        "guidance_items = list(_presentation_local_cleanup[\"guidance_items\"] or [])",
    ]:
        if required not in legacy_source:
            failures.append(f"legacy_missing_{required}")
    for stale in [
        "_dg_overview = guidance_debug.get(\"overview\")",
        "_local_cleanup_seed_items = guidance_items",
        "_dg_presentation = _build_design_guide_presentation_state(",
        "_engine_terminal_item = legacy_item_from_decision(",
        "_terminal_shear_cleanup = _shear_tightening_as_local_cleanup_item(",
    ]:
        if stale in legacy_source:
            failures.append(f"legacy_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_presentation_local_cleanup_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "legacy_size": legacy_size,
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
