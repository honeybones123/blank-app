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
    json_path = ARTIFACT_DIR / f"inputs_page_terminal_state_derivation_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_terminal_state_derivation_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    originals: dict[str, Any] = {
        "_design_guide_terminal_state_from_render_artifacts": inputs_page._design_guide_terminal_state_from_render_artifacts,
        "_derive_design_guide_terminal_state_from_current_overview": inputs_page._derive_design_guide_terminal_state_from_current_overview,
    }
    session_keys = [
        inputs_page.DESIGN_GUIDE_APPLY_BANNER_KEY,
        inputs_page.DESIGN_GUIDE_APPLY_BANNER_META_KEY,
        inputs_page.DESIGN_GUIDE_PENDING_STEP_CTX_KEY,
        "_design_guide_banner_generic_only",
    ]
    failures: list[str] = []
    cases: list[dict[str, Any]] = []

    def _restore() -> None:
        for original_name, original_value in originals.items():
            setattr(inputs_page, original_name, original_value)
        for key in session_keys:
            try:
                inputs_page.st.session_state.pop(key, None)
            except Exception:
                pass

    def _run_case(
        name: str,
        *,
        explicit_terminal: str | None,
        derived_terminal: str | None,
        guidance_debug: dict[str, Any],
        recommendation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        events: list[str] = []
        stages: list[str] = []
        items = [{"id": "primary"}]
        state = {"D": 500}

        def _explicit(items_arg, debug_arg):
            events.append("explicit")
            return explicit_terminal

        def _derived(debug_arg, state_arg, items_arg):
            events.append("derived")
            return derived_terminal

        try:
            inputs_page._design_guide_terminal_state_from_render_artifacts = _explicit
            inputs_page._derive_design_guide_terminal_state_from_current_overview = _derived
            inputs_page.st.session_state[inputs_page.DESIGN_GUIDE_APPLY_BANNER_KEY] = {"banner": True}
            inputs_page.st.session_state[inputs_page.DESIGN_GUIDE_APPLY_BANNER_META_KEY] = {"meta": True}
            inputs_page.st.session_state[inputs_page.DESIGN_GUIDE_PENDING_STEP_CTX_KEY] = {"pending": True}
            inputs_page.st.session_state["_design_guide_banner_generic_only"] = True

            out_debug, out_recommendation, terminal_state, terminal_source, terminal_meta = inputs_page.render_design_guide_terminal_state_derivation(
                guidance_items=items,
                guidance_debug=dict(guidance_debug),
                guidance_disp_state=state,
                current_recommendation_result=dict(recommendation or {"existing": True}),
                stage=lambda label: stages.append(str(label)),
            )
            session_after = {
                key: inputs_page.st.session_state.get(key)
                for key in session_keys
                if key in inputs_page.st.session_state
            }
        finally:
            _restore()

        case = {
            "name": name,
            "events": events,
            "stages": stages,
            "debug": out_debug,
            "recommendation": out_recommendation,
            "terminal_state": terminal_state,
            "terminal_source": terminal_source,
            "terminal_meta": terminal_meta,
            "session_after": session_after,
        }
        cases.append(case)
        return case

    explicit = _run_case(
        "explicit_terminal_clears_banner",
        explicit_terminal="optimal",
        derived_terminal="very_low_demand",
        guidance_debug={"_derived_terminal_state_meta": {"current_fail_keys": []}},
    )
    if explicit["events"] != ["explicit", "derived"]:
        failures.append(f"explicit_events_mismatch:{explicit['events']}")
    if explicit["stages"] != ["after_terminal_state_from_artifacts", "after_derive_terminal_state"]:
        failures.append(f"explicit_stages_mismatch:{explicit['stages']}")
    if explicit["terminal_state"] != "optimal" or explicit["terminal_source"] != "explicit_render_artifact":
        failures.append(f"explicit_terminal_mismatch:{explicit}")
    if explicit["recommendation"] is not None:
        failures.append(f"explicit_recommendation_not_cleared:{explicit['recommendation']}")
    if explicit["session_after"] != {"_design_guide_banner_generic_only": False}:
        failures.append(f"explicit_session_not_cleared:{explicit['session_after']}")

    derived = _run_case(
        "derived_terminal_used",
        explicit_terminal=None,
        derived_terminal="very_low_demand",
        guidance_debug={"_derived_terminal_state_meta": {"target_band_lo": 0.8}},
    )
    if derived["terminal_state"] != "very_low_demand" or derived["terminal_source"] != "derived_current_overview":
        failures.append(f"derived_terminal_mismatch:{derived}")
    if derived["terminal_meta"] != {"target_band_lo": 0.8}:
        failures.append(f"derived_meta_mismatch:{derived['terminal_meta']}")
    if derived["recommendation"] is not None:
        failures.append(f"derived_recommendation_not_cleared:{derived['recommendation']}")

    branch = _run_case(
        "branch_terminal_used",
        explicit_terminal=None,
        derived_terminal=None,
        guidance_debug={"guidance_branch": "optimal"},
    )
    if branch["terminal_state"] != "optimal" or branch["terminal_source"] != "guidance_branch_terminal_proof":
        failures.append(f"branch_terminal_mismatch:{branch}")

    active_fail = _run_case(
        "active_failure_suppresses_terminal",
        explicit_terminal="optimal",
        derived_terminal=None,
        guidance_debug={"overview": {"any_fail": True}},
    )
    if active_fail["terminal_state"] is not None or active_fail["terminal_source"] != "active_failure_takes_priority":
        failures.append(f"active_fail_terminal_mismatch:{active_fail}")
    if active_fail["debug"].get("design_guide_terminal_state_suppressed_reason") != "active_failure_takes_priority":
        failures.append(f"active_fail_debug_missing:{active_fail['debug']}")
    if active_fail["recommendation"] != {"existing": True}:
        failures.append(f"active_fail_recommendation_changed:{active_fail['recommendation']}")
    if active_fail["session_after"].get(inputs_page.DESIGN_GUIDE_APPLY_BANNER_KEY) != {"banner": True}:
        failures.append(f"active_fail_banner_unexpectedly_cleared:{active_fail['session_after']}")

    unresolved_low = _run_case(
        "unresolved_low_suppresses_terminal",
        explicit_terminal=None,
        derived_terminal="optimal",
        guidance_debug={
            "post_click_accepted_green": False,
            "post_click_unresolved_low_util_families": ["shear"],
        },
    )
    if unresolved_low["terminal_state"] is not None or unresolved_low["terminal_source"] != "accepted_green_invalid_unresolved_low_family":
        failures.append(f"unresolved_low_terminal_mismatch:{unresolved_low}")
    if unresolved_low["debug"].get("design_guide_terminal_state_suppressed_reason") != "accepted_green_invalid_unresolved_low_family":
        failures.append(f"unresolved_low_debug_missing:{unresolved_low['debug']}")
    if unresolved_low["recommendation"] != {"existing": True}:
        failures.append(f"unresolved_low_recommendation_changed:{unresolved_low['recommendation']}")

    none_case = _run_case(
        "no_terminal_preserves_recommendation",
        explicit_terminal=None,
        derived_terminal=None,
        guidance_debug={"guidance_branch": "active"},
    )
    if none_case["terminal_state"] is not None or none_case["terminal_source"] != "none":
        failures.append(f"none_terminal_mismatch:{none_case}")
    if none_case["recommendation"] != {"existing": True}:
        failures.append(f"none_recommendation_changed:{none_case['recommendation']}")

    payload = {
        "verifier": "inputs_page_terminal_state_derivation_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Terminal State Derivation Verifier",
                "",
                f"Status: `{payload['status']}`",
                "",
                "## Evidence",
                "",
                *(
                    f"- `{case['name']}` terminal: `{case['terminal_state']}`, source: `{case['terminal_source']}`, stages: `{case['stages']}`"
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
        print("failures=" + ",".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
