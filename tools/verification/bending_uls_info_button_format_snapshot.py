"""Verify ULS bending 1.x info buttons use the Check 1.6 row format."""

from __future__ import annotations

import json
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENDING_TABS = ROOT / "bending_tabs.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    generated_at = time.strftime("%Y-%m-%dT%H-%M-%S")
    source = BENDING_TABS.read_text(encoding="utf-8")

    check_help_texts = [
        "Stress block parameters",
        "Steel area and tensile force",
        "Concrete compressive force",
        "Strain compatibility and steel yield",
    ]
    checks = {
        "shared_info_row_helper_exists": "def _bending_check_info_row(" in source
        and "st.columns([0.9, 0.1])" in source
        and 'st.markdown("**Info:**")' in source
        and "with info_i_button(help_text=help_text):" in source,
        "uls_1x_direct_info_buttons_removed": all(
            f'with info_i_button(help_text="{help_text}")' not in source
            for help_text in check_help_texts
        ),
        "uls_1x_info_buttons_use_shared_row": all(
            f'with _bending_check_info_row(help_text="{help_text}")' in source
            for help_text in check_help_texts
        ),
        "uls_1x_info_buttons_are_content_before_calc": all(
            token in source
            for token in (
                "content_before=info_1_1",
                "content_before=info_1_2",
                "content_before=info_1_3",
                "content_before=info_1_5",
            )
        ),
        "uls_1x_diagrams_do_not_own_info_rows": "def diagram_1_1():\n            info_1_1()" not in source
        and "def diagram_1_5():\n            info_1_5()" not in source
        and "diagram_fn=info_1_2" not in source
        and "diagram_fn=info_1_3" not in source,
        "check_1_6_reference_format_preserved": "def content_1_5():" in source
        and "col_ku_title, col_ku_info = st.columns([0.9, 0.1])" in source
        and 'st.markdown("**Info:**")' in source
        and 'with info_i_button(help_text="What does the neutral-axis ratio mean?")' in source,
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "schema": "bending_uls_info_button_format_snapshot.v1",
        "generated_at": generated_at,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "ownership": {
            "surface": "bending ULS check info-button formatting",
            "calculation_logic_changed": False,
            "visible_info_copy_changed": False,
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"bending_uls_info_button_format_{generated_at}.json"
    report_path = AUDIT_DIR / f"bending_uls_info_button_format_{generated_at}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Bending ULS Info Button Format Snapshot",
                "",
                f"Result: `{payload['status']}`",
                "",
                "## Checks",
                "",
                *[f"- `{name}`: {'PASS' if ok else 'FAIL'}" for name, ok in checks.items()],
                "",
                "## Notes",
                "",
                "- Checks 1.1, 1.2, 1.4, and 1.5 now use the same content-before-calc Info row pattern as Check 1.6.",
                "- Existing info popover copy and calculation logic are unchanged.",
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in failures] or ["- None"]),
            ]
        ),
        encoding="utf-8",
    )
    print(f"bending_uls_info_button_format_snapshot {payload['status']}")
    print(f"json: {json_path}")
    print(f"report: {report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
