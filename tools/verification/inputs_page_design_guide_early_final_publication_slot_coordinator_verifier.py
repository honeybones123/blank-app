from __future__ import annotations

import ast
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _function_sources(source: str, name: str) -> list[tuple[str, int, int, int]]:
    tree = ast.parse(source)
    matches: list[tuple[str, int, int, int]] = []
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            size = node.end_lineno - node.lineno + 1
            matches.append(("\n".join(lines[node.lineno - 1 : node.end_lineno]), size, node.lineno, node.end_lineno))
    return matches


def _largest_function_source(source: str, name: str) -> tuple[str, int]:
    matches = _function_sources(source, name)
    if not matches:
        return "", 0
    function_source, size, _, _ = max(matches, key=lambda item: item[1])
    return function_source, size


def main() -> int:
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / (
        f"inputs_page_design_guide_early_final_publication_slot_coordinator_{timestamp}.json"
    )
    report_path = AUDIT_DIR / (
        f"inputs_page_design_guide_early_final_publication_slot_coordinator_{timestamp}.md"
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _largest_function_source(
        source,
        "render_inputs_design_guide_early_final_publication_slot_coordinator",
    )
    render_inputs_source, _ = _largest_function_source(source, "render_inputs")
    stale_nested_sources = _function_sources(
        source,
        "_render_design_guide_slot_from_final_publication_payload",
    )

    failures: list[str] = []
    if not coordinator_source:
        failures.append("early_final_publication_slot_coordinator_missing")
    if coordinator_size > 270:
        failures.append(f"early_final_publication_slot_coordinator_too_large:{coordinator_size}")
    if stale_nested_sources:
        failures.append("stale_nested_final_publication_slot_renderer_still_present")
    for required in [
        "show_design_guide_for_current_inputs",
        "design_guide_slot is None",
        "st.session_state.get(DESIGN_GUIDE_DEBUG_BUNDLE_KEY)",
        "def publication_payload_candidates(",
        '"final_publication_verifier_payload"',
        '"final_design_guide_publication"',
        '"top_level_publication_probe"',
        '"publication_probe"',
        '"guidance_compute_probe"',
        '"design_guide_probe"',
        '"browser_debug_probe"',
        '"post_cleanup_acceptance_probe"',
        '"render_final_publication_payload_early_reason"',
        '"no_publication_payload_found"',
        '"render_final_publication_payload_early_candidate_count"',
        '"Apply proposed result"',
        '"apply_resolved_candidate"',
        '"handle_apply_buttons"',
        '"handle_auto_design"',
        "_record_rendered_design_guide_primary_apply_payload(",
        "_build_final_design_guide_publication(",
        "_build_final_design_guide_card_format(",
        "_render_final_design_guide_card_html(",
        "design_guide_slot.empty()",
        "_render_design_guide_heading_if_needed()",
        "st.button(",
        "on_click=_queue_primary_design_guide_button_action",
        '"marker": "early_final_publication_payload_render"',
        '"real_design_guide_card_rendered_source"',
        '"render_final_publication_payload_early_error"',
        "return True",
        "return False",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "_render_design_guide_slot_from_final_publication_payload = functools.partial(",
        "render_inputs_design_guide_early_final_publication_slot_coordinator,",
        "show_design_guide_for_current_inputs=show_design_guide_for_current_inputs",
        "design_guide_slot=design_guide_slot",
        "render_inputs_design_guide_before_inputs_form_panel_coordinator(",
        "render_design_guide_slot_from_final_publication_payload_fn=(",
        "_render_design_guide_slot_from_final_publication_payload",
    ]:
        if required not in render_inputs_source:
            failures.append(f"render_inputs_missing_{required}")
    for stale in [
        "def _render_design_guide_slot_from_final_publication_payload(",
        "def _publication_payload_candidates(",
        "_publication_candidates = list(",
        'bundle["render_final_publication_payload_early_candidate_count"]',
        'key=f"apply_design_guide_{str(source or',
        'bundle["real_design_guide_card_rendered_source"] = str(source or "")',
    ]:
        if stale in render_inputs_source:
            failures.append(f"render_inputs_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_early_final_publication_slot_coordinator_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Early Final Publication Slot Coordinator Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
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
