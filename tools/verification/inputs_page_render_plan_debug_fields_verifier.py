from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_render_plan_debug_fields_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_render_plan_debug_fields_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    original_first_actionable = inputs_page._first_actionable_guidance_item
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        inputs_page._first_actionable_guidance_item = original_first_actionable
        try:
            inputs_page.st.session_state.pop("_design_guide_render_plan_debug", None)
        except Exception:
            pass

    def _run_case(
        name: str,
        *,
        guidance_items: list[dict],
        actionable_item: dict | None,
        terminal_state: str | None,
    ) -> dict[str, Any]:
        stages: list[str] = []
        calls: list[dict[str, Any]] = []
        terminal_meta = {
            "current_fail_keys": ["bending", "shear"],
            "current_governing_util": 1.11,
            "target_band_lo": 0.82,
            "target_band_hi": 0.94,
        }
        redundancy_meta = {
            "suppressed": True,
            "reason": "unit_overlap",
            "suppressed_titles": ["Duplicate"],
        }
        render_plan = {
            "render_primary_only": True,
            "reason": "unit_primary",
            "input_count": "3",
            "visible_count": "1",
        }
        recommendation_result = {"recommendation": name}
        guidance_debug: dict[str, Any] = {"existing": True}

        def _first_actionable(items):
            calls.append({"event": "first_actionable", "items": [dict(item) for item in items]})
            return actionable_item

        try:
            inputs_page._first_actionable_guidance_item = _first_actionable
            out_debug = inputs_page.render_design_guide_render_plan_debug_fields(
                guidance_items=[dict(item) for item in guidance_items],
                guidance_debug=guidance_debug,
                recommendation_result=recommendation_result,
                terminal_state=terminal_state,
                terminal_state_source="unit_source",
                terminal_meta=terminal_meta,
                redundancy_meta=redundancy_meta,
                banner_matches_current_render=True,
                banner_reconciled="kept_matching_banner",
                render_post_apply_banner=False,
                render_plan=render_plan,
                stage=lambda label: stages.append(str(label)),
            )
            session_debug = dict(inputs_page.st.session_state.get("_design_guide_render_plan_debug") or {})
        finally:
            _restore()

        case = {
            "name": name,
            "stages": stages,
            "calls": calls,
            "debug": out_debug,
            "session_debug": session_debug,
        }
        cases.append(case)
        return case

    terminal = _run_case(
        "terminal_actionable",
        guidance_items=[{"id": "primary"}],
        actionable_item={"id": "primary"},
        terminal_state="optimal",
    )
    if terminal["stages"] != ["post_plan.after_render_plan_debug_fields"]:
        failures.append(f"terminal_stage_mismatch:{terminal['stages']}")
    if terminal["debug"].get("design_guide_terminal_state") != "optimal":
        failures.append(f"terminal_state_missing:{terminal['debug']}")
    if terminal["debug"].get("design_guide_terminal_positive") is not True:
        failures.append(f"terminal_positive_mismatch:{terminal['debug']}")
    if terminal["debug"].get("design_guide_has_actionable_recommendation") is not True:
        failures.append(f"terminal_actionable_mismatch:{terminal['debug']}")
    if terminal["debug"].get("design_guide_visible_guidance_item_count") != 1:
        failures.append(f"terminal_visible_count_mismatch:{terminal['debug']}")
    expected_session_subset = {
        "terminal_state": "optimal",
        "terminal_state_source": "unit_source",
        "current_fail_keys": ["bending", "shear"],
        "current_governing_util": 1.11,
        "target_band_lo": 0.82,
        "target_band_hi": 0.94,
        "render_primary_only": True,
        "reason": "unit_primary",
        "input_count": 3,
        "visible_count": 1,
        "banner_matches_current_render": True,
        "banner_reconciled": "kept_matching_banner",
        "post_apply_banner_rendered": False,
    }
    if terminal["session_debug"] != expected_session_subset:
        failures.append(f"terminal_session_debug_mismatch:{terminal['session_debug']}")

    nonterminal = _run_case(
        "nonterminal_not_actionable",
        guidance_items=[{"id": "secondary"}],
        actionable_item=None,
        terminal_state="blocked",
    )
    if nonterminal["debug"].get("design_guide_terminal_positive") is not False:
        failures.append(f"nonterminal_positive_mismatch:{nonterminal['debug']}")
    if nonterminal["debug"].get("design_guide_has_actionable_recommendation") is not False:
        failures.append(f"nonterminal_actionable_mismatch:{nonterminal['debug']}")
    if not nonterminal["calls"] or nonterminal["calls"][0].get("items") != [{"id": "secondary"}]:
        failures.append(f"nonterminal_actionable_call_mismatch:{nonterminal['calls']}")

    required_debug_keys = {
        "design_guide_terminal_state_source",
        "design_guide_terminal_current_fail_keys",
        "design_guide_terminal_current_governing_util",
        "design_guide_terminal_target_band_lo",
        "design_guide_terminal_target_band_hi",
        "recommendation_result",
        "design_guide_overlap_suppressed",
        "design_guide_overlap_suppression_reason",
        "design_guide_overlap_suppressed_titles",
        "design_guide_banner_matches_current_render",
        "design_guide_banner_reconciled",
        "design_guide_post_apply_banner_rendered",
        "design_guide_render_primary_only",
        "design_guide_render_plan_reason",
        "design_guide_visible_guidance_item_count",
    }
    missing = sorted(required_debug_keys - set(terminal["debug"]))
    if missing:
        failures.append(f"required_debug_keys_missing:{missing}")

    payload = {
        "verifier": "inputs_page_render_plan_debug_fields_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Render Plan Debug Fields Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` terminal_positive: `{case['debug'].get('design_guide_terminal_positive')}`, actionable: `{case['debug'].get('design_guide_has_actionable_recommendation')}`"
                    for case in cases
                ),
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
