from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    import inputs_page

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"inputs_page_specific_blocker_presentation_override_{timestamp}.json"
    report_path = AUDIT_DIR / f"inputs_page_specific_blocker_presentation_override_{timestamp}.md"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    cases: list[dict] = []

    presentation, guidance_debug = inputs_page.render_design_guide_specific_blocker_presentation_override(
        guidance_items=[
            {
                "guidance_intent": "specific_blocker",
                "title_main": "Bending cleanup blocked",
                "primary_action": "Increase depth first.",
                "bucket": "FAIL",
            }
        ],
        dg_presentation={"existing": True, "show_apply_button": True},
        guidance_debug={"existing_debug": True},
    )
    cases.append(
        {
            "name": "specific_blocker_title_main_overrides_presentation",
            "presentation": presentation,
            "debug": guidance_debug,
        }
    )
    expected = {
        "existing": True,
        "headline": "Bending cleanup blocked",
        "subtext": "Increase depth first.",
        "show_apply_button": False,
        "css_bucket": "fail",
        "use_success_style": False,
    }
    for key, value in expected.items():
        if presentation.get(key) != value:
            failures.append(f"specific_{key}_mismatch:{presentation}")
    if guidance_debug.get("design_guide_presentation") != presentation:
        failures.append(f"specific_debug_presentation_mismatch:{guidance_debug}")
    if guidance_debug.get("existing_debug") is not True:
        failures.append(f"specific_existing_debug_lost:{guidance_debug}")

    presentation, guidance_debug = inputs_page.render_design_guide_specific_blocker_presentation_override(
        guidance_items=[
            {
                "title": "Exact blocker remains",
                "secondary_action": "Try a larger section.",
                "exact_blockers_by_family": {"bending": {"reason": "too shallow"}},
            }
        ],
        dg_presentation={"theme": "warn"},
        guidance_debug={},
    )
    cases.append(
        {
            "name": "exact_blocker_without_intent_overrides_presentation",
            "presentation": presentation,
            "debug": guidance_debug,
        }
    )
    if presentation.get("headline") != "Exact blocker remains":
        failures.append(f"exact_headline_mismatch:{presentation}")
    if presentation.get("subtext") != "Try a larger section.":
        failures.append(f"exact_subtext_mismatch:{presentation}")
    if presentation.get("css_bucket") != "warn":
        failures.append(f"exact_default_bucket_mismatch:{presentation}")
    if presentation.get("show_apply_button") is not False:
        failures.append(f"exact_apply_visibility_mismatch:{presentation}")
    if guidance_debug.get("design_guide_presentation") != presentation:
        failures.append(f"exact_debug_presentation_mismatch:{guidance_debug}")

    original_presentation = {"headline": "Keep existing", "show_apply_button": True}
    presentation, guidance_debug = inputs_page.render_design_guide_specific_blocker_presentation_override(
        guidance_items=[{"guidance_intent": "required_fix", "title": "Normal action"}],
        dg_presentation=dict(original_presentation),
        guidance_debug={},
    )
    cases.append(
        {
            "name": "non_specific_primary_is_noop",
            "presentation": presentation,
            "debug": guidance_debug,
        }
    )
    if presentation != original_presentation:
        failures.append(f"noop_presentation_changed:{presentation}")
    if "design_guide_presentation" in guidance_debug:
        failures.append(f"noop_debug_stamped_unexpectedly:{guidance_debug}")

    payload_out = {
        "verifier": "inputs_page_specific_blocker_presentation_override_verifier",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "case_count": len(cases),
        "cases": cases,
    }
    json_path.write_text(json.dumps(payload_out, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Page Specific Blocker Presentation Override Verifier",
                "",
                f"Status: `{payload_out['status']}`",
                "",
                "## Cases",
                "",
                *(f"- `{case['name']}`" for case in cases),
                "",
                "## Failures",
                "",
                *(f"- `{failure}`" for failure in failures),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(payload_out["status"])
    print(f"json={json_path}")
    print(f"report={report_path}")
    if failures:
        print("failures=" + ";".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
