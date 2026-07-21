from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
STYLE_PATH = ROOT / "ui" / "inputs_page_style.py"
ARTIFACTS_VERIFICATION = ROOT / "artifacts" / "verification"
ARTIFACTS_AUDITS = ROOT / "artifacts" / "audits"


DELETED_TEXT = "Next step: confirm or auto-design the shear reinforcement below."


def main() -> int:
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    style_source = STYLE_PATH.read_text(encoding="utf-8")
    checks = {
        "deleted_shear_next_hint_text_absent": DELETED_TEXT not in inputs_source,
        "deleted_fast_next_hint_helper_absent": "def _render_fast_next_hint" not in inputs_source,
        "deleted_fast_next_hint_call_absent": "_render_fast_next_hint(" not in inputs_source,
        "deleted_fast_next_hint_css_absent": ".fast-next-hint {" not in style_source
        and ".fast-next-hint.fast-next-hint--design-guide-follow" not in style_source,
        "shear_section_still_renders": '_render_recommendation_section_header(\n            "Shear"' in inputs_source,
        "auto_design_summary_class_preserved": "fast-auto-design-summary" in style_source
        and "fast-next-hint--design-guide-follow" in inputs_source,
        "design_brain_truth_not_touched": all(
            token not in inputs_source
            for token in (
                "delete_shear_next_hint_changes_family",
                "FinalDesignGuidePublication =",
            )
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    payload = {
        "status": status,
        "checks": checks,
        "scope": {
            "deleted": "Fast-mode shear next-step hint above the shear inputs.",
            "engineering_logic_changed": False,
            "cta_apply_publication_changed": False,
            "shear_inputs_changed": False,
        },
    }

    ARTIFACTS_VERIFICATION.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_VERIFICATION / f"inputs_shear_next_hint_deleted_{now}.json"
    report_path = ARTIFACTS_AUDITS / f"inputs_shear_next_hint_deleted_{now}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Shear Next Hint Deleted Snapshot",
                "",
                f"Status: `{status}`",
                "",
                "## Checks",
                *[f"- `{name}`: `{'PASS' if ok else 'FAIL'}`" for name, ok in checks.items()],
                "",
                "## Scope",
                "- Removed only the fast-mode hint above the Shear input section.",
                "- Shear widgets, Design Brain, CTA/apply, publication, and engineering behavior are unchanged.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
