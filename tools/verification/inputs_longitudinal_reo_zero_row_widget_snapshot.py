from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
WIDGETS_HELPERS = ROOT / "widgets_helpers.py"
STATE_AND_HELPERS = ROOT / "state_and_helpers.py"
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


def _line_number(text: str, needle: str) -> int | None:
    index = text.find(needle)
    if index < 0:
        return None
    return text[:index].count("\n") + 1


def main() -> int:
    inputs_text = INPUTS_PAGE.read_text(encoding="utf-8")
    widgets_text = WIDGETS_HELPERS.read_text(encoding="utf-8")
    state_text = STATE_AND_HELPERS.read_text(encoding="utf-8")

    row_config_body = _function_body(widgets_text, "render_longitudinal_reo_row_config_controls")
    sync_body = _function_body(widgets_text, "_longitudinal_reo_sync_row_count_state")
    state_rows_body = _function_body(state_text, "get_longitudinal_row_inputs")
    zero_allowed_body = _function_body(state_text, "zero_allowed")
    overlay_body = _function_body(inputs_text, "_overlay_inputs_reo_widget_mirrors_for_model")
    zero_widget_options_body = _function_body(
        inputs_text,
        "_ensure_inputs_longitudinal_reo_zero_row_widget_options",
    )

    nonzero_block_start = state_text.find("NONZERO_REQUIRED_SHARED_KEYS = {")
    nonzero_block_end = state_text.find("ZERO_ALLOWED_SHARED_KEYS = {", nonzero_block_start)
    nonzero_block = state_text[nonzero_block_start:nonzero_block_end] if nonzero_block_start >= 0 else ""

    zero_block_start = state_text.find("ZERO_ALLOWED_SHARED_KEYS = {")
    zero_block_end = state_text.find("def zero_allowed", zero_block_start)
    zero_block = state_text[zero_block_start:zero_block_end] if zero_block_start >= 0 else ""

    zero_options_call = inputs_text.find("_ensure_inputs_longitudinal_reo_zero_row_widget_options()")
    row_config_call = inputs_text.find("render_longitudinal_reo_row_config_controls(")

    checks = {
        "rows_select_includes_zero": "list(range(0, max_rows + 1))" in row_config_body,
        "row_count_sync_clamps_to_zero_minimum": "max(0, min(max_rows, current_row_count))" in sync_body,
        "row_count_change_clamps_to_zero_minimum": "max(0, min(max_rows, new_count))" in row_config_body,
        "rowgap_disabled_for_zero_or_one_rows": "disabled=n_for_gap < 2" in row_config_body,
        "shared_zero_allowed_includes_row_counts": (
            '"bot_row_count", "top_row_count"' in zero_block
            or '"top_row_count", "bot_row_count"' in zero_block
        ),
        "shared_nonzero_required_excludes_row_counts": (
            '"bot_row_count"' not in nonzero_block and '"top_row_count"' not in nonzero_block
        ),
        "zero_allowed_no_longer_rejects_row_counts": (
            'shared_key in {"top_row_count", "bot_row_count"}' not in zero_allowed_body
        ),
        "row_input_model_allows_zero_visible_rows": (
            "row_count = max(0, min(LONGITUDINAL_REO_MAX_ROWS" in state_rows_body
        ),
        "inputs_overlay_preserves_zero_row_count": (
            "lambda value: max(0, int(float(value or 0)))" in overlay_body
        ),
        "inputs_coords_staleness_allows_zero_row_count": (
            'row_count = max(0, int(float(working.get(f"{section}_row_count", 1) or 0)))' in overlay_body
        ),
        "live_widget_options_version_reset_exists": (
            "_LONGITUDINAL_REO_ZERO_ROW_WIDGET_OPTIONS_VERSION" in inputs_text
            and "zero-row-v1" in inputs_text
        ),
        "live_widget_options_reset_clears_only_widget_keys": (
            'ss.pop(widget_key, None)' in zero_widget_options_body
            and 'ss.pop(f"_cached_{widget_key}", None)' in zero_widget_options_body
            and "preserved_shared[shared_key]" in zero_widget_options_body
        ),
        "live_widget_options_reset_runs_before_row_config_render": (
            zero_options_call >= 0
            and row_config_call >= 0
            and zero_options_call < row_config_call
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    payload = {
        "status": status,
        "checks": checks,
        "locations": {
            "widgets_row_config_line": _line_number(widgets_text, "def render_longitudinal_reo_row_config_controls"),
            "widgets_row_count_sync_line": _line_number(widgets_text, "def _longitudinal_reo_sync_row_count_state"),
            "state_zero_allowed_line": _line_number(state_text, "def zero_allowed"),
            "state_get_longitudinal_row_inputs_line": _line_number(state_text, "def get_longitudinal_row_inputs"),
            "inputs_overlay_line": _line_number(inputs_text, "def _overlay_inputs_reo_widget_mirrors_for_model"),
            "inputs_zero_row_widget_options_line": _line_number(
                inputs_text,
                "def _ensure_inputs_longitudinal_reo_zero_row_widget_options",
            ),
        },
        "scope": {
            "allowed_user_intent": "bot/top longitudinal Rows may be 0 to represent no active row",
            "engineering_truth": "checks still decide whether a zero-row design fails or needs repair",
        },
    }

    ARTIFACTS_VERIFICATION.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_VERIFICATION / f"inputs_longitudinal_reo_zero_row_widget_{now}.json"
    report_path = ARTIFACTS_AUDITS / f"inputs_longitudinal_reo_zero_row_widget_{now}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    report_lines = [
        "# Inputs Longitudinal REO Zero Row Widget Snapshot",
        "",
        f"Status: `{status}`",
        "",
        "## Checks",
    ]
    for key, value in checks.items():
        report_lines.append(f"- `{key}`: `{bool(value)}`")
    report_lines.extend(["", "## Scope"])
    for key, value in payload["scope"].items():
        report_lines.append(f"- `{key}`: {value}")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": status, "json": str(json_path), "report": str(report_path)}, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
