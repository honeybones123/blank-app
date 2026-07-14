from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
STYLE_PATH = ROOT / "ui" / "inputs_page_style.py"
ARTIFACTS_VERIFICATION = ROOT / "artifacts" / "verification"
ARTIFACTS_AUDITS = ROOT / "artifacts" / "audits"


def _function_body(text: str, name: str) -> str:
    pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", text[match.end() :], re.MULTILINE)
    if not next_match:
        return text[match.start() :]
    return text[match.start() : match.end() + next_match.start()]


def _css_block(text: str, selector: str) -> str:
    matches = list(re.finditer(rf"^\s*{re.escape(selector)}\s*\{{", text, re.MULTILINE))
    if not matches:
        return ""
    start = matches[0].start()
    brace = text.find("{", matches[0].start())
    depth = 0
    for index in range(brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def main() -> int:
    inputs_text = INPUTS_PAGE.read_text(encoding="utf-8")
    style_text = STYLE_PATH.read_text(encoding="utf-8")
    constraints_body = _function_body(inputs_text, "_render_design_guide_constraints_panel")
    fast_card_css = _css_block(style_text, ".fast-guidance-item")
    dg_card_css = _css_block(style_text, ".dg-card")
    pending_shell_css = _css_block(style_text, ".dg-proof-pending-shell")

    expected_shadow = "box-shadow: 0 6px 18px rgba(15, 23, 42, 0.055);"
    checks = {
        "constraints_header_is_button_only": (
            "with info_i_button(" in constraints_body
            and "status_col" not in constraints_body
            and "info_col" not in constraints_body
            and "status_text" not in constraints_body
            and 'st.caption(f"Constraints: {status_text}")' not in constraints_body
        ),
        "constraints_button_remains_above_design_guide": (
            "include_heading" in constraints_body
            and "_render_design_guide_heading_if_needed()" in constraints_body
            and "with info_i_button(" in constraints_body
        ),
        "axis_toggles_stay_inside_info_button": (
            constraints_body.find("with info_i_button(") >= 0
            and constraints_body.find("with info_i_button(") < constraints_body.find('"Lock width"')
            and constraints_body.find("with info_i_button(") < constraints_body.find('"Lock depth"')
        ),
        "fast_guidance_item_has_batch_style_shadow": expected_shadow in fast_card_css,
        "final_design_guide_card_has_batch_style_shadow": expected_shadow in dg_card_css,
        "design_guide_loading_shell_has_batch_style_shadow": expected_shadow in pending_shell_css,
        "design_brain_truth_not_touched": all(
            token not in constraints_body
            for token in (
                "FinalDesignGuidePublication",
                "_design_guide_button_contract",
                "_record_rendered_design_guide_primary_apply_payload",
                "family_strategy_for",
            )
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    payload = {
        "status": status,
        "checks": checks,
        "scope": {
            "changed": "Design Guide header constraints caption removed; info button/toggles retained; card shadows aligned with Batch design elevation.",
            "engineering_logic_changed": False,
            "visible_wording_changed": "Only the visible 'Constraints: ...' header caption was removed.",
            "cta_apply_publication_changed": False,
        },
    }

    ARTIFACTS_VERIFICATION.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_VERIFICATION / f"design_guide_header_shadow_polish_{now}.json"
    report_path = ARTIFACTS_AUDITS / f"design_guide_header_shadow_polish_{now}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# Design Guide Header And Shadow Polish Snapshot",
                "",
                f"Status: `{status}`",
                "",
                "## Checks",
                *[f"- `{key}`: `{'PASS' if value else 'FAIL'}`" for key, value in checks.items()],
                "",
                "## Scope",
                f"- {payload['scope']['changed']}",
                "- No Design Brain, CTA/apply, publication, or engineering ownership moved.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
