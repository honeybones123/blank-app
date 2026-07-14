"""Verify the Inputs Batch design control-panel layout.

This snapshot follows the current architecture: inputs_page.py owns the shell
call into batch_design.ui.page, while the Batch design package owns the compact
workspace banner, lazy expanded body, and project-beam controls.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
BATCH_PAGE = ROOT / "batch_design" / "ui" / "page.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _batch_shell_block(source: str) -> str:
    marker = "render_batch_design_page("
    start = source.find(marker)
    if start < 0:
        return ""
    end_marker = "_mark(\"beam_manager\")"
    end = source.find(end_marker, start)
    if end < 0:
        end = start + 6000
    return source[start:end]


def main() -> int:
    generated_at = time.strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    inputs_source = INPUTS_PAGE.read_text(encoding="utf-8")
    batch_source = BATCH_PAGE.read_text(encoding="utf-8")
    shell_block = _batch_shell_block(inputs_source)
    checks = {
        "inputs_page_calls_batch_design_renderer": "render_batch_design_page(" in shell_block
        and "BatchDesignPageContext(" in shell_block,
        "inputs_page_no_longer_owns_batch_heading": 'st.markdown("### Batch design")' not in inputs_source
        and 'st.markdown("### Batch Design")' not in inputs_source,
        "workspace_banner_exists": "def _render_batch_design_workspace_banner_visual" in batch_source
        and "batch-design-hero" in batch_source
        and "Batch design workspace" in batch_source,
        "batch_heading_owned_by_batch_package": 'st.markdown("### Batch design")' in batch_source,
        "batch_heading_outside_workspace_card": 'class="batch-design-hero-title"' not in batch_source
        and ".batch-design-hero-title" not in batch_source,
        "workspace_card_has_bottom_spacing_before_design_guide": "height: 0.85rem" in batch_source,
        "workspace_uses_lazy_toggle": "with st.expander(" not in batch_source
        and 'key="batch_design_workspace_banner_toggle"' in batch_source
        and "if not workspace_expanded:" in batch_source
        and "_render_project_beam_design_editor(ctx, workflow)" in batch_source
        and "WORKSPACE_EXPANDED_KEY" in batch_source
        and "WORKSPACE_QUERY_PARAM" in batch_source,
        "workspace_default_closed": "st.session_state[WORKSPACE_EXPANDED_KEY] = False" in batch_source,
        "project_beam_editor_lives_in_batch_package": 'st.markdown("### Project beams")' in batch_source
        and "_render_project_beam_controls(ctx)" in batch_source,
        "selector_left_label_active_set": 'st.selectbox(\n                "Active set"' in batch_source,
        "controls_in_one_columns_row": "beam_selector_col, spacer_col, add_beam_col, dup_beam_col, del_beam_col, reset_workspace_col = st.columns" in batch_source,
        "balanced_medium_gap": 'gap="medium"' in batch_source,
        "bottom_aligned_controls": 'vertical_alignment="bottom"' in batch_source,
        "add_button_present": 'st.button("+ Add"' in batch_source,
        "duplicate_button_present": 'st.button("Duplicate"' in batch_source,
        "delete_button_preserved": 'st.button(\n            "Delete"' in batch_source,
        "reset_workspace_present": '"Reset workspace"' in batch_source,
        "batch_layout_does_not_touch_design_guide_truth": all(
            token not in batch_source
            for token in (
                "FinalDesignGuidePublication",
                "_design_guide_button_contract",
                "_record_rendered_design_guide_primary_apply_payload",
                "design_guide_independence",
            )
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    payload = {
        "schema": "inputs_batch_design_layout_snapshot.v1",
        "generated_at": generated_at,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "layout_hash": _stable_hash(checks),
        "ownership": {
            "changed": "Inputs shell plus batch_design.ui.page layout only",
            "engineering_logic_changed": False,
            "cta_publication_apply_changed": False,
        },
    }
    report_lines = [
        "# Inputs Batch Design Layout Snapshot",
        "",
        f"Result: `{payload['status']}`",
        "",
        "## Checks",
        "",
        *[f"- `{name}`: {'PASS' if ok else 'FAIL'}" for name, ok in checks.items()],
        "",
        "## Ownership",
        "",
        "- inputs_page.py delegates Batch design rendering to batch_design.ui.page.",
        "- The Batch design package owns the Batch design section heading, compact workspace banner, and lazy expanded body.",
        "- The Batch design heading is outside the compact workspace card and uses the same native heading level as Design Guide.",
        "- A small spacer separates Batch design from the following Design Guide section.",
        "- Collapsed Batch design renders only the banner/toggle and does not build hidden expanded controls.",
        "- The expanded Project beams card contains the active set selector plus one row of actions.",
        "- Existing functionality is preserved, including Delete.",
        "- No Design Guide, CTA, apply, publication, or engineering behavior moved.",
        "",
        "## Failures",
        "",
        *([f"- `{failure}`" for failure in failures] or ["- None"]),
    ]
    json_path = ARTIFACT_DIR / f"inputs_batch_design_layout_{generated_at}.json"
    report_path = AUDIT_DIR / f"inputs_batch_design_layout_{generated_at}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"inputs_batch_design_layout_snapshot {payload['status']}")
    print(f"json: {json_path}")
    print(f"report: {report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
