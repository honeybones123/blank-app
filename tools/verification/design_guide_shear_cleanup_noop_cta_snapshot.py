from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
ARTIFACTS_VERIFICATION = ROOT / "artifacts" / "verification"
ARTIFACTS_AUDITS = ROOT / "artifacts" / "audits"


def _line_number(text: str, needle: str) -> int | None:
    index = text.find(needle)
    if index < 0:
        return None
    return text[:index].count("\n") + 1


def _function_body(text: str, name: str) -> str:
    pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\(", text[match.end() :], re.MULTILINE)
    if not next_match:
        return text[match.start() :]
    return text[match.start() : match.end() + next_match.start()]


def main() -> int:
    text = INPUTS_PAGE.read_text(encoding="utf-8")
    helper_body = _function_body(text, "_shear_best_safe_cleanup_item_from_evidence")
    widget_window_start = text.find('"No. of legs"')
    widget_window = text[widget_window_start : widget_window_start + 1200] if widget_window_start >= 0 else ""
    normaliser_body = _function_body(text, "_normalise_invalid_shear_state_updates")

    noop_guard_pos = helper_body.find("if _updates_match_state(state, updates):")
    evaluate_pos = helper_body.find("_evaluate_auto_design_candidate(")
    explicit_fail_pos = helper_body.find("_candidate_preview_statuses_have_explicit_fail")

    checks = {
        "best_safe_helper_exists": bool(helper_body),
        "best_safe_helper_blocks_noop_updates": noop_guard_pos >= 0,
        "noop_guard_before_preview_evaluation": noop_guard_pos >= 0 and evaluate_pos >= 0 and noop_guard_pos < evaluate_pos,
        "best_safe_helper_blocks_explicit_preview_fail": explicit_fail_pos >= 0,
        "best_safe_helper_requires_shear_update_keys": "_COMPOUND_SHEAR_UPDATE_KEYS" in helper_body,
        "zero_leg_widget_option_present": "[0] + list(range(2, 13))" in widget_window,
        "zero_leg_widget_uses_current_value": "int(lig_legs_val)" in widget_window,
        "zero_leg_normaliser_preserves_no_link_state": (
            'normalised_updates["lig_legs"] = 0' in normaliser_body
            and 'normalised_updates["lig_d"] = 0' in normaliser_body
            and "CANONICAL_NO_SHEAR_SLIG_MM" in normaliser_body
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    payload = {
        "status": status,
        "checks": checks,
        "locations": {
            "best_safe_helper_line": _line_number(text, "def _shear_best_safe_cleanup_item_from_evidence"),
            "noop_guard_line": _line_number(text, "if _updates_match_state(state, updates):"),
            "zero_leg_widget_line": _line_number(text, '"No. of legs"'),
            "shear_state_normaliser_line": _line_number(text, "def _normalise_invalid_shear_state_updates"),
        },
        "scope": {
            "product_behavior_changed": "no visible wording/layout changes; stale no-op cleanup CTA is refused before publication",
            "zero_leg_widget_policy": "0 remains an allowed explicit no-link option; active repair may still add links when shear demand requires them",
        },
    }

    ARTIFACTS_VERIFICATION.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_VERIFICATION / f"design_guide_shear_cleanup_noop_cta_{now}.json"
    report_path = ARTIFACTS_AUDITS / f"design_guide_shear_cleanup_noop_cta_{now}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    report_lines = [
        "# Design Guide Shear Cleanup No-Op CTA Snapshot",
        "",
        f"Status: `{status}`",
        "",
        "## Checks",
    ]
    for key, value in checks.items():
        report_lines.append(f"- `{key}`: `{bool(value)}`")
    report_lines.extend(["", "## Locations"])
    for key, value in payload["locations"].items():
        report_lines.append(f"- `{key}`: `{value}`")
    report_lines.extend(
        [
            "",
            "## Scope",
            "- Stale/no-op best-safe shear cleanup evidence cannot build an enabled CTA.",
            "- The explicit `0` no-link leg option remains present in the Inputs widget.",
        ]
    )
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
