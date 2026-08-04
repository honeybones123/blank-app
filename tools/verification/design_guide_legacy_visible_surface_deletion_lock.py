"""Lock retired visible Design Guide/Input legacy surfaces.

This verifier does not delete code while it runs.  It proves that specific
legacy visible surfaces have already been removed or reduced to non-rendering
compatibility hooks, so they cannot quietly come back in later edits.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _check_absent(source: str, tokens: tuple[str, ...]) -> list[str]:
    return [token for token in tokens if token in source]


def main() -> int:
    landing = _read("inputs_page_modules/landing.py")
    current = _read("inputs_page_modules/design_guide/current_coordinators.py")

    checks: dict[str, Any] = {
        "current_inputs_landing_card_is_explicit_supported_surface": all(
            token in landing
            for token in (
                "def render_inputs_landing_card(",
                "inputs-landing-wrap",
                "Go to Design Inputs",
                "Open Design Mode",
                "st_module.button(",
            )
        ),
        "retired_inputs_landing_card_markup_is_not_misclassified": not _check_absent(
            landing,
            ("Retired visible landing card",),
        ),
        "legacy_advisory_secondary_panel_deleted": "Recommendation is advisory, not directly executable"
        not in current,
        "legacy_one_click_feedback_not_rendered_as_warning_or_info": (
            "st.warning(message)" not in current and "st.info(message)" not in current
        ),
        "legacy_one_click_feedback_is_debug_only_if_present": (
            "One-click found a candidate" not in current
            or (
                "design_guide_legacy_one_click_feedback_suppressed" in current
                and "st.warning(message)" not in current
                and "st.info(message)" not in current
            )
        ),
        "legacy_advisory_state_is_non_authoritative": (
            "design_guide_legacy_advisory_panel_suppressed" in current
            and "design_guide_legacy_advisory_panel_reason" in current
        ),
    }
    failures = [name for name, passed in checks.items() if not passed]
    status = "PASS" if not failures else "FAIL"
    timestamp = _stamp()

    payload = {
        "schema": "design_guide_legacy_visible_surface_deletion_lock.v1",
        "status": status,
        "timestamp": timestamp,
        "checks": checks,
        "failures": failures,
        "deleted_or_retired_surfaces": [
            {
                "surface": "inputs_landing_card",
                "file": "inputs_page_modules/landing.py",
                "state": "current supported empty-input navigation surface; not a deletion candidate",
            },
            {
                "surface": "legacy_design_guide_advisory_secondary_panel",
                "file": "inputs_page_modules/design_guide/current_coordinators.py",
                "state": "visible panel removed; reason retained as non-authoritative debug metadata",
            },
            {
                "surface": "legacy_one_click_feedback_warning_info_banner",
                "file": "inputs_page_modules/design_guide/current_coordinators.py",
                "state": "visible st.warning/st.info removed; message retained as non-authoritative debug metadata",
            },
        ],
        "verifier_deletes_code": False,
        "enforcement_model": "fail_if_legacy_visible_surface_returns",
        "product_behaviour_changed": "visible legacy surfaces retired by request",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACT_DIR / f"design_guide_legacy_visible_surface_deletion_lock_{timestamp}.json"
    md_path = AUDIT_DIR / f"design_guide_legacy_visible_surface_deletion_lock_{timestamp}.md"
    payload["artifact"] = str(json_path)
    payload["report"] = str(md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                "# Design Guide Legacy Visible Surface Deletion Lock",
                "",
                f"Status: `{status}`",
                "",
                "This verifier does not delete code during verification. It fails if the retired visible legacy surfaces return.",
                "",
                "## Checks",
                *[f"- `{name}`: `{passed}`" for name, passed in checks.items()],
                "",
                "## Retired Surfaces",
                *[
                    f"- `{row['surface']}` in `{row['file']}`: {row['state']}"
                    for row in payload["deleted_or_retired_surfaces"]
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"design_guide_legacy_visible_surface_deletion_lock {status}")
    print(f"json={json_path}")
    print(f"report={md_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
