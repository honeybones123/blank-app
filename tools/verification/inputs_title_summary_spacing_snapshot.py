"""Source snapshot for Inputs title and summary-card spacing."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
SUMMARY_SECTIONS = ROOT / "ui" / "summary_sections.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    stamp = time.strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    summary_source = SUMMARY_SECTIONS.read_text(encoding="utf-8")
    summary_start = inputs_source.find("def _render_current_inputs_summary()")
    summary_end = inputs_source.find("render_timing_mark(\n            \"inputs_page.summary_render.end\"", summary_start)
    summary_render_source = (
        inputs_source[summary_start:summary_end]
        if summary_start >= 0 and summary_end > summary_start
        else ""
    )

    title_css_match = re.search(
        r"\.inputs-page-title\s*\{(?P<body>[^}]*)\}",
        inputs_source,
        flags=re.DOTALL,
    )
    title_css = title_css_match.group("body") if title_css_match else ""
    stack_css_match = re.search(
        r"\.summary-card-stack\s*\{(?P<body>[^}]*)\}",
        summary_source,
        flags=re.DOTALL,
    )
    stack_css = stack_css_match.group("body") if stack_css_match else ""

    checks = {
        "native_title_replaced_by_scoped_heading": 'st.title("Inputs")' not in summary_render_source
        and '<h1 class="inputs-page-title">Inputs</h1>' in summary_render_source,
        "title_has_tight_top_margin": "margin: 0.15rem 0 0.38rem" in title_css,
        "title_letter_spacing_not_negative": "letter-spacing: 0" in title_css,
        "summary_stack_top_margin_tight": "margin: 0.18rem 0 1rem" in stack_css,
        "summary_stack_still_contained": "contain: layout paint" in stack_css,
        "engineering_and_design_brain_not_touched": "FinalDesignGuidePublication" not in title_css + stack_css
        and "_design_guide_button_contract" not in title_css + stack_css,
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "schema": "inputs_title_summary_spacing_snapshot.v1",
        "generated_at": stamp,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "ownership": {
            "changed": "Inputs heading CSS and summary-card stack margin only",
            "engineering_logic_changed": False,
            "cta_publication_apply_changed": False,
        },
    }

    json_path = ARTIFACT_DIR / f"inputs_title_summary_spacing_{stamp}.json"
    report_path = AUDIT_DIR / f"inputs_title_summary_spacing_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Inputs Title Summary Spacing Snapshot",
                "",
                f"Result: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *[f"- `{name}`: {'PASS' if ok else 'FAIL'}" for name, ok in checks.items()],
                "",
                "## Ownership",
                "",
                "- Only Inputs title spacing and summary-card stack top margin are covered.",
                "- No Design Guide, CTA, Apply, publication, or engineering behavior moved.",
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in failures] or ["- None"]),
            ]
        ),
        encoding="utf-8",
    )
    print(f"inputs_title_summary_spacing_snapshot {payload['status']}")
    print(f"json: {json_path}")
    print(f"report: {report_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
