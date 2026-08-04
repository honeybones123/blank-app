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
    json_path = ARTIFACT_DIR / f"inputs_page_design_guide_feedback_cta_current_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_design_guide_feedback_cta_current_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = (ROOT / "inputs_page.py").read_text(encoding="utf-8", errors="ignore")
    coordinator_source, coordinator_size = _function_source(
        source,
        "render_design_guide_feedback_cta_current_coordinator",
    )
    legacy_source, legacy_size = _function_source(source, "_render_fast_design_guidance_panel")

    failures: list[str] = []
    if not coordinator_source:
        failures.append("feedback_cta_current_coordinator_missing")
    if coordinator_size > 250:
        failures.append(f"feedback_cta_current_coordinator_too_large:{coordinator_size}")
    for required in [
        "_one_click_feedback_cta_state(_dg_overview)",
        "guidance_debug[\"design_guide_feedback_status\"]",
        "guidance_debug[\"design_guide_one_click_cta_suppressed\"]",
        "guidance_debug[\"design_guide_engine_decision\"] = dict(_dg_engine_decision)",
        "st.session_state[DESIGN_GUIDE_DEBUG_BUNDLE_KEY].update(",
        "\"button_contract\": dict(guidance_debug.get(\"primary_button_contract\") or {})",
        "st.session_state[\"design_guide_feedback_status\"]",
        "st.session_state[\"design_guide_current_fail_fingerprint\"]",
        "st.warning(message)",
        "st.info(message)",
    ]:
        if required not in coordinator_source:
            failures.append(f"coordinator_missing_{required}")
    for required in [
        "render_design_guide_feedback_cta_current_coordinator(",
        "_dg_overview=_dg_overview",
        "guidance_debug=guidance_debug",
        "_dg_engine_decision=_dg_engine_decision",
    ]:
        if required not in legacy_source:
            failures.append(f"legacy_missing_{required}")
    for stale in [
        "_feedback_cta_state = _one_click_feedback_cta_state(_dg_overview)",
        "_oc_feedback = dict(_feedback_cta_state.get(\"feedback\") or {})",
        "guidance_debug[\"design_guide_one_click_cta_suppressed\"]",
        "st.session_state[\"design_guide_feedback_fail_fingerprint\"] = dict(_oc_feedback_fp)",
        "feedback_status = _oc_feedback_status.lower()",
    ]:
        if stale in legacy_source:
            failures.append(f"legacy_still_owns_{stale}")

    payload = {
        "verifier": "inputs_page_design_guide_feedback_cta_current_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "coordinator_size": coordinator_size,
        "legacy_size": legacy_size,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Design Guide Feedback CTA Current Verifier",
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
