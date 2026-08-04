"""Verify direct shell card projection is final-publication owned."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUTS_PAGE = ROOT / "inputs_page.py"
FINAL_PUBLICATION = ROOT / "design_brain" / "final_publication.py"
ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
REPORT_DIR = ROOT / "artifacts" / "reports"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from design_brain.final_publication import (  # noqa: E402
    build_final_design_guide_direct_shell_card_projection,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    start = source.find(f"def {name}(")
    if start < 0:
        return ""
    next_def = source.find("\ndef ", start + 1)
    if next_def < 0:
        return source[start:]
    return source[start:next_def]


def _scenario_rows() -> list[dict[str, Any]]:
    scenarios = [
        {
            "name": "bending_fail_active_strength_shell",
            "title": "Bending capacity is low",
            "candidate_family": "bending",
            "expected_util": 0.92,
            "preview_pass": True,
            "overview": {
                "utils": {"bending": 1.42, "shear": 0.82, "crack": 0.0, "deflection": 0.0},
                "statuses": {"bending": "FAIL", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
            },
            "identity": {
                "selected_family_id": "BENDING_FAIL_GOVERNS",
                "published_family_id": "BENDING_FAIL_GOVERNS",
                "cta_family_id": "BENDING_FAIL_GOVERNS",
                "updates": {"D": 650},
            },
            "expected": {
                "title": "Strengthening required",
                "card_class": "fast-guidance-item fail",
                "anchor_bucket": "fail",
                "bending_after_status": "PASS",
                "summary_line": "Bending capacity is failing. Run one-click auto design.",
            },
        },
        {
            "name": "shear_fail_active_strength_shell",
            "title": "Shear capacity is low",
            "candidate_family": "shear",
            "expected_util": 0.75,
            "preview_pass": True,
            "overview": {
                "utils": {"bending": 0.96, "shear": 1.23, "crack": 0.0, "deflection": 0.0},
                "statuses": {"bending": "PASS", "shear": "FAIL", "crack": "PASS", "deflection": "PASS"},
            },
            "identity": {
                "selected_family_id": "SHEAR_FAIL_GOVERNS",
                "published_family_id": "SHEAR_FAIL_GOVERNS",
                "cta_family_id": "SHEAR_FAIL_GOVERNS",
                "updates": {"lig_spacing": 150},
            },
            "expected": {
                "title": "Strengthening required",
                "card_class": "fast-guidance-item fail",
                "anchor_bucket": "fail",
                "shear_after_status": "PASS",
                "summary_line": "Shear capacity is failing. Run one-click auto design.",
            },
        },
        {
            "name": "passive_cleanup_shell",
            "title": "Design is safe - optional cleanup available",
            "candidate_family": "bending",
            "expected_util": 0.69,
            "preview_pass": True,
            "overview": {
                "utils": {"bending": 0.24, "shear": 0.69, "crack": 0.0, "deflection": 0.0},
                "statuses": {"bending": "PASS", "shear": "PASS", "crack": "PASS", "deflection": "PASS"},
            },
            "identity": {
                "selected_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "published_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "cta_family_id": "BENDING_OVERDESIGN_GOVERNS",
                "updates": {"N_bottom": 5},
            },
            "expected": {
                "title": "Design is safe - optional cleanup available",
                "card_class": "fast-guidance-item efficiency",
                "anchor_bucket": "efficiency",
                "bending_after_status": "PASS",
                "summary_line": "Run one-click auto design.",
            },
        },
    ]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        projection = build_final_design_guide_direct_shell_card_projection(
            title=scenario["title"],
            current_overview=dict(scenario["overview"]),
            candidate_family=scenario["candidate_family"],
            expected_util=scenario["expected_util"],
            preview_pass=scenario["preview_pass"],
            governing_label=None,
            family_identity=dict(scenario["identity"]),
            summary_line="Run one-click auto design.",
            reason_text="Run one-click auto design.",
        ).to_dict()
        vm = dict(projection.get("view_model") or {})
        preview = dict(vm.get("preview") or {})
        expected = dict(scenario["expected"])
        checks = {
            "title": vm.get("title") == expected.get("title"),
            "card_class": projection.get("card_class") == expected.get("card_class"),
            "anchor_bucket": projection.get("anchor_bucket") == expected.get("anchor_bucket"),
            "summary_line": vm.get("summary_line") == expected.get("summary_line"),
            "cta_enabled": dict(vm.get("cta") or {}).get("enabled") is True,
            "payload_id_present": bool(dict(vm.get("cta") or {}).get("payload_id")),
            "current_rows_four_families": len(list(vm.get("current") or [])) == 4,
        }
        for family in ("bending", "shear"):
            key = f"{family}_after_status"
            if key in expected:
                checks[key] = dict(preview.get(family) or {}).get("after_status") == expected[key]
        rows.append(
            {
                "name": scenario["name"],
                "checks": checks,
                "projection_hash": projection.get("projection_hash"),
                "active_strength_shell": projection.get("active_strength_shell"),
                "title": vm.get("title"),
                "card_class": projection.get("card_class"),
                "anchor_bucket": projection.get("anchor_bucket"),
            }
        )
    return rows


def _build_payload() -> dict[str, Any]:
    inputs_source = _read(INPUTS_PAGE)
    final_source = _read(FINAL_PUBLICATION)
    helper = _function_body(inputs_source, "_design_guide_direct_action_shell_card_html")
    rows = _scenario_rows()
    source_checks = {
        "card_projection_exported": '"build_final_design_guide_direct_shell_card_projection"' in final_source,
        "card_projection_imported": (
            "build_final_design_guide_direct_shell_card_projection as _build_final_design_guide_direct_shell_card_projection"
            in inputs_source
        ),
        "helper_uses_card_projection": "_build_final_design_guide_direct_shell_card_projection(" in helper,
        "helper_no_family_row_builder": "_design_guide_family_row_from_overview(" not in helper,
        "helper_no_display_util_formatter": "_design_guide_format_display_util(" not in helper,
        "helper_no_active_failure_key_decision": "_overview_active_failure_keys(" not in helper,
        "helper_no_payload_id_builder": "_generic_family_owned_payload_id(" not in helper,
        "helper_no_problem_bits": "problem_bits" not in helper,
        "helper_no_local_preview_rows": "preview_rows" not in helper,
        "helper_still_renders_html": "_design_guide_dashboard_card_html_with_render_model(" in helper,
        "final_publication_no_streamlit_import": "import streamlit" not in final_source.lower()
        and "from streamlit" not in final_source.lower(),
        "final_publication_no_inputs_page_import": "inputs_page" not in final_source,
    }
    failures: list[str] = []
    for row in rows:
        for key, passed in dict(row["checks"]).items():
            if passed is not True:
                failures.append(f"scenario:{row['name']}:{key}")
    for key, value in source_checks.items():
        if value is not True:
            failures.append(f"source:{key}")
    status = "PASS" if not failures else "FAIL"
    return {
        "schema": "design_guide_direct_shell_card_projection_cutover.v1",
        "status": status,
        "surface": "direct action shell card projection",
        "projection_scenarios": rows,
        "source_checks": source_checks,
        "failures": failures,
        "ownership_after": {
            "current_preview_row_projection": "FinalDesignGuidePublication",
            "active_strength_shell_row_projection": "FinalDesignGuidePublication",
            "cta_payload_id_projection": "Design Brain publication helper via FinalDesignGuidePublication projection",
            "html_rendering": "inputs_page.py",
            "apply_routing": "inputs_page.py",
        },
        "product_behavior_changed": False,
    }


def _write_artifacts(payload: dict[str, Any]) -> tuple[Path, Path, Path]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    json_path = ARTIFACT_DIR / f"design_guide_direct_shell_card_projection_cutover_{timestamp}.json"
    audit_path = AUDIT_DIR / f"design_guide_direct_shell_card_projection_cutover_{timestamp}.md"
    report_path = REPORT_DIR / f"design_brain_physical_extraction_direct_shell_card_projection_{timestamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Direct Shell Card Projection Cutover",
        "",
        f"Status: `{payload['status']}`",
        "",
        "## Surface Targeted",
        "Direct action shell current/preview rows, active-strength row shaping, and CTA payload-id projection.",
        "",
        "## Ownership After",
    ]
    for key, value in dict(payload["ownership_after"]).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Source Checks",
        ]
    )
    for key, value in dict(payload["source_checks"]).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Scenario Checks",
        ]
    )
    for row in payload["projection_scenarios"]:
        lines.append(f"- `{row['name']}`: {all(dict(row['checks']).values())}")
    lines.extend(
        [
            "",
            "## Failures",
            *(f"- {failure}" for failure in payload["failures"]),
        ]
    )
    text = "\n".join(lines) + "\n"
    audit_path.write_text(text, encoding="utf-8")
    report_path.write_text(text, encoding="utf-8")
    return json_path, audit_path, report_path


def main() -> int:
    payload = _build_payload()
    json_path, audit_path, report_path = _write_artifacts(payload)
    print(f"design_guide_direct_shell_card_projection_cutover {payload['status']}")
    print(f"json={json_path}")
    print(f"audit={audit_path}")
    print(f"report={report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
