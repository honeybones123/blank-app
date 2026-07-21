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
    json_path = ARTIFACT_DIR / f"inputs_page_guidance_secondary_card_model_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_guidance_secondary_card_model_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    render_source = (ROOT / "inputs_page_modules" / "design_guide" / "render_coordinators.py").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_guidance_secondary_card_model_current_coordinator",
    )
    renderer_source, renderer_size = _function_source(render_source, "render_guidance_secondary_items")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("guidance_secondary_card_model_coordinator_missing")
    if coordinator_size > 190:
        failures.append(f"guidance_secondary_card_model_coordinator_too_large:{coordinator_size}")
    if renderer_size > 80:
        failures.append(f"guidance_secondary_renderer_not_wrapper:{renderer_size}")
    for required in [
        "_guidance_card_label(item)",
        "_guidance_before_after_text(item, guidance_disp_state)",
        "fast-guidance-action-anchor--primary",
        "_guidance_card_why_body(item)",
        "_guidance_card_proposed_change_html(item, guidance_disp_state)",
        "_derived_guidance_title_from_updates(guidance_disp_state, title_updates)",
        "st.session_state[\"design_guide_title_rebuilt_from_updates\"]",
        "inputs_render_audit[\"design_guide_title_rebuilt_from_updates\"]",
        "inputs_render_audit[\"next_mode_recommendation_rendered\"]",
        "inputs_render_audit[\"shear_tightening_rendered\"]",
        "\"card_html\": card_html",
        "\"anchor_class\": anchor_class",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_card_model_fn(",
        "idx=idx",
        "item=item",
        "guidance_disp_state=guidance_disp_state",
        "inputs_render_audit=inputs_render_audit",
        "start_index=start_index",
        "primary_card_presentation=primary_card_presentation",
        "card_html = str(card_model[\"card_html\"] or \"\")",
        "anchor_class = str(card_model[\"anchor_class\"] or \"\")",
        "st_module.markdown(card_html, unsafe_allow_html=True)",
    ]:
        if required not in renderer_source:
            failures.append(f"renderer_missing_{required}")
    for stale in [
        "badge_label = _guidance_card_label(item)",
        "before_after = item.get(\"guidance_before_after\")",
        "display_truth = dict(item.get(\"display_truth\") or {})",
        "st.session_state[\"design_guide_title_rebuilt_from_updates\"]",
        "inputs_render_audit[\"next_mode_recommendation_rendered\"]",
        "card_html = (",
    ]:
        if stale in renderer_source:
            failures.append(f"renderer_still_owns_{stale}")
    if "def _render_guidance_secondary_items(" in source:
        failures.append("page_local_guidance_secondary_items_still_present")

    payload = {
        "verifier": "inputs_page_guidance_secondary_card_model_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "renderer_size": renderer_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Guidance Secondary Card Model Current Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                f"Coordinator size: `{coordinator_size}`",
                f"Renderer size: `{renderer_size}`",
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
