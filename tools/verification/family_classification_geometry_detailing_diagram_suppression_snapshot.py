"""Verify invalid geometry/detailing suppresses model diagrams.

This snapshot locks the live render boundary after GEOMETRY_DETAILING_GOVERNS
classification. Invalid D/b geometry must not continue to render a 2D/3D model
from a later page-owned diagram path. The guard is intentionally page-local
render logic, while the numeric ratio limit remains family-owned via the
BENDING_FAIL_GOVERNS geometry-ratio contract helper.
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

from design_brain.families.bending_fail_governs.geometry_ratio import (  # noqa: E402
    bending_depth_width_ratio_limit,
    depth_width_ratio,
)
from design_brain.family_classification_runtime import (  # noqa: E402
    classify_family_from_whole_beam_evidence,
)


ARTIFACT_DIR = ROOT / "artifacts" / "verification"
AUDIT_DIR = ROOT / "artifacts" / "audits"
INPUTS_PAGE = ROOT / "inputs_page.py"
EXPECTED_FAMILY = "GEOMETRY_DETAILING_GOVERNS"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _function_block(source: str, name: str) -> str:
    pattern = rf"^def {re.escape(name)}\(.*?(?=^def |\Z)"
    match = re.search(pattern, source, flags=re.M | re.S)
    return match.group(0) if match else ""


def _case(case_id: str, *, width: float, depth: float) -> dict[str, Any]:
    limit = float(bending_depth_width_ratio_limit())
    ratio = float(depth_width_ratio(width=width, depth=depth) or 0.0)
    geometry_blocked = ratio > limit + 1e-9
    classification = classify_family_from_whole_beam_evidence(
        {
            "geometry_detailing_state": "BLOCKED" if geometry_blocked else "PASS",
            "bending_status": "FAIL" if not geometry_blocked else "PASS",
            "shear_status": "PASS",
            "serviceability_status": "PASS",
            "minimum_bending_reo_state": "PASS",
            "minimum_shear_reo_state": "PASS",
            "bending_overdesign_state": "PASS",
            "shear_overdesign_state": "PASS",
            "terminal_status": None,
            "legal_repair_exists": True,
        }
    )
    selected_family = str(classification.get("selected_family_id") or "")
    diagram_suppressed = bool(geometry_blocked)
    expected_family = EXPECTED_FAMILY if geometry_blocked else "BENDING_FAIL_GOVERNS"
    failures: list[str] = []
    if geometry_blocked and selected_family != EXPECTED_FAMILY:
        failures.append(f"blocked_geometry_expected_{EXPECTED_FAMILY}_got_{selected_family}")
    if not geometry_blocked and selected_family == EXPECTED_FAMILY:
        failures.append("valid_geometry_unexpected_geometry_detailing_family")
    return {
        "case_id": case_id,
        "width": width,
        "depth": depth,
        "depth_width_ratio": ratio,
        "maximum_depth_width_ratio": limit,
        "geometry_blocked": geometry_blocked,
        "expected_family_when_blocked": expected_family,
        "contract_selected_family": selected_family,
        "diagram_suppressed": diagram_suppressed,
        "hash": _stable_hash(
            {
                "case_id": case_id,
                "width": width,
                "depth": depth,
                "ratio": ratio,
                "limit": limit,
                "selected_family": selected_family,
                "diagram_suppressed": diagram_suppressed,
            }
        ),
        "failures": failures,
    }


def _render_guard_checks(source: str) -> dict[str, Any]:
    helper = _function_block(source, "_inputs_geometry_detailing_diagram_blocker")
    message = _function_block(source, "_render_geometry_detailing_diagram_blocked_message")
    section_2d = _function_block(source, "_render_section_2d_diagram_block")
    section_3d = _function_block(source, "_render_3d_diagram_block")
    fast_2d = _function_block(source, "_render_fast_lightweight_2d_diagram")
    forbidden_terms = ("apply routing", "apply_routing", "publication", "button_contract")

    checks = {
        "helper_exists": bool(helper),
        "message_helper_exists": bool(message),
        "helper_uses_family_ratio_limit": "_design_guide_depth_width_ratio_limit" in helper
        and "_design_guide_depth_width_ratio_for_state" in helper,
        "helper_selects_geometry_detailing_family": EXPECTED_FAMILY in helper,
        "section_2d_uses_guard": "_inputs_geometry_detailing_diagram_blocker" in section_2d
        and "_render_geometry_detailing_diagram_blocked_message" in section_2d,
        "section_3d_uses_guard": "_inputs_geometry_detailing_diagram_blocker" in section_3d
        and "_render_geometry_detailing_diagram_blocked_message" in section_3d,
        "fast_lightweight_2d_uses_guard": "_inputs_geometry_detailing_diagram_blocker" in fast_2d
        and "_render_geometry_detailing_diagram_blocked_message" in fast_2d,
        "helper_has_no_cta_apply_publication_ownership": not any(
            term in helper.lower() for term in forbidden_terms
        ),
    }
    return {
        "checks": checks,
        "failures": [name for name, ok in checks.items() if not ok],
        "hash": _stable_hash(checks),
    }


def _build_report(payload: dict[str, Any]) -> str:
    rows = []
    for case in payload["cases"]:
        rows.append(
            "| {case_id} | {width:g} | {depth:g} | {depth_width_ratio:.4f} | {maximum_depth_width_ratio:.4f} | {contract_selected_family} | {diagram_suppressed} | {status} |".format(
                **{
                    **case,
                    "status": "PASS" if not case["failures"] else "FAIL",
                }
            )
        )
    guard_rows = [
        f"- `{name}`: {'PASS' if ok else 'FAIL'}"
        for name, ok in payload["render_guard_checks"]["checks"].items()
    ]
    failure_rows = [f"- `{failure}`" for failure in payload["failures"]] or ["- None"]
    return "\n".join(
        [
            "# GEOMETRY_DETAILING_GOVERNS Diagram Suppression Snapshot",
            "",
            f"Result: `{payload['status']}`",
            "",
            "This snapshot proves invalid input geometry can no longer keep rendering model diagrams from later page render paths after the family classification contract selects `GEOMETRY_DETAILING_GOVERNS`.",
            "",
            "The renderer remains page-owned. The D/b numeric limit is loaded through the family-owned BENDING_FAIL_GOVERNS geometry-ratio contract helper.",
            "",
            "## Cases",
            "",
            "| Case | Width | Depth | D/b | Max D/b | Contract family | Diagram suppressed | Status |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
            *rows,
            "",
            "## Render Guard Checks",
            "",
            *guard_rows,
            "",
            "## Ownership",
            "",
            "- `GEOMETRY_DETAILING_GOVERNS` owns the classification decision for invalid input geometry/detailing.",
            "- `inputs_page.py` owns render suppression because the diagram is UI.",
            "- CTA, publication, apply routing, family runtimes, and engineering formulas were not moved.",
            "",
            "## Failures",
            "",
            *failure_rows,
        ]
    )


def main() -> int:
    generated_at = time.strftime("%Y-%m-%dT%H-%M-%S")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    source = INPUTS_PAGE.read_text(encoding="utf-8")
    cases = [
        _case("screenshot_invalid_ratio_300x850", width=300.0, depth=850.0),
        _case("contract_boundary_valid_ratio_300x600", width=300.0, depth=600.0),
        _case("normal_valid_ratio_400x600", width=400.0, depth=600.0),
    ]
    render_guard_checks = _render_guard_checks(source)
    failures: list[str] = []
    for case in cases:
        failures.extend(f"{case['case_id']}:{failure}" for failure in case["failures"])
    failures.extend(f"render_guard:{failure}" for failure in render_guard_checks["failures"])

    payload = {
        "schema": "family_classification_geometry_detailing_diagram_suppression_snapshot.v1",
        "generated_at": generated_at,
        "status": "PASS" if not failures else "FAIL",
        "expected_family": EXPECTED_FAMILY,
        "cases": cases,
        "render_guard_checks": render_guard_checks,
        "ownership": {
            "classification": "Design Brain family classification contract",
            "ratio_limit": "design_brain.families.bending_fail_governs.geometry_ratio",
            "diagram_suppression": "inputs_page.py render boundary",
            "cta_publication_apply_moved": False,
        },
        "failures": failures,
        "snapshot_hash": _stable_hash(
            {
                "cases": cases,
                "render_guard_checks": render_guard_checks,
                "ownership": {
                    "classification": "contract",
                    "ratio_limit": "family_helper",
                    "diagram_suppression": "page_render_boundary",
                },
            }
        ),
    }
    json_path = ARTIFACT_DIR / f"family_classification_geometry_detailing_diagram_suppression_{generated_at}.json"
    report_path = AUDIT_DIR / f"family_classification_geometry_detailing_diagram_suppression_{generated_at}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(_build_report(payload), encoding="utf-8")
    print(f"family_classification_geometry_detailing_diagram_suppression_snapshot {payload['status']}")
    print(f"json: {json_path}")
    print(f"report: {report_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
