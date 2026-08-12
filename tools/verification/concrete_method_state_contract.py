"""Verify selectable concrete methods participate in shared project state."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import state_and_helpers as state  # noqa: E402


def main() -> None:
    required_defaults = {
        "crack_control_method": "existing_as3600",
        "shrinkage_method": "existing_as3600",
        "crack_wall_thickness_mm": 600.0,
        "crack_c766_restraint_type": "continuous_edge",
        "shrinkage_relative_humidity_percent": 51.0,
    }
    for key, expected in required_defaults.items():
        assert state.SHARED_DEFAULTS[key] == expected
        assert key in state.BEAM_PROJECT_PARAM_KEYS

    required_widget_mappings = {
        "crack_method": "crack_control_method",
        "crack_wall_thickness": "crack_wall_thickness_mm",
        "crack_c766_restraint": "crack_c766_restraint_type",
        "sh_method": "shrinkage_method",
        "sh_rh": "shrinkage_relative_humidity_percent",
    }
    for widget_key, shared_key in required_widget_mappings.items():
        assert state.TAB_KEYS[widget_key] == shared_key

    print("PASS: concrete method defaults and project-state mappings")


if __name__ == "__main__":
    main()
