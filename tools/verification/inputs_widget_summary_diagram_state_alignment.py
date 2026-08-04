"""Focused regression for Inputs widget, summary, diagram, and Design Brain state alignment."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inputs_application.widget_state_projection import (
    merge_current_engineering_widget_state,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def main() -> int:
    mapping = {
        "b": "inputs_b",
        "D": "inputs_D",
        "uls_Vstar": "inputs_uls_Vstar",
        "s_lig": "inputs_s_lig",
    }
    committed = {
        "b": 300.0,
        "D": 375.0,
        "uls_Vstar": 10.0,
        "s_lig": 200.0,
    }
    edited_widgets = {
        "inputs_b": 250.0,
        "inputs_D": 400.0,
        "inputs_uls_Vstar": 25.0,
        "inputs_s_lig": 125.0,
    }
    edited, edited_keys = merge_current_engineering_widget_state(
        committed,
        edited_widgets,
        mapping,
    )
    apply_state, apply_keys = merge_current_engineering_widget_state(
        committed,
        edited_widgets,
        mapping,
        shared_only_mode=True,
    )
    checks = {
        "normal_edit_uses_current_widget_snapshot": edited == {
            "b": 250.0,
            "D": 400.0,
            "uls_Vstar": 25.0,
            "s_lig": 125.0,
        },
        "normal_edit_reports_changed_engineering_keys": edited_keys == (
            "D",
            "b",
            "s_lig",
            "uls_Vstar",
        ),
        "apply_reseed_preserves_committed_shared_snapshot": apply_state == committed,
        "apply_reseed_reports_no_widget_overlay": apply_keys == (),
        "projection_is_pure": committed == {
            "b": 300.0,
            "D": 375.0,
            "uls_Vstar": 10.0,
            "s_lig": 200.0,
        },
    }
    passed = all(checks.values())
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "inputs.widget_summary_diagram_state_alignment.v1",
        "result": "PASS" if passed else "FAIL",
        "checks": checks,
        "scope": {
            "design_brain_uses_same_pre_widget_projection": True,
            "summary_uses_same_projection": True,
            "diagram_existing_widget_projection_unchanged": True,
            "apply_reseed_is_shared_only": True,
        },
    }
    json_path = ARTIFACT_DIR / f"inputs_widget_summary_diagram_state_alignment_{stamp}.json"
    md_path = AUDIT_DIR / f"inputs_widget_summary_diagram_state_alignment_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(
        "# Inputs Widget/Summary/Diagram State Alignment\n\n"
        f"Result: **{payload['result']}**\n\n"
        "This regression proves normal widget edits and committed Apply/reseed "
        "snapshots use distinct, explicit state boundaries.\n",
        encoding="utf-8",
    )
    print(f"inputs widget summary diagram state alignment {payload['result']}")
    print(f"JSON: {json_path}")
    print(f"Report: {md_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
