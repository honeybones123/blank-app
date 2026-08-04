from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
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
    state_text = STATE_AND_HELPERS.read_text(encoding="utf-8")

    constraints_body = _function_body(inputs_text, "_render_design_guide_constraints_panel")
    geometry_lock_body = _function_body(inputs_text, "_geometry_lock_enabled")
    width_lock_body = _function_body(inputs_text, "_geometry_width_lock_enabled")
    depth_lock_body = _function_body(inputs_text, "_geometry_depth_lock_enabled")
    migration_body = _function_body(inputs_text, "_migrate_geometry_master_lock_to_axis_locks_once")
    sync_body = _function_body(inputs_text, "_sync_geometry_master_lock_from_axis_locks")

    defaults_start = state_text.find("SHARED_DEFAULTS = {")
    defaults_end = state_text.find("# Materials", defaults_start)
    defaults_block = state_text[defaults_start:defaults_end] if defaults_start >= 0 else ""

    tab_keys_start = state_text.find("TAB_KEYS = {")
    tab_keys_end = state_text.find("# ----------------- BENDING PAGE", tab_keys_start)
    tab_keys_block = state_text[tab_keys_start:tab_keys_end] if tab_keys_start >= 0 else ""

    constraints_call = inputs_text.find("_render_design_guide_constraints_panel(sync_callbacks, include_heading=True)")
    placeholder_call = inputs_text.find("design_guide_page.render_pre_widget_placeholder")
    info_button_index = constraints_body.find("with info_i_button(")
    first_toggle_index = constraints_body.find("_shared_toggle(")

    checks = {
        "constraints_ui_is_info_popover_not_card": (
            "with info_i_button(" in constraints_body
            and "st.container(border=True)" not in constraints_body
        ),
        "constraints_ui_is_button_only_header_control": (
            "constraints_col, _ = st.columns([1.55, 0.35, 8.0]" in constraints_body
            and "_, constraints_col = st.columns([8.0, 0.35]" in constraints_body
            and 'st.caption(f"Constraints: {status_text}")' not in constraints_body
            and 'st.caption("Constraints: none")' not in constraints_body
            and "status_text" not in constraints_body
            and "Design Guide constraints: locked axes" not in constraints_body
        ),
        "constraints_ui_renders_above_design_guide_placeholder": (
            constraints_call >= 0
            and placeholder_call >= 0
            and constraints_call < placeholder_call
        ),
        "width_and_depth_lock_shared_defaults_exist": (
            '"optimisation_lock_width": False' in defaults_block
            and '"optimisation_lock_depth": False' in defaults_block
        ),
        "width_and_depth_lock_widget_mappings_exist": (
            '"inputs_optimisation_lock_width": "optimisation_lock_width"' in tab_keys_block
            and '"inputs_optimisation_lock_depth": "optimisation_lock_depth"' in tab_keys_block
        ),
        "constraints_ui_has_axis_toggles": (
            '"Lock width"' in constraints_body
            and '"Lock depth"' in constraints_body
            and '"inputs_optimisation_lock_width"' in constraints_body
            and '"inputs_optimisation_lock_depth"' in constraints_body
        ),
        "axis_toggles_are_inside_info_popover": (
            info_button_index >= 0
            and first_toggle_index >= 0
            and info_button_index < first_toggle_index
        ),
        "master_geometry_lock_includes_both_axis_locks": (
            '"optimisation_lock_width"' in geometry_lock_body
            and '"optimisation_lock_depth"' in geometry_lock_body
            and "and" in geometry_lock_body
        ),
        "axis_lock_helpers_exist": (
            '"optimisation_lock_width"' in width_lock_body
            and '"optimisation_lock_depth"' in depth_lock_body
        ),
        "old_master_lock_migrates_to_axis_locks_once": (
            "axis-locks-v1" in migration_body
            and 'st.session_state[shared_key] = True' in migration_body
            and 'st.session_state[widget_key] = True' in migration_body
        ),
        "axis_locks_sync_legacy_master_when_both_locked": (
            "master_locked = bool(width_locked and depth_locked)" in sync_body
            and 'st.session_state["optimisation_lock_geometry"] = master_locked' in sync_body
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    payload = {
        "status": status,
        "checks": checks,
        "locations": {
            "constraints_panel_line": _line_number(inputs_text, "def _render_design_guide_constraints_panel"),
            "geometry_lock_line": _line_number(inputs_text, "def _geometry_lock_enabled"),
            "state_defaults_line": _line_number(state_text, '"optimisation_lock_width": False'),
            "tab_keys_line": _line_number(state_text, '"inputs_optimisation_lock_width": "optimisation_lock_width"'),
        },
        "scope": {
            "ui_change": "Design Guide constraints render as an info popover button above the Design Guide; the visible constraints caption is removed.",
            "state_change": "Width and depth locks are shared state; locking both activates the legacy fixed-geometry gate.",
            "not_proven": "Axis-specific family ladder behavior still needs separate contract/runtime wiring before claiming width-only or depth-only authority.",
        },
    }

    ARTIFACTS_VERIFICATION.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_AUDITS.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_VERIFICATION / f"design_guide_constraints_info_tab_{now}.json"
    report_path = ARTIFACTS_AUDITS / f"design_guide_constraints_info_tab_{now}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    report_lines = [
        "# Design Guide Constraints Info Tab Snapshot",
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
