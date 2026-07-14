"""Design Guide display tone contract snapshot.

Proof-only verifier for the visible colour contract:

- fail/repair states render red
- pass/accepted states render green
- optimisation/overdesign states render blue

This verifier checks the contract, the rendered HTML class shape, and the CSS
selectors that prevent actionable fail cards from inheriting the generic blue
action pill styling. It does not execute family runtimes, route CTA/apply
payloads, or change product behaviour.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.display_formatting_contract import status_colour_contract  # noqa: E402
from design_brain.final_design_guide_formatter import (  # noqa: E402
    FinalDesignGuideCardFormat,
    FinalDesignGuideFormatSection,
    resolve_final_design_guide_status_tone,
)
from ui.final_design_guide_card import render_final_design_guide_card_html  # noqa: E402


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
STYLE_PATH = ROOT / "ui" / "inputs_page_style.py"


def _stable_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()


def _stamp() -> str:
    return time.strftime("%Y-%m-%dT%H-%M-%S")


def _render_case(*, name: str, status: str, pill: str, card_class: str) -> dict[str, Any]:
    tone = "grey"
    if "fail" in card_class:
        tone = "red"
    elif "efficiency" in card_class:
        tone = "blue"
    elif "pass" in card_class:
        tone = "green"
    outcome = "ACTION" if status == "action" else "PASS" if status == "pass" else status.upper()
    model = FinalDesignGuideCardFormat(
        selected_family=name,
        outcome_state=outcome,
        tone=tone,
        tone_source="synthetic_display_tone_contract",
        title=f"{name} card",
        badge=pill,
        summary="Synthetic display tone contract case.",
        blocker_explanation="",
        governing_label="Governing utilisation 1.12" if status == "action" else "All checks pass",
        sections=(
            FinalDesignGuideFormatSection(
                "Current",
                (
                    {"family": "bending", "label": "Bending", "value": "1.12", "status": "FAIL", "tone": "red"},
                    {"family": "shear", "label": "Shear", "value": "0.82", "status": "PASS", "tone": "green"},
                ),
                True,
            ),
            FinalDesignGuideFormatSection(
                "Status",
                ({"test_label": "result", "label": "Result", "text": "Synthetic case."},),
                True,
            ),
        ),
        publication_hash=f"{name}:publication",
        display_hash=f"{name}:display",
        cta_hash=f"{name}:cta",
        evidence_hash=f"{name}:evidence",
        contract_hash=f"{name}:contract",
        format_hash=f"{name}:format",
    )
    html = render_final_design_guide_card_html(model)
    return {
        "name": name,
        "status": status,
        "pill": pill,
        "card_class": card_class,
        "html_hash": _stable_hash(html),
        "has_expected_card_classes": all(token in html for token in card_class.split()),
        "has_status_class": f"dg-card--{status}" in html,
        "has_status_pill": f"dg-status-pill--{status}" in html,
        "has_util_pill": "dg-util-pill" in html,
        "html_sample": html[:900],
    }


def _selector_present(style: str, selector: str) -> bool:
    pattern = re.escape(selector).replace(r"\ ", r"\s+")
    return bool(re.search(pattern, style))


def _write(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    json_path = ARTIFACT_DIR / f"design_guide_display_tone_contract_{stamp}.json"
    report_path = AUDIT_DIR / f"design_guide_display_tone_contract_{stamp}.md"
    snapshot["artifact"] = str(json_path)
    snapshot["report"] = str(report_path)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Design Guide Display Tone Contract Snapshot",
        "",
        f"Result: `{snapshot['result']}`",
        "",
        "## Contract",
        "",
        "- Fail / repair states: red.",
        "- Pass / accepted states: green.",
        "- Optimisation / overdesign states: blue.",
        "",
        "## Checks",
        "",
    ]
    for key, value in snapshot["checks"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Failures", ""])
    lines.extend([f"- `{failure}`" for failure in snapshot["failures"]] or ["- none"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, report_path


def main() -> int:
    style = STYLE_PATH.read_text(encoding="utf-8", errors="replace")
    colour_contract = status_colour_contract()
    red_families = {str(value) for value in dict(colour_contract.get("RED") or {}).get("families") or ()}
    blue_families = {str(value) for value in dict(colour_contract.get("BLUE") or {}).get("families") or ()}
    green_families = {str(value) for value in dict(colour_contract.get("GREEN") or {}).get("families") or ()}

    fail_action = _render_case(
        name="fail_action",
        status="action",
        pill="ACTION",
        card_class="fast-guidance-item fail",
    )
    optimise_action = _render_case(
        name="optimise_action",
        status="action",
        pill="ACTION",
        card_class="fast-guidance-item efficiency",
    )
    pass_case = _render_case(
        name="pass",
        status="pass",
        pill="PASS",
        card_class="fast-guidance-item pass guidance-success",
    )

    required_selectors = {
        "fail_action_card_red": ".fast-guidance-item.fail.dg-card--action",
        "fail_blocked_card_red": ".fast-guidance-item.fail.dg-card--blocked",
        "fail_action_pill_red": ".fast-guidance-item.fail .dg-status-pill--action",
        "fail_blocked_pill_red": ".fast-guidance-item.fail .dg-status-pill--blocked",
        "fail_action_util_red": ".fast-guidance-item.fail.dg-card--action .dg-util-pill",
        "fail_blocked_util_red": ".fast-guidance-item.fail.dg-card--blocked .dg-util-pill",
        "pass_card_green": ".dg-card--pass",
        "pass_pill_green": ".dg-status-pill--pass",
        "generic_action_blue": ".dg-card--action",
        "generic_action_pill_blue": ".dg-status-pill--action",
    }
    selector_checks = {key: _selector_present(style, selector) for key, selector in required_selectors.items()}

    red_css = "#e03131"
    green_css = "#2f9e44"
    blue_css = "#4263eb"
    checks = {
        "contract_has_red_green_blue": {"RED", "GREEN", "BLUE"}.issubset(set(colour_contract)),
        "red_contract_has_fail_families": bool(
            red_families
            & {
                "BENDING_FAIL_GOVERNS",
                "SHEAR_FAIL_GOVERNS",
                "BENDING_AND_SHEAR_FAIL_GOVERN",
                "GEOMETRY_DETAILING_GOVERNS",
            }
        ),
        "blue_contract_has_optimise_families": bool(
            blue_families
            & {
                "BENDING_OVERDESIGN_GOVERNS",
                "SHEAR_OVERDESIGN_GOVERNS",
                "COMBINED_OVERDESIGN",
                "COMBINED_OVERDESIGN_GOVERNS",
            }
        ),
        "green_contract_has_pass_families": bool(green_families & {"TARGET_BAND_REACHED", "EXACT_STOP_PROVEN"}),
        "tone_helper_fail_red": resolve_final_design_guide_status_tone("FAIL") == "red",
        "tone_helper_pass_green": resolve_final_design_guide_status_tone("PASS") == "green",
        "tone_helper_warn_amber": resolve_final_design_guide_status_tone("WARNING") == "amber",
        "fail_action_html_shape": fail_action["has_expected_card_classes"]
        and fail_action["has_status_class"]
        and fail_action["has_status_pill"]
        and fail_action["has_util_pill"],
        "optimise_action_html_shape": optimise_action["has_expected_card_classes"]
        and optimise_action["has_status_class"]
        and optimise_action["has_status_pill"]
        and optimise_action["has_util_pill"],
        "pass_html_shape": pass_case["has_expected_card_classes"]
        and pass_case["has_status_class"]
        and pass_case["has_status_pill"],
        "css_contains_red": red_css in style,
        "css_contains_green": green_css in style,
        "css_contains_blue": blue_css in style,
        **selector_checks,
        "no_cta_apply_routing_in_style": "apply routing" not in style.lower() and "one_click" not in style.lower(),
    }
    failures = [key for key, passed in checks.items() if not passed]
    snapshot = {
        "schema": "design_guide_display_tone_contract_snapshot.v1",
        "result": "PASS" if not failures else "FAIL",
        "style_path": str(STYLE_PATH),
        "checks": checks,
        "required_selectors": required_selectors,
        "contract_family_counts": {
            "RED": len(red_families),
            "BLUE": len(blue_families),
            "GREEN": len(green_families),
        },
        "cases": {
            "fail_action": fail_action,
            "optimise_action": optimise_action,
            "pass": pass_case,
        },
        "failures": failures,
    }
    json_path, report_path = _write(snapshot)
    if failures:
        print("Design Guide display tone contract FAIL")
        print(f"JSON: {json_path}")
        print(f"Report: {report_path}")
        return 1
    print("Design Guide display tone contract PASS")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
