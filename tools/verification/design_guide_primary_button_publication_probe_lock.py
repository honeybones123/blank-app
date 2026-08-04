"""Lock the rendered primary Design Guide button to the browser publication probe.

This guards the live failure where the card rendered an enabled Apply button,
but the browser/exported publication payload still had no CTA intent.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_body(source: str, name: str) -> str:
    marker = f"def {name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + len(marker))
    return source[start:] if next_def < 0 else source[start:next_def]


def main() -> int:
    source_path = ROOT / "inputs_page_modules" / "design_guide" / "current_coordinators.py"
    source = source_path.read_text(encoding="utf-8", errors="ignore")
    panel_path = ROOT / "inputs_page_modules" / "design_guide" / "panel_coordinators.py"
    panel_source = panel_path.read_text(encoding="utf-8", errors="ignore")
    app_path = ROOT / "app.py"
    app_source = app_path.read_text(encoding="utf-8", errors="ignore")
    body = _function_body(source, "render_guidance_secondary_button_contract_current_coordinator")
    failures: list[str] = []

    required_tokens = {
        "writes_primary_button_contract_session": 'st.session_state["design_guide_primary_button_contract"]',
        "reads_existing_debug_bundle": "debug_bundle = dict(st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY) or {})",
        "publishes_displayed_contract": '"displayed_primary_button_contract": dict(button_contract)',
        "publishes_button_contract": '"button_contract": dict(button_contract)',
        "publishes_contract_updates": '"button_contract_updates": dict(button_contract.get("updates") or {})',
        "projects_final_publication": "_final_publication_debug_projection(",
        "uses_render_publication_reason": 'publication_reason="design_guide_render_primary_button_contract"',
        "writes_debug_bundle_after_projection": "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = debug_bundle",
    }
    if not body:
        failures.append("render_guidance_secondary_button_contract_current_coordinator_missing")
    for name, token in required_tokens.items():
        if token not in body:
            failures.append(f"{name}_missing")

    projection_index = body.find("_final_publication_debug_projection(")
    session_write_index = body.rfind("st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY] = debug_bundle")
    if projection_index < 0 or session_write_index < 0 or session_write_index < projection_index:
        failures.append("debug_bundle_not_written_after_final_publication_projection")

    exit_body = _function_body(source, "render_design_guide_publication_exit_state_current_coordinator")
    if "_refresh_design_guide_debug_bundle_publication_projection(publication_reason)" not in exit_body:
        failures.append("panel_exit_publication_refresh_coordinator_missing")
    if "render_design_guide_publication_exit_state_current_coordinator()" not in panel_source:
        failures.append("panel_does_not_call_exit_publication_refresh")

    app_required_tokens = {
        "late_exact_evidence_reprojection_gate": "_dg_publication_has_late_exact_evidence",
        "stale_general_publication_reprojection_gate": "_dg_final_publication_needs_reprojection",
        "browser_reprojection_source": '"source": "browser_state_guidance_probe_projection"',
        "canonical_family_preferred_over_button_family": (
            '"selected_family_id": _probe_publication_dict.get("selected_family")'
        ),
        "debug_bundle_selected_family_restamped": (
            'dg_bundle_safe["selected_family_id"] = dg_final_publication_payload.get("selected_family_id")'
        ),
        "debug_bundle_publication_restamped": 'dg_bundle_safe["final_design_guide_publication"] = dict(_probe_publication_dict)',
    }
    for name, token in app_required_tokens.items():
        if token not in app_source:
            failures.append(f"{name}_missing")

    payload = {
        "schema": "design_guide.primary_button_publication_probe_lock.v1",
        "status": "PASS" if not failures else "FAIL",
        "source": [
            str(source_path.relative_to(ROOT)),
            str(panel_path.relative_to(ROOT)),
            str(app_path.relative_to(ROOT)),
        ],
        "failures": failures,
        "locked_gap": (
            "visible primary Apply button must stamp the same contract into browser publication/debug state; "
            "late exact-blocker evidence must reproject stale general publication identities"
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_primary_button_publication_probe_lock_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_primary_button_publication_probe_lock_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide Primary Button Publication Probe Lock",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Locked Gap",
                "",
                "- A visible enabled primary Apply button must publish the same CTA contract into the browser/debug publication probe.",
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
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
